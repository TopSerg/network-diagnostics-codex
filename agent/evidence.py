"""Sanitized operation journals and evidence-linked reports, local only."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import uuid

from agent_tools.redaction import redact
from .diagnostics import Observation
from .models import Check, Device


class Journal:
    def __init__(self):
        self.operation_id = str(uuid.uuid4())
        self.entries: list[dict] = []

    def record(self, device: Device, check: Check, observation: Observation) -> dict:
        payload = redact({"target": asdict(device), "check": check.value,
                          "status": observation.status.value, "source": asdict(observation.source),
                          "facts": observation.facts})
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
        item = {"evidence_id": f"E{len(self.entries) + 1:03}", "sha256": hashlib.sha256(encoded).hexdigest(),
                **payload}
        self.entries.append(item)
        return item

    def write(self, folder: Path, report: str) -> Path:
        # New operation directory only: never overwrite old evidence/configurations.
        target = folder / self.operation_id
        target.mkdir(parents=True, exist_ok=False)
        (target / "evidence.json").write_text(json.dumps({"operation_id": self.operation_id,
            "entries": self.entries}, ensure_ascii=False, indent=2), encoding="utf8")
        (target / "report.md").write_text(redact(report), encoding="utf8")
        return target
