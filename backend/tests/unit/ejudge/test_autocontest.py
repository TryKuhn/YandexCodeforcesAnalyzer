"""Automatic ejudge contests (blocks of N problems) for publications without a contest id."""
from __future__ import annotations

import re

import pytest
from sqlalchemy import select

import api.user.nlogn.publish as publish
from api.user.ejudge import autocontest
from api.user.ejudge.config import EjudgeConfig
from api.user.ejudge.remote import CommandResult
from api.user.ejudge.servecfg import ServeCfg
from models.user.integrations import EjudgeAutoContest, NlognPublication
from settings import settings
from tests.unit.ejudge.helpers import SERVE_CFG, FakeHost, package_zip
from tests.unit.nlogn.fixtures import HTML_STATEMENTS

JUDGES = "/home/judges"
XML_DIR = f"{JUDGES}/data/contests"
TEMPLATE_XML = """<?xml version="1.0" encoding="utf-8" ?>
<contest id="42" autoregister="no" disable_team_password="yes">
  <name>Course contest 42</name>
  <name_en>Course contest 42</name_en>
  <root_dir>/home/judges/000042</root_dir>
  <caps>
    <cap login="nlogn-judge">MASTER_SET</cap>
  </caps>
</contest>
"""
CONFIG = EjudgeConfig(source="server", ssh_host="ejudge.local", judges_dir=JUDGES)


class ContestHost(FakeHost):
    """FakeHost plus the commands contest creation runs (ls, mkdir/cp -a, chmod)."""

    async def run(self, command: str) -> CommandResult:
        unq = command.replace("'", "")
        m = re.match(r"^ls -1 (\S+)$", unq)
        if m:
            base = m.group(1).rstrip("/") + "/"
            names = sorted({k[len(base):].split("/")[0] for k in self.files if k.startswith(base)})
            self.commands.append(command)
            return CommandResult(0, "\n".join(names) + "\n", "")
        if unq.startswith("set -e; mkdir "):
            self.commands.append(command)
            new_dir = unq.split()[3].rstrip(";")
            src = unq.split("cp -a ")[1].split()[0]
            if any(k.startswith(new_dir + "/") for k in self.files):
                return CommandResult(1, "", f"mkdir: {new_dir}: File exists")
            for k, v in list(self.files.items()):
                if k.startswith(src + "/"):
                    self.files[new_dir + "/conf/" + k[len(src) + 1:]] = v
            for k in [k for k in self.files if k.startswith(new_dir + "/conf/serve.cfg.bak-")]:
                del self.files[k]
            return CommandResult(0, "", "")
        if unq.startswith("chmod -R a+rX "):
            self.commands.append(command)
            return CommandResult(0, "", "")
        return await super().run(command)


def contest_files(contest_id: int, problems: int = 1) -> dict[str, bytes]:
    cfg = SERVE_CFG + "".join(
        f'\n[problem]\nid = {i}\nshort_name = "{chr(65 + i - 1)}"\ninternal_name = "p{i}"\n'
        for i in range(2, problems + 1)
    )
    return {
        f"{JUDGES}/{contest_id:06d}/conf/serve.cfg": cfg.encode(),
        f"{JUDGES}/{contest_id:06d}/conf/variant.map": b"",
        f"{JUDGES}/{contest_id:06d}/conf/serve.cfg.bak-20260101": b"old",
        f"{XML_DIR}/{contest_id:06d}.xml": TEMPLATE_XML.replace('id="42"', f'id="{contest_id}"')
        .replace("000042", f"{contest_id:06d}").encode(),
    }


@pytest.fixture(autouse=True)
def settings_reset(monkeypatch):
    monkeypatch.setattr(settings, "EJUDGE_AUTO_CONTEST_SIZE", 10)
    monkeypatch.setattr(settings, "EJUDGE_TEMPLATE_CONTEST", 0)
    monkeypatch.setattr(settings, "EJUDGE_CONTESTS_XML_DIR", "")


async def no_lock(db, key):
    return None


def test_blank_serve_cfg_keeps_setup_and_drops_problems():
    template = "contest_id = 42\n" + SERVE_CFG.replace("advanced_layout\n", "")
    cfg = ServeCfg(autocontest.blank_serve_cfg(ServeCfg(template), 43))
    assert cfg.concrete_problems() == []
    assert [s.values.get("short_name") for s in cfg.abstract_problems()] == ["Generic"]
    assert cfg.advanced_layout and cfg.score_system == "olympiad"
    assert "[language]" in cfg.text() and cfg.globals["contest_id"] == "43"


def test_clone_contest_xml():
    xml = autocontest.clone_contest_xml(TEMPLATE_XML, 42, 1502, "TaskForge for NlogN #1")
    assert '<contest id="1502"' in xml and "<root_dir>/home/judges/001502</root_dir>" in xml
    assert "<name>TaskForge for NlogN #1</name>" in xml and "<name_en>TaskForge for NlogN #1</name_en>" in xml
    assert '<cap login="nlogn-judge">MASTER_SET</cap>' in xml  # the NlogN judges keep their rights
    with pytest.raises(Exception, match="не похоже"):
        autocontest.clone_contest_xml(TEMPLATE_XML, 43, 1502, "x")


async def test_allocate_creates_a_block_from_the_published_contest_and_reuses_it(db, user):
    host = ContestHost({**contest_files(42), **contest_files(1501)})
    db.add(NlognPublication(user_id=user.id, polygon_id=1, ejudge_contest_id=42, ejudge_problem_id=1,
                            short_name="A"))
    await db.commit()

    contest_id, created = await autocontest.allocate_contest(host, CONFIG, db, user.id, lock=no_lock)

    assert (contest_id, created) == (1502, True)  # after the highest number in use
    serve = ServeCfg(host.files[f"{JUDGES}/001502/conf/serve.cfg"].decode())
    assert serve.concrete_problems() == [] and serve.advanced_layout
    assert f"{JUDGES}/001502/conf/variant.map" in host.files
    assert not any(".bak-" in k for k in host.files if k.startswith(f"{JUDGES}/001502/"))
    xml = host.files[f"{XML_DIR}/001502.xml"].decode()
    assert '<contest id="1502"' in xml and "TaskForge for NlogN #1" in xml
    row = (await db.execute(select(EjudgeAutoContest))).scalars().one()
    assert (row.contest_id, row.template_id, row.created_by) == (1502, 42, user.id)

    # room left: the same block
    assert await autocontest.allocate_contest(host, CONFIG, db, user.id, lock=no_lock) == (1502, False)


async def test_a_full_block_gets_a_successor_cloned_from_it(db, user, monkeypatch):
    monkeypatch.setattr(settings, "EJUDGE_AUTO_CONTEST_SIZE", 3)
    host = ContestHost({**contest_files(42), **contest_files(1600, problems=3)})
    db.add(EjudgeAutoContest(host_key=autocontest.host_key(CONFIG), contest_id=1600, template_id=42))
    await db.commit()

    contest_id, created = await autocontest.allocate_contest(host, CONFIG, db, user.id, lock=no_lock)

    assert (contest_id, created) == (1601, True)
    rows = (await db.execute(select(EjudgeAutoContest).order_by(EjudgeAutoContest.contest_id))).scalars().all()
    assert [(r.contest_id, r.template_id) for r in rows] == [(1600, 42), (1601, 1600)]
    assert "TaskForge for NlogN #2" in host.files[f"{XML_DIR}/001601.xml"].decode()


async def test_no_template_found_is_a_clear_error(db, user):
    host = ContestHost({f"{XML_DIR}/README": b"", f"{JUDGES}/data/ejudge.xml": b""})
    with pytest.raises(Exception, match="контест-образец"):
        await autocontest.allocate_contest(host, CONFIG, db, user.id, lock=no_lock)


# --------------------------------------------------------------------------- through the publication
@pytest.fixture
def polygon(polygon_api):
    data = package_zip([{"sample": True}, {}, {}], statements=HTML_STATEMENTS)
    polygon_api.respond("problem.packages", [{"id": 4, "state": "READY"}])
    polygon_api.respond("problem.package", lambda params: data)
    return polygon_api


@pytest.fixture
def server_ejudge(monkeypatch):
    monkeypatch.setattr(settings, "EJUDGE_SSH_HOST", "ejudge.local")
    monkeypatch.setattr(settings, "EJUDGE_JUDGES_DIR", JUDGES)
    monkeypatch.setattr(settings, "EJUDGE_URL", "")
    monkeypatch.setattr(settings, "EJUDGE_GVALUER_PATH", "")
    # an allowed-contests list does not stop the blocks this app created itself
    monkeypatch.setattr(settings, "EJUDGE_ALLOWED_CONTESTS", "42")
    monkeypatch.setattr(autocontest, "_pg_lock", no_lock)
    monkeypatch.setattr(settings, "EJUDGE_TEMPLATE_CONTEST", 42)


async def test_publication_without_contest_goes_to_a_block_and_stays_there(polygon, server_ejudge, db, user):
    host = ContestHost(contest_files(42))
    first = await publish.run_publish(publish.PublishRequest(polygon_id=555, mode="pull"), user.id, db,
                                      host_factory=host)
    assert first["ejudge_contest_id"] == 43 and first["auto_contest"] == {"id": 43, "created": True}
    assert first["ejudge_problem_id"] == 1 and first["short_name"] == "A"  # the block starts empty

    again = await publish.run_publish(publish.PublishRequest(polygon_id=555, mode="pull"), user.id, db,
                                      host_factory=host)
    assert again["auto_contest"] == {"id": 43, "created": False}
    assert again["ejudge_problem_id"] == 1  # updated in place, not a second copy

    other = await publish.run_publish(publish.PublishRequest(polygon_id=556, mode="pull"), user.id, db,
                                      host_factory=host)
    assert (other["ejudge_contest_id"], other["short_name"]) == (43, "B")
