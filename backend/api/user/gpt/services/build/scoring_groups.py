"""Test-group / points configuration for the build pipeline.

Parses the LaTeX scoring table into group configs, enables groups+points on the
Polygon problem, and distributes built tests across groups proportionally to
their points. Moved verbatim (behaviour-preserving) out of upload_orchestrator.
"""
import logging
import re

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.files.test.get.tests import get_tests
from api.user.polygon.files.test.post.save_test import save_test
from api.user.polygon.problem.settings.enable_groups import enable_groups
from api.user.polygon.problem.settings.enable_points import enable_points
from api.user.polygon.problem.settings.save_test_group import save_test_group
from api.user.polygon.problem.settings.set_test_group import set_test_group

logger = logging.getLogger(__name__)


def subtasks_to_groups(subtasks: list[dict] | None) -> list[dict]:
    """Convert a structured subtask plan into group config dicts.

    Returns list of {group, points, dependencies, feedback_policy, num_tests}.
    Uses ``icpc`` feedback (stop on first failed test) for every subtask.
    """
    if not subtasks:
        return []
    groups = []
    for st in subtasks:
        groups.append({
            "group": str(st.get("group")),
            "points": int(st.get("points", 0)),
            "dependencies": [str(d) for d in (st.get("depends_on") or [])],
            "feedback_policy": "icpc",
            "num_tests": int(st.get("num_tests", 0)),
        })
    return groups


def parse_scoring_groups(scoring_latex: str | None) -> list[dict]:
    """Parse a LaTeX scoring table into group config dicts.

    Returns list of {group, points, dependencies, feedback_policy}. Skips
    group 0 (sample tests with no points).
    """
    if not scoring_latex:
        return []

    tab_match = re.search(
        r"\\begin\{tabular\}(.*?)\\end\{tabular\}", scoring_latex, re.DOTALL
    )
    if not tab_match:
        return []

    inner = tab_match.group(1)
    inner = re.sub(r"^\s*\{[^}]*\}\s*", "", inner)

    def clean_cell(cell: str) -> str:
        cell = re.sub(r"\\textbf\s*\{\\scriptsize\s*\{([^}]*)\}\}", r"\1", cell)
        cell = re.sub(r"\\textbf\s*\{([^}]*)\}", r"\1", cell)
        cell = re.sub(r"\\scriptsize\s*\{([^}]*)\}", r"\1", cell)
        cell = re.sub(r"\$([^$]+)\$", r"\1", cell)
        cell = cell.replace("\\hline", "").strip()
        return cell

    rows = []
    for seg in inner.split("\\\\"):
        seg = seg.replace("\\hline", "").strip()
        if seg:
            rows.append([clean_cell(c) for c in seg.split("&")])

    if len(rows) < 2:
        return []

    groups = []
    for row in rows[1:]:
        if len(row) < 5:
            continue
        group_num = row[0].strip()
        points_str = row[1].strip()
        deps_str = row[3].strip()
        feedback_str = row[4].strip()

        if group_num == "0" or points_str == "--":
            continue

        try:
            points = int(float(re.sub(r"[^0-9.]", "", points_str) or "0"))
        except (ValueError, TypeError):
            continue

        deps = []
        if deps_str and deps_str != "--":
            for d in deps_str.split(","):
                d = d.strip()
                if d and d != "--":
                    deps.append(d)

        feedback = (
            "icpc"
            if ("первая" in feedback_str.lower() or "first" in feedback_str.lower())
            else "complete"
        )

        groups.append(
            {
                "group": group_num,
                "points": points,
                "dependencies": deps,
                "feedback_policy": feedback,
            }
        )

    return groups


async def setup_groups_and_points(
    session_id: str,
    problem_id: int,
    user_id: int,
    problem_settings: dict,
    scoring_latex: str | None,
    db: AsyncSession,
    subtasks: list[dict] | None = None,
) -> list[dict]:
    """Enable groups/points on Polygon and configure each group.

    Prefers the structured ``subtasks`` plan (carries per-group test counts);
    falls back to parsing the Scoring LaTeX table. Returns the group configs for
    later test assignment.
    """
    enable_grp = problem_settings.get("enable_groups", False)
    enable_pts = problem_settings.get("enable_points", False)

    if not enable_grp and not enable_pts:
        return []

    groups = subtasks_to_groups(subtasks) or parse_scoring_groups(scoring_latex)

    if enable_grp:
        try:
            await enable_groups(problem_id, "tests", True, user_id, db)
            logger.info(f"[{session_id}] Groups enabled")
        except Exception as e:
            logger.warning(f"[{session_id}] Failed to enable groups: {e}")

    if enable_pts:
        try:
            await enable_points(problem_id, True, user_id, db)
            logger.info(f"[{session_id}] Points enabled")
        except Exception as e:
            logger.warning(f"[{session_id}] Failed to enable points: {e}")

    for group_cfg in groups:
        try:
            await save_test_group(
                problem_id=problem_id,
                test_set="tests",
                group=group_cfg["group"],
                points=group_cfg["points"],
                points_policy="complete-group",
                feedback_policy=group_cfg["feedback_policy"],
                dependencies=group_cfg["dependencies"],
                user_id=user_id,
                db=db,
            )
            logger.info(
                f"[{session_id}] Configured group {group_cfg['group']} "
                f"({group_cfg['points']} pts, deps={group_cfg['dependencies']})"
            )
        except Exception as e:
            logger.warning(
                f"[{session_id}] Failed to configure group {group_cfg['group']}: {e}"
            )

    return groups


def _slice_counts(groups: list[dict], total: int) -> list[int]:
    """How many tests each group gets.

    Uses each group's planned ``num_tests`` when the plan covers all tests;
    otherwise distributes proportionally to points. The last group absorbs any
    remainder so every test is assigned.
    """
    planned = [max(0, int(g.get("num_tests", 0))) for g in groups]
    if sum(planned) and sum(planned) <= total:
        counts = planned[:]
        counts[-1] += total - sum(planned)
        return counts

    total_pts = sum(g["points"] for g in groups) or len(groups)
    counts, assigned = [], 0
    for i, g in enumerate(groups):
        if i == len(groups) - 1:
            counts.append(total - assigned)
        else:
            c = max(1, round(total * g["points"] / total_pts))
            counts.append(c)
            assigned += c
    return counts


async def assign_tests_to_groups(
    session_id: str,
    problem_id: int,
    user_id: int,
    groups: list[dict],
    db: AsyncSession,
) -> dict:
    """After a build, assign contiguous test ranges to groups and put each
    group's full points on its first test (COMPLETE_GROUP scoring sums test
    points, so one point-bearing test per group is the correct configuration).

    ``testInput`` is optional in problem.saveTest, so the first test's points are
    updated by index without touching its script-generated input.

    Returns {group: [test_indices]} for reporting back to the user.
    """
    mapping: dict = {}
    if not groups:
        return mapping

    try:
        tests = await get_tests(problem_id, "tests", user_id, db, no_inputs=True)
        non_example_indices = sorted(
            t.get("index", 0) for t in tests if not t.get("useInStatements", False)
        )
        if not non_example_indices:
            logger.info(f"[{session_id}] No non-example tests to assign to groups")
            return mapping

        total = len(non_example_indices)
        counts = _slice_counts(groups, total)

        assigned = 0
        for group_cfg, count in zip(groups, counts):
            slice_indices = non_example_indices[assigned: assigned + count]
            assigned += count
            if not slice_indices:
                continue

            indices_str = ",".join(str(idx) for idx in slice_indices)
            try:
                await set_test_group(
                    problem_id, "tests", group_cfg["group"], indices_str, user_id, db,
                )
            except Exception as e:
                logger.warning(
                    f"[{session_id}] Failed to assign group {group_cfg['group']}: {e}"
                )
                continue

            mapping[group_cfg["group"]] = slice_indices

            try:
                await save_test(
                    problem_id=problem_id, testset="tests",
                    test_index=slice_indices[0], test_input=None,
                    test_group=group_cfg["group"],
                    test_points=float(group_cfg["points"]),
                    user_id=user_id, db=db,
                )
                logger.info(
                    f"[{session_id}] Group {group_cfg['group']}: tests [{indices_str}], "
                    f"{group_cfg['points']} pts on test {slice_indices[0]}"
                )
            except Exception as e:
                logger.warning(
                    f"[{session_id}] set points on test {slice_indices[0]} failed: {e}"
                )
    except Exception as e:
        logger.warning(f"[{session_id}] assign_tests_to_groups failed: {e}")
    return mapping
