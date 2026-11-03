"""Offline CLI. Never connects to devices or corporate services."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from agent_tools.redaction import redact
from .demo import make_demo
from .diagnostics import FixtureDiagnostics, Observation
from .inventory import LocalInventory
from .knowledge import LocalKnowledge
from .models import AccessPoint, Check, Device, PolicyError, ReadGrant, Request, Source, Status, TargetError
from .service import NetworkAgent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--demo", action="store_true", help="Synthetic offline diagnostic run")
    mode.add_argument("--case", type=Path, help="Explicit offline JSON fixture case")
    mode.add_argument("--inventory-xlsx", type=Path, help="Local inventory lookup only")
    mode.add_argument("--inventory-html", type=Path, help="Saved XNet HTML lookup only")
    parser.add_argument("--site")
    parser.add_argument("--device")
    parser.add_argument("--observed-at", help="Inventory snapshot ISO-8601 time with timezone")
    parser.add_argument("--kb-db", help="Optional explicit private knowledge.db")
    parser.add_argument("--with-kb", action="store_true", help="Attach local KB references")
    parser.add_argument("--output", type=Path, default=Path("agent_reports"))
    args = parser.parse_args(argv)
    try:
        if args.inventory_xlsx or args.inventory_html:
            if not all((args.site, args.device, args.observed_at)):
                raise TargetError("Local lookup requires --site, --device and --observed-at")
            path = args.inventory_xlsx or args.inventory_html
            source = Source(str(path), args.observed_at)
            if args.inventory_xlsx:
                inventory = LocalInventory.from_excel(path, args.site, source)
            else:
                inventory = LocalInventory.from_xnet_html(path.read_text(encoding="utf8"), args.site, source)
            device = inventory.find_device(args.site, args.device)
            print(json.dumps(redact(asdict(device)), ensure_ascii=False, indent=2))
            return 0
        if args.demo:
            inventory, transport, request, grant = make_demo()
        else:
            case = json.loads(args.case.read_text(encoding="utf8"))
            if case.get("mode") != "fixture":
                raise PolicyError("Only explicit fixture cases accepted; live mode unavailable")
            devices = [Device(**{**d, "source": Source(**d["source"])}) for d in case["devices"]]
            aps = [AccessPoint(**{**a, "source": Source(**a["source"])}) for a in case.get("aps", [])]
            inventory = LocalInventory(devices, aps)
            records = {}
            for row in case.get("observations", []):
                key = (row["device_id"], Check(row["check"]))
                if key in records:
                    raise TargetError("Duplicate observation identity")
                records[key] = Observation(Status(row["status"]), Source(**row["source"]), row["facts"])
            transport = FixtureDiagnostics(records)
            request = Request(**case["request"])
            rights = case["grant"]
            grant = ReadGrant(rights["site_id"], rights["device_id"], frozenset(Check(c) for c in rights["checks"]))
        knowledge = LocalKnowledge(args.kb_db) if args.with_kb or args.kb_db else None
        journal, report = NetworkAgent(inventory, transport, knowledge).investigate(request, grant)
        path = journal.write(args.output, report)
        print(json.dumps({"mode": "offline-fixture", "operation_id": journal.operation_id,
                          "evidence_count": len(journal.entries), "report_directory": str(path)}, indent=2))
        return 0
    except Exception as exc:
        # No raw exception text: paths, HTML and credential values can appear there.
        print(json.dumps({"status": "refused", "error_type": type(exc).__name__,
                          "notice": "Invalid/ambiguous case, unsupported metadata or missing read rights; no network access."}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
