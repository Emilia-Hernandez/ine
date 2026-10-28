from __future__ import annotations

import json
from pathlib import Path

import pytest

import radar27.publishing.dashboard_release as publication


def _fake_source(root: Path) -> None:
    (root / "dashboard/data").mkdir(parents=True)
    (root / "dashboard/assets").mkdir(parents=True)
    for name in publication.DATA_FILES:
        (root / "dashboard/data" / name).write_text("data", encoding="utf-8")
    (root / "dashboard/data/manifest.json").write_text(
        '{"handoff_version":"model.1","security_version":"security.1"}\n', encoding="utf-8"
    )
    for name in publication.ASSET_FILES:
        (root / "dashboard/assets" / name).write_text("asset", encoding="utf-8")


def test_publication_requires_approval_and_failed_release_keeps_pointer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_source(tmp_path)
    pointer = tmp_path / "dashboard/data/current_release.json"
    pointer.write_text('{"dashboard_release_version":"old"}\n', encoding="utf-8")
    monkeypatch.setattr(publication, "_validate_source", lambda *args: {"handoff_version": "model.1", "security_version": "security.1"})
    with pytest.raises(PermissionError):
        publication.publish_dashboard_release(tmp_path, "new", "model.1", False)
    (tmp_path / "dashboard/assets" / publication.ASSET_FILES[0]).unlink()
    with pytest.raises(FileNotFoundError):
        publication.publish_dashboard_release(tmp_path, "broken", "model.1", True)
    assert json.loads(pointer.read_text())["dashboard_release_version"] == "old"


def test_publication_and_rollback_switch_one_atomic_pointer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_source(tmp_path)
    monkeypatch.setattr(publication, "_validate_source", lambda *args: {"handoff_version": "model.1", "security_version": "security.1"})
    first = publication.publish_dashboard_release(tmp_path, "release-1", "model.1", True)
    assert first["dashboard_release_version"] == "release-1"
    for name in publication.DATA_FILES:
        (tmp_path / "dashboard/data" / name).write_text("new-data", encoding="utf-8")
    (tmp_path / "dashboard/data/manifest.json").write_text(
        '{"handoff_version":"model.1","security_version":"security.1"}\n', encoding="utf-8"
    )
    second = publication.publish_dashboard_release(tmp_path, "release-2", "model.1", True)
    assert second["dashboard_release_version"] == "release-2"
    rolled = publication.rollback_dashboard_release(tmp_path, "release-1", True)
    assert rolled["rollback"] is True
    assert json.loads((tmp_path / "dashboard/data/current_release.json").read_text())["dashboard_release_version"] == "release-1"
