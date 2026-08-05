"""Package import/export: every format must survive a round trip."""
import zipfile
from io import BytesIO

import pytest

from app.packaging import (NativeFormat, Package, PackageError, PackageTest,
                           PolygonFormat, available, get)

FORMATS = [NativeFormat(), PolygonFormat()]


def _package() -> Package:
    return Package(
        name="aplusb",
        tests=[
            PackageTest(1, b"2 3\n", b"5\n", points=20, is_sample=True),
            PackageTest(2, b"7 8\n", b"15\n", group="g1", points=30),
            PackageTest(3, b"-1 -2\n", b"-3\n", group="g1", points=50),
        ],
        checker=b"// testlib checker",
        time_limit_ms=2500,
        memory_limit_mb=64,
        files={"testlib.h": b"// testlib"},
    )


@pytest.mark.parametrize("fmt", FORMATS, ids=lambda f: f.name)
def test_round_trip_keeps_everything(fmt):
    original = _package()
    restored = fmt.materialize(fmt.export(original))

    assert restored.name == original.name
    assert restored.time_limit_ms == original.time_limit_ms
    assert restored.memory_limit_mb == original.memory_limit_mb
    assert restored.checker == original.checker
    assert len(restored.tests) == len(original.tests)


@pytest.mark.parametrize("fmt", FORMATS, ids=lambda f: f.name)
def test_round_trip_keeps_test_data(fmt):
    original = _package()
    restored = fmt.materialize(fmt.export(original))

    for before, after in zip(original.tests, restored.tests):
        assert after.input_data == before.input_data
        assert after.answer_data == before.answer_data
        assert after.points == before.points
        assert after.group == before.group
        assert after.is_sample == before.is_sample


@pytest.mark.parametrize("fmt", FORMATS, ids=lambda f: f.name)
def test_export_is_a_zip(fmt):
    archive = fmt.export(_package())
    with zipfile.ZipFile(BytesIO(archive)) as zip_file:
        assert zip_file.namelist()


@pytest.mark.parametrize("fmt", FORMATS, ids=lambda f: f.name)
def test_garbage_is_rejected(fmt):
    with pytest.raises(PackageError):
        fmt.materialize(b"definitely not a zip")


def test_polygon_layout_is_what_polygon_expects():
    archive = PolygonFormat().export(_package())
    with zipfile.ZipFile(BytesIO(archive)) as zip_file:
        names = set(zip_file.namelist())
    assert "problem.xml" in names
    assert "check.cpp" in names
    # Polygon keeps inputs as tests/NN and answers as tests/NN.a
    assert "tests/01" in names
    assert "tests/01.a" in names


def test_polygon_manifest_carries_limits_and_groups():
    archive = PolygonFormat().export(_package())
    with zipfile.ZipFile(BytesIO(archive)) as zip_file:
        manifest = zip_file.read("problem.xml").decode()
    assert "<time-limit>2500</time-limit>" in manifest
    # memory is stored in bytes over there
    assert str(64 * 1024 * 1024) in manifest
    assert 'name="g1"' in manifest


def test_cross_format_transfer():
    # a problem exported for Polygon can be read back and re-exported natively
    original = _package()
    via_polygon = PolygonFormat().materialize(PolygonFormat().export(original))
    restored = NativeFormat().materialize(NativeFormat().export(via_polygon))

    assert [t.answer_data for t in restored.tests] == [t.answer_data for t in original.tests]
    assert restored.time_limit_ms == original.time_limit_ms


def test_registry_lists_both_formats():
    assert {"native", "polygon"} <= set(available())
    assert get("polygon").name == "polygon"


def test_unknown_format_is_reported():
    with pytest.raises(PackageError):
        get("nosuchformat")


def test_package_without_groups_has_no_group_section():
    plain = Package(name="p", tests=[PackageTest(1, b"1\n", b"1\n")], checker=b"//")
    with zipfile.ZipFile(BytesIO(PolygonFormat().export(plain))) as zip_file:
        assert "<groups>" not in zip_file.read("problem.xml").decode()
