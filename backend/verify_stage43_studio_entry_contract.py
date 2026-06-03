from __future__ import annotations

import sys

from fastapi.testclient import TestClient

try:
    from .db import init_db
    from .main import app
except ImportError:
    from db import init_db
    from main import app


DEFAULT_JOB_ID = "task_stage41_ce1b32f2"


def _fail(message: str) -> int:
    print(f"[STAGE43A][FAIL] {message}")
    return 1


def main() -> int:
    job_id = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_JOB_ID
    init_db()
    client = TestClient(app)

    detail_resp = client.get(f"/api/jobs/{job_id}")
    if detail_resp.status_code != 200:
        return _fail(f"job detail unavailable: job_id={job_id}, status={detail_resp.status_code}")
    detail = detail_resp.json()
    if detail.get("job_type") != "cover":
        return _fail(f"job is not cover: job_id={job_id}, job_type={detail.get('job_type')}")
    if detail.get("status") not in {"完成", "已完成", "completed"}:
        return _fail(f"job is not completed: job_id={job_id}, status={detail.get('status')}")
    if not detail.get("can_open_studio"):
        return _fail(f"can_open_studio is false: job_id={job_id}, detail={detail}")

    artifact_id = detail.get("final_artifact_id") or detail.get("studio_artifact_id")
    download_url = detail.get("final_artifact_download_url")
    studio_url = detail.get("studio_url")
    if not artifact_id:
        return _fail(f"missing final artifact id: job_id={job_id}")
    if not download_url:
        return _fail(f"missing final artifact download url: job_id={job_id}")
    if not studio_url:
        return _fail(f"missing studio url: job_id={job_id}")

    download_resp = client.get(download_url)
    if download_resp.status_code != 200:
        return _fail(f"download url failed: url={download_url}, status={download_resp.status_code}")
    if len(download_resp.content or b"") <= 0:
        return _fail(f"download content is empty: url={download_url}")

    status_resp = client.get(f"/api/task_status/{job_id}")
    if status_resp.status_code != 200:
        return _fail(f"task_status unavailable: job_id={job_id}, status={status_resp.status_code}")
    status_payload = status_resp.json()
    if not status_payload.get("can_open_studio"):
        return _fail(f"task_status can_open_studio is false: job_id={job_id}")
    if not status_payload.get("final_artifact_download_url"):
        return _fail(f"task_status missing final_artifact_download_url: job_id={job_id}")
    if not status_payload.get("studio_url"):
        return _fail(f"task_status missing studio_url: job_id={job_id}")

    print(
        "[STAGE43A][PASS] studio entry contract ok "
        f"job_id={job_id} artifact_id={artifact_id} studio_url={studio_url}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
