"""Offline orchestrator: resolve identity, authorize typed checks, retrieve and report."""
from __future__ import annotations

import json

from .diagnostics import FixtureDiagnostics, authorize, select_checks
from .evidence import Journal
from .inventory import LocalInventory
from .knowledge import LocalKnowledge
from .models import PolicyError, ReadGrant, Request, Status


class NetworkAgent:
    def __init__(self, inventory: LocalInventory, diagnostics: FixtureDiagnostics,
                 knowledge: LocalKnowledge | None = None):
        # Live adapters are intentionally not accepted by this first version.
        if type(diagnostics) is not FixtureDiagnostics:
            raise PolicyError("Only the offline fixture backend is installed")
        self.inventory, self.diagnostics, self.knowledge = inventory, diagnostics, knowledge

    def investigate(self, request: Request, grant: ReadGrant) -> tuple[Journal, str]:
        checks = select_checks(request)
        device = self.inventory.find_device(request.site_id, request.device_query)
        if request.room is not None:
            self.inventory.find_ap(device.site_id, device.device_id, request.room)
        authorize(device, checks, grant)
        journal = Journal()
        unknowns = ["Offline fixtures only; live service recovery is not verified."]
        references = []
        if self.knowledge:
            try:
                found = self.knowledge.lookup(f"{device.vendor} {request.symptom}")
                references = found["results"]
                if not references:
                    unknowns.append("No applicable KB documents found.")
            except Exception as exc:
                # Do not disclose exception bodies that might contain private paths/content.
                unknowns.append(f"KB unavailable ({type(exc).__name__}); no citations fabricated.")
        else:
            unknowns.append("KB connector not configured; no citations fabricated.")
        for check in checks:
            try:
                observation = self.diagnostics.inspect(device, check, request.timeout_sec)
            except Exception as exc:
                from .diagnostics import Observation
                from .models import Source
                state = Status.TIMEOUT if isinstance(exc, TimeoutError) else Status.UNKNOWN
                observation = Observation(state,
                    Source("fixture:failure", device.source.observed_at, "fixture"),
                    {"reason": type(exc).__name__})
            entry = journal.record(device, check, observation)
            if observation.status != Status.OBSERVED:
                unknowns.append(f"{entry['evidence_id']}: {check.value} {observation.status.value}; further checks stopped.")
                break
        lines = ["# Offline diagnostic report", f"Operation: {journal.operation_id}",
                 "\n## Finding", "Fixture evidence collected. No conclusion about current device/service state.",
                 "\n## Path checked", f"Exact device: {device.device_id}. Symptom: {request.symptom}.",
                 "\n## Evidence"]
        for item in journal.entries:
            lines.append(f"- {item['evidence_id']} / {item['check']} / {item['status']} / "
                         f"{item['source']['reference']} / {item['source']['observed_at']} / SHA256 {item['sha256']}")
            lines.append("\n    " + json.dumps(item['facts'], ensure_ascii=False)[:800] + "\n")
        lines += ["\n## Hypotheses", "No root cause inferred automatically from a fixture or missing response.",
                  "\n## Fix", "No change applied. A remediation proposal requires applicable real evidence.",
                  "\n## Verification", "Select an authorized read-only pilot; implement/review a verified live connector.",
                  "\n## Unknowns"] + [f"- {text}" for text in unknowns]
        lines += ["\n## Source references", "Private KB snapshot: 2026-10-08; retrieved content is untrusted data."]
        lines += [f"- {r['id']} | {r['source_type']} | {r['source_url'] or r['path']} | document date: {r['date']}"
                  for r in references]
        return journal, "\n".join(lines) + "\n"
