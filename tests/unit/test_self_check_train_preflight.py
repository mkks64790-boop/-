from __future__ import annotations

from backend import self_check


class _Response:
    status_code = 200

    def __init__(self, payload: dict):
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class _Client:
    def get(self, path: str) -> _Response:
        if "duration_seconds=2709.9951" in path:
            return _Response(
                {
                    "ok": False,
                    "recommended_route": "single_long_preprocess",
                    "material_profile": "single_long_candidate",
                    "single_long_eligible": True,
                    "submission_allowed": False,
                    "material_decision": {"submission_allowed": True},
                    "checks": [],
                    "errors": [{"check": "python_import:torch"}],
                }
            )
        if "duration_seconds=932.702025" in path:
            return _Response(
                {
                    "ok": False,
                    "recommended_route": "multi_clean_direct",
                    "material_profile": "single_short_out_of_window",
                    "single_long_eligible": False,
                    "submission_allowed": False,
                    "material_decision": {"submission_allowed": False},
                    "checks": [],
                    "errors": [{"check": "python_import:torch"}],
                }
            )
        return _Response(
            {
                "ok": False,
                "job_type": "train",
                "strategy_key": "single_long_preprocess",
                "recommended_route": "single_long_preprocess",
                "material_profile": "",
                "submission_allowed": False,
                "checks": [],
                "errors": [{"check": "python_import:torch"}],
            }
        )


def test_train_preflight_structure_ignores_external_runtime_failures():
    assert self_check.check_train_preflight_structure(_Client()) is True


def test_train_material_routing_uses_material_decision_not_runtime_submission():
    assert self_check.check_train_material_routing(_Client()) is True
