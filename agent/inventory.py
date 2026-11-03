"""Local-only adapters to the existing DeviceRow and XNet HTML parser."""
from __future__ import annotations

import hashlib
import importlib.util
import ipaddress
import re
from pathlib import Path
from typing import Iterable

from mikenopa_utils.models import DeviceRow
from .models import AccessPoint, Device, Source, TargetError


def from_legacy(row: DeviceRow, source: Source, *, firmware: str | None = None,
                role: str = "unknown") -> Device:
    # Do not retain login, password or unstructured note in model-facing records.
    site = row.marsha.strip().upper()
    address = row.optional_ip or row.ip
    if not site or not address or not row.name:
        raise TargetError("Exact site, device name and address required")
    try:
        address = str(ipaddress.ip_address(address.strip()))
    except ValueError as exc:
        raise TargetError("Inventory address is not an IP address") from exc
    ident = hashlib.sha256(f"{site}|{row.name}|{address}".encode()).hexdigest()[:16]
    return Device(site, ident, row.name, address, row.vendor, row.model, firmware, role, source)


class LocalInventory:
    def __init__(self, devices: Iterable[Device], aps: Iterable[AccessPoint] = ()):
        self.devices = tuple(devices)
        self.aps = tuple(aps)

    @classmethod
    def from_xnet_html(cls, html: str, site_id: str, source: Source) -> "LocalInventory":
        # Pure parser only: no browser client and no credential extraction callbacks.
        # xnet/__init__.py imports browser/client. Load the audited parser file directly
        # with a private module name whose relative import still resolves DeviceRow.
        import mikenopa_utils
        path = Path(mikenopa_utils.__file__).parent / "xnet" / "parsing.py"
        spec = importlib.util.spec_from_file_location("mikenopa_utils._offline_xnet.parsing", path)
        if spec is None or spec.loader is None:
            raise TargetError("Local legacy parser unavailable")
        parser = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(parser)
        return cls(from_legacy(row, source) for row in parser.extract_devices_from_table(html, site_id))

    @classmethod
    def from_excel(cls, path: Path, site_id: str, source: Source) -> "LocalInventory":
        # Use an explicit trusted site binding; never guess a hotel from a filename.
        from openpyxl import load_workbook
        workbook = load_workbook(path, read_only=True, data_only=True)
        try:
            rows = workbook.active.iter_rows(values_only=True)
            headers = next(rows)
            devices = []
            for values in rows:
                data = dict(zip(headers, values))
                if not data.get("ip"):
                    continue
                row = DeviceRow(site_id, ip=data.get("ip"), optional_ip=data.get("ipOptional"),
                                model=data.get("model"), vendor=data.get("vendor"),
                                name=data.get("controlName"))
                devices.append(from_legacy(row, source))
            return cls(devices)
        finally:
            workbook.close()

    def find_device(self, site_id: str, query: str) -> Device:
        if not site_id.strip() or not query.strip():
            raise TargetError("Exact site and device query required")
        matches = [d for d in self.devices if d.site_id == site_id.strip().upper()
                   and query.casefold() in {d.device_id.casefold(), d.name.casefold(), d.address}]
        if len(matches) != 1:
            raise TargetError(f"Expected one exact device; found {len(matches)}")
        return matches[0]

    def find_ap(self, site_id: str, controller_id: str, room: str) -> AccessPoint:
        matches = [a for a in self.aps if a.site_id == site_id.strip().upper()
                   and a.controller_id == controller_id and a.room == room.strip()]
        if len(matches) != 1:
            raise TargetError(f"Expected one exact room/AP binding; found {len(matches)}")
        ap = matches[0]
        if not re.fullmatch(r"[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}", ap.mac):
            raise TargetError("AP MAC invalid")
        return ap
