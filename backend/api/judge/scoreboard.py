"""Standings maths: ICPC and IOI, as pure functions over submissions."""
from dataclasses import dataclass, field

from models.judge.contest import ScoringKind

# an ICPC wrong attempt costs this much, but only if the problem is solved later
PENALTY_MINUTES = 20


@dataclass(frozen=True)
class SubmissionFact:
    """The little a scoreboard needs to know about one submission."""

    user_id: int
    problem_id: int
    verdict: str
    score: float
    # minutes since the contest started
    minute: int


@dataclass
class ProblemCell:
    problem_id: int
    solved: bool = False
    attempts: int = 0
    score: float = 0.0
    # minute of the accepted submission, for ICPC penalty
    solved_at: int | None = None

    @property
    def penalty(self) -> int:
        if not self.solved or self.solved_at is None:
            return 0
        return self.solved_at + PENALTY_MINUTES * self.attempts


@dataclass
class ScoreboardRow:
    user_id: int
    display_name: str = ""
    is_official: bool = True
    cells: dict[int, ProblemCell] = field(default_factory=dict)

    @property
    def solved(self) -> int:
        return sum(1 for cell in self.cells.values() if cell.solved)

    @property
    def penalty(self) -> int:
        return sum(cell.penalty for cell in self.cells.values())

    @property
    def score(self) -> float:
        return round(sum(cell.score for cell in self.cells.values()), 6)


def build_rows(
    submissions: list[SubmissionFact],
    participants: dict[int, tuple[str, bool]],
    scoring: str,
) -> list[ScoreboardRow]:
    """Fold submissions into one row per participant, then rank them."""
    rows: dict[int, ScoreboardRow] = {
        user_id: ScoreboardRow(user_id=user_id, display_name=name, is_official=official)
        for user_id, (name, official) in participants.items()
    }

    for fact in sorted(submissions, key=lambda s: s.minute):
        row = rows.get(fact.user_id)
        if row is None:
            continue
        cell = row.cells.setdefault(fact.problem_id, ProblemCell(problem_id=fact.problem_id))

        if scoring == ScoringKind.IOI.value:
            # only the best result counts, later attempts never lower it
            cell.score = max(cell.score, fact.score)
            cell.attempts += 1
            if fact.verdict == "OK":
                cell.solved = True
                if cell.solved_at is None:
                    cell.solved_at = fact.minute
            continue

        if cell.solved:
            # attempts after a solve are free in ICPC
            continue
        if fact.verdict == "OK":
            cell.solved = True
            cell.solved_at = fact.minute
            cell.score = 1.0
        elif fact.verdict != "CE":
            # a compile error is not an attempt, everything else is
            cell.attempts += 1

    return rank(list(rows.values()), scoring)


def rank(rows: list[ScoreboardRow], scoring: str) -> list[ScoreboardRow]:
    """Order rows the way the scoring kind demands."""
    if scoring == ScoringKind.IOI.value:
        return sorted(rows, key=lambda r: (-r.score, r.display_name.lower()))
    return sorted(rows, key=lambda r: (-r.solved, r.penalty, r.display_name.lower()))


def places(rows: list[ScoreboardRow], scoring: str) -> list[int]:
    """Places for ranked rows; ties share a place, unofficial rows get 0."""
    result: list[int] = []
    previous_key = None
    previous_place = 0
    official_seen = 0

    for row in rows:
        if not row.is_official:
            result.append(0)
            continue
        official_seen += 1
        key = (
            (row.score,)
            if scoring == ScoringKind.IOI.value
            else (row.solved, -row.penalty)
        )
        if key == previous_key:
            result.append(previous_place)
        else:
            result.append(official_seen)
            previous_key, previous_place = key, official_seen
    return result
