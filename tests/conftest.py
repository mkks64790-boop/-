from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import db as backend_db
from backend import main as backend_main
from backend.services import batch_service, dataset_service, lyric_service


def _patch_backend_paths(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    backend_root = root / "backend"
    shared_root = root / "shared_data"
    monkeypatch.setattr(backend_db, "DB_PATH", str(backend_root / "feishark.db"), raising=False)
    monkeypatch.setattr(backend_db, "PROJECT_ROOT", str(root), raising=False)
    monkeypatch.setattr(backend_db, "WEIGHTS_DIR", str(shared_root / "weights"), raising=False)
    monkeypatch.setattr(backend_db, "OUTPUT_ROOT", str(shared_root / "outputs"), raising=False)
    monkeypatch.setattr(backend_db, "JOBS_ROOT", str(shared_root / "jobs"), raising=False)
    monkeypatch.setattr(backend_db, "BATCHES_ROOT", str(shared_root / "batches"), raising=False)

    monkeypatch.setattr(dataset_service, "PROJECT_ROOT", str(root), raising=False)
    monkeypatch.setattr(dataset_service, "JOBS_ROOT", str(shared_root / "jobs"), raising=False)

    monkeypatch.setattr(batch_service, "PROJECT_ROOT", str(root), raising=False)
    monkeypatch.setattr(batch_service, "BATCHES_ROOT", str(shared_root / "batches"), raising=False)

    monkeypatch.setattr(lyric_service, "PROJECT_ROOT", str(root), raising=False)

    monkeypatch.setattr(backend_main, "UPLOAD_DIR", str(shared_root / "uploads"), raising=False)
    monkeypatch.setattr(backend_main, "OUTPUT_ROOT", str(shared_root / "outputs"), raising=False)
    monkeypatch.setattr(backend_main, "DATASET_DIR", str(shared_root / "datasets"), raising=False)
    monkeypatch.setattr(backend_main, "WEIGHTS_DIR", str(shared_root / "weights"), raising=False)


@pytest.fixture()
def isolated_backend(tmp_path, monkeypatch):
    root = tmp_path / "feishark"
    root.mkdir(parents=True, exist_ok=True)
    (root / "backend").mkdir(parents=True, exist_ok=True)
    (root / "shared_data").mkdir(parents=True, exist_ok=True)
    _patch_backend_paths(monkeypatch, root)
    backend_db.init_db()
    return root


@pytest.fixture()
def client(isolated_backend):
    with TestClient(backend_main.app) as test_client:
        yield test_client
