"""ejudge contests this app creates itself for publications without a contest id.

Problems published to NlogN without an explicit ejudge contest go into "blocks":
contests created here, ``EJUDGE_AUTO_CONTEST_SIZE`` (10) problems each. While the
newest block has room it is reused; a full block gets a successor.

A new contest is a clone of a template contest that NlogN already judges on:

* ``<judges>/NNNNNN/conf/`` -- the template's ``conf/`` with every concrete
  ``[problem]`` removed from ``serve.cfg`` (languages, testers, abstract problems,
  the scoring setup stay) and ``advanced_layout`` on (the export needs it);
* ``<contests xml dir>/NNNNNN.xml`` -- the template's contest description with the
  new id, name and paths. It keeps the judges' capabilities, so the NlogN judge
  accounts can log into the new contest exactly as into the template.

The xml is written last: until then ejudge does not see the contest at all.
"""
from __future__ import annotations

import logging
import posixpath
import re
from collections.abc import Awaitable, Callable

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.user.ejudge.common import EjudgeError
from api.user.ejudge.config import EjudgeConfig
from api.user.ejudge.remote import EjudgeHost, q
from api.user.ejudge.servecfg import ServeCfg
from models.user.integrations import EjudgeAutoContest, NlognPublication
from settings import settings

logger = logging.getLogger(__name__)

_CONTEST_DIR_RE = re.compile(r"^\d{6}$")
_CONTEST_XML_RE = re.compile(r"^(\d{6})\.xml$")


def host_key(config: EjudgeConfig) -> str:
    return f"{config.ssh_user}@{config.ssh_host}:{config.ssh_port}{config.judges_dir}"


def contests_xml_dir(config: EjudgeConfig) -> str:
    return settings.EJUDGE_CONTESTS_XML_DIR or posixpath.join(config.judges_dir, "data", "contests")


def contest_name(number: int) -> str:
    # ASCII only: ejudge xml files are not always UTF-8
    return f"TaskForge for NlogN #{number}"


async def _ls(host: EjudgeHost, path: str) -> list[str]:
    result = await host.run(f"ls -1 {q(path)}")
    if result.exit_status != 0:
        raise EjudgeError(f"не удалось прочитать каталог {path} на сервере ejudge: "
                          f"{(result.stderr or result.stdout).strip()[:500]}")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


async def _serve_cfg(host: EjudgeHost, config: EjudgeConfig, contest_id: int) -> ServeCfg:
    path = posixpath.join(config.judges_dir, f"{contest_id:06d}", "conf", "serve.cfg")
    return ServeCfg(await host.read_text(path))


def blank_serve_cfg(template: ServeCfg, new_id: int) -> str:
    """The template's serve.cfg without its concrete problems (and with the new ``contest_id``, if it has one)."""
    concrete = {s.start for s in template.concrete_problems()}
    keep: list[str] = []
    for section in template.sections:
        if section.start not in concrete:
            keep.extend(template.lines[section.start:section.end])
    cfg = ServeCfg(template.newline.join(keep) + template.newline)
    if not cfg.advanced_layout:
        cfg.set_global("advanced_layout", 1)
    if "contest_id" in cfg.globals:
        cfg.set_global("contest_id", new_id)
    return cfg.text()


def clone_contest_xml(xml: str, template_id: int, new_id: int, name: str) -> str:
    """The template's contest description for the new contest."""
    root = re.search(r"<contest\b[^>]*>", xml)
    if root is None or not re.search(rf'\bid\s*=\s*"0*{template_id}"', root.group(0)):
        raise EjudgeError(f"описание контеста {template_id} на сервере ejudge не похоже на contest xml")
    head = re.sub(rf'(\bid\s*=\s*")0*{template_id}(")', rf"\g<1>{new_id}\g<2>", root.group(0), count=1)
    xml = xml[:root.start()] + head + xml[root.end():]
    # explicit directories of the template (root_dir, conf_dir, ...) point to the new one
    xml = xml.replace(f"/{template_id:06d}", f"/{new_id:06d}")
    xml = re.sub(r"<name>.*?</name>", f"<name>{name}</name>", xml, count=1, flags=re.S)
    xml = re.sub(r"<name_en>.*?</name_en>", f"<name_en>{name}</name_en>", xml, count=1, flags=re.S)
    return xml


async def existing_contest_ids(host: EjudgeHost, config: EjudgeConfig) -> set[int]:
    """Contest numbers in use: contest directories and contest descriptions."""
    ids = {int(name) for name in await _ls(host, config.judges_dir) if _CONTEST_DIR_RE.match(name)}
    for name in await _ls(host, contests_xml_dir(config)):
        m = _CONTEST_XML_RE.match(name)
        if m:
            ids.add(int(m.group(1)))
    return ids


async def choose_template(host: EjudgeHost, config: EjudgeConfig, db: AsyncSession) -> int:
    """The contest to clone, in this order:

    1. ``EJUDGE_TEMPLATE_CONTEST``;
    2. the newest block created here (it is known to work);
    3. the contest of the latest publication on this host (NlogN already judges there);
    4. the newest contest on the host with ``advanced_layout``.
    """
    if settings.EJUDGE_TEMPLATE_CONTEST:
        return settings.EJUDGE_TEMPLATE_CONTEST
    newest_block = (await db.execute(
        select(EjudgeAutoContest.contest_id).where(EjudgeAutoContest.host_key == host_key(config))
        .order_by(EjudgeAutoContest.contest_id.desc()).limit(1)
    )).scalar()
    if newest_block:
        return int(newest_block)
    # publications do not record the host; with one ejudge per installation the latest one is right,
    # and a wrong guess is caught below (a contest without a description is skipped)
    published = (await db.execute(
        select(NlognPublication.ejudge_contest_id).order_by(NlognPublication.updated_at.desc()).limit(5)
    )).scalars().all()
    xml_names = set(await _ls(host, contests_xml_dir(config)))
    for contest_id in published:
        if f"{contest_id:06d}.xml" in xml_names:
            return int(contest_id)
    dirs = sorted((int(n) for n in await _ls(host, config.judges_dir) if _CONTEST_DIR_RE.match(n)), reverse=True)
    for contest_id in dirs:
        if f"{contest_id:06d}.xml" not in xml_names:
            continue
        try:
            if (await _serve_cfg(host, config, contest_id)).advanced_layout:
                return contest_id
        except EjudgeError:
            continue
    raise EjudgeError("не нашёл на сервере ejudge контест-образец (с advanced_layout): укажите ID контеста "
                      "вручную или задайте EJUDGE_TEMPLATE_CONTEST")


async def create_contest(host: EjudgeHost, config: EjudgeConfig, template_id: int, new_id: int, name: str) -> None:
    """Clone ``template_id`` into ``new_id`` (see the module docstring)."""
    judges = config.judges_dir
    template_dir = posixpath.join(judges, f"{template_id:06d}")
    new_dir = posixpath.join(judges, f"{new_id:06d}")
    xml_dir = contests_xml_dir(config)
    template_xml = await host.read_text(posixpath.join(xml_dir, f"{template_id:06d}.xml"))
    new_xml = clone_contest_xml(template_xml, template_id, new_id, name)
    serve = blank_serve_cfg(await _serve_cfg(host, config, template_id), new_id)

    result = await host.run(
        f"set -e; mkdir {q(new_dir)}; cp -a {q(template_dir + '/conf')} {q(new_dir + '/conf')}; "
        f"rm -f {q(new_dir + '/conf')}/serve.cfg.bak-* {q(new_dir + '/conf')}/serve.cfg.tmp-*; "
        f"mkdir -p {q(new_dir + '/problems')}"
    )
    if result.exit_status != 0:
        raise EjudgeError(f"не удалось создать каталог контеста {new_id}: "
                          f"{(result.stderr or result.stdout).strip()[:500]}")
    try:
        await host.write_text(posixpath.join(new_dir, "conf", "serve.cfg"), serve)
        xml_path = posixpath.join(xml_dir, f"{new_id:06d}.xml")
        await host.write_text(xml_path + ".tmp", new_xml)
        await host.rename(xml_path + ".tmp", xml_path)
        await host.run(f"chmod -R a+rX {q(new_dir)}")
    except BaseException:
        await host.run(f"rm -rf {q(new_dir)} {q(posixpath.join(xml_dir, f'{new_id:06d}.xml.tmp'))}")
        raise


Locker = Callable[[AsyncSession, str], Awaitable[None]]


async def _pg_lock(db: AsyncSession, key: str) -> None:
    """A transaction-level advisory lock on Postgres (no-op elsewhere, e.g. in tests)."""
    if db.get_bind().dialect.name == "postgresql":
        await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": "ejudge-auto:" + key})


async def allocate_contest(
    host: EjudgeHost, config: EjudgeConfig, db: AsyncSession, user_id: int, *, lock: Locker = _pg_lock
) -> tuple[int, bool]:
    """``(contest id, created)``: the newest block if it has room, otherwise a new block.

    The advisory lock makes two concurrent publications agree on one new contest
    instead of creating two (it is held until the commit below).
    """
    key = host_key(config)
    await lock(db, key)
    size = max(1, settings.EJUDGE_AUTO_CONTEST_SIZE)
    newest = (await db.execute(
        select(EjudgeAutoContest).where(EjudgeAutoContest.host_key == key)
        .order_by(EjudgeAutoContest.contest_id.desc()).limit(1)
    )).scalars().first()
    if newest is not None:
        try:
            used = len((await _serve_cfg(host, config, newest.contest_id)).concrete_problems())
        except EjudgeError:
            used = size  # gone or unreadable: start a new block
        if used < size:
            await db.commit()
            return newest.contest_id, False

    template_id = await choose_template(host, config, db)
    new_id = max(await existing_contest_ids(host, config), default=0) + 1
    number = 1 + len((await db.execute(
        select(EjudgeAutoContest.id).where(EjudgeAutoContest.host_key == key)
    )).scalars().all())
    await create_contest(host, config, template_id, new_id, contest_name(number))
    db.add(EjudgeAutoContest(host_key=key, contest_id=new_id, template_id=template_id, created_by=user_id))
    await db.commit()
    logger.info("created ejudge contest %s from template %s for publications", new_id, template_id)
    return new_id, True


async def is_auto_contest(db: AsyncSession, config: EjudgeConfig, contest_id: int) -> bool:
    return (await db.execute(
        select(EjudgeAutoContest.id).where(
            EjudgeAutoContest.host_key == host_key(config), EjudgeAutoContest.contest_id == contest_id,
        )
    )).first() is not None
