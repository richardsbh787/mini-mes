from typing import Any, Dict, List
from app.repos.model_routing_repo import ModelRoutingRepo

class ModelRoutingService:
    def __init__(self):
        self.repo = ModelRoutingRepo()

    @staticmethod
    def _validate_steps(steps: List[Dict[str, Any]]) -> None:
        if not steps:
            raise ValueError("steps cannot be empty")

        seqs = [s.get("seq") for s in steps]
        if any((x is None) for x in seqs):
            raise ValueError("each step must have seq")
        if len(set(seqs)) != len(seqs):
            raise ValueError("seq must be unique")

        # enforce ascending order (user can send unordered; we sort later)
        # stage/process required
        for s in steps:
            if not str(s.get("stage") or "").strip():
                raise ValueError("each step must have stage")
            if not str(s.get("process") or "").strip():
                raise ValueError("each step must have process")

    def upsert_active(self, org_id: str, model_code: str, steps: List[Dict[str, Any]], version: int = 1) -> Dict[str, Any]:
        steps_sorted = sorted(steps, key=lambda x: x["seq"])
        self._validate_steps(steps_sorted)

        # rule: only one active per org+model => deactivate old, then insert new
        self.repo.deactivate_active(org_id, model_code)

        payload = {
            "org_id": org_id,
            "model_code": model_code,
            "version": version,
            "is_active": True,
            "steps": steps_sorted,
        }
        return self.repo.insert(payload)

    def get_active(self, org_id: str, model_code: str) -> Dict[str, Any]:
        row = self.repo.get_active(org_id, model_code)
        if not row:
            raise ValueError("active routing not found")
        return row