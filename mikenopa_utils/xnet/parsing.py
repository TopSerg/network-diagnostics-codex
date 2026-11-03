from __future__ import annotations

import re
from typing import Optional

from bs4 import BeautifulSoup

from ..models import DeviceRow


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


def pick_column_indexes(headers: list[str]) -> dict[str, int]:
    """Heuristic mapping of table headers -> column indexes."""
    idx: dict[str, int] = {}
    for i, h in enumerate(headers):
        hl = norm(h)

        if (
            ("optional" in hl and "ip" in hl)
            or ("opt" in hl and "ip" in hl)
            or ("secondary" in hl and "ip" in hl)
            or ("backup" in hl and "ip" in hl)
        ):
            idx["optional_ip"] = i
        elif hl in ("ip",) or ("ip address" in hl) or hl.startswith("ip "):
            idx["ip"] = i
        if ("login" in hl) or (hl in ("user", "username")) or ("user name" in hl):
            idx["login"] = i
        if ("password" in hl) or (hl == "pass"):
            idx["password"] = i
        if ("note" in hl) or ("comment" in hl) or ("remarks" in hl):
            idx["note"] = i
        if (
            hl == "model"
            or hl == "type"
            or hl == "device type"
            or hl == "equipment"
            or hl == "equipment type"
            or "device model" in hl
            or "controller model" in hl
            or "equipment model" in hl
            or "hardware model" in hl
            or "type/model" in hl
        ):
            idx["model"] = i
        if (
            "vendor" in hl
            or "manufacturer" in hl
            or hl == "brand"
            or "device brand" in hl
        ):
            idx["vendor"] = i
        if (
            hl == "name"
            or "device name" in hl
            or "host name" in hl
            or hl == "hostname"
            or "controller name" in hl
        ):
            idx["name"] = i

    return idx


def extract_devices_from_table(page_html: str, marsha: str) -> list[DeviceRow]:
    """Parse every device row from an XNet devices table."""
    soup = BeautifulSoup(page_html, "html.parser")

    table = soup.find("table")
    if not table:
        return [DeviceRow(marsha=marsha, note="No <table> found on page (maybe not logged in / layout changed).")]

    thead = table.find("thead")
    if not thead:
        return [DeviceRow(marsha=marsha, note="No <thead> found in table (layout changed).")]

    header_cells = thead.find_all(["th", "td"])
    headers = [c.get_text(strip=True) for c in header_cells]
    col_idx = pick_column_indexes(headers)

    tbody = table.find("tbody")
    if not tbody:
        return [DeviceRow(marsha=marsha, note="No <tbody> found in table (no rows?).")]

    rows = tbody.find_all("tr")
    if not rows:
        return [DeviceRow(marsha=marsha, note="No rows in table.")]

    result: list[DeviceRow] = []
    for html_row in rows:
        cells = html_row.find_all(["td", "th"])
        values = [c.get_text(" ", strip=True) for c in cells]

        def getv(key: str) -> Optional[str]:
            if key not in col_idx:
                return None
            i = col_idx[key]
            if i < 0 or i >= len(values):
                return None
            value = values[i].strip()
            return value or None

        row = DeviceRow(
            marsha=marsha,
            ip=getv("ip"),
            optional_ip=getv("optional_ip"),
            model=getv("model"),
            vendor=getv("vendor"),
            name=getv("name"),
            login=getv("login"),
            password=getv("password"),
            note=getv("note"),
        )
        if not any((row.ip, row.optional_ip, row.login, row.password, row.model, row.vendor, row.name)):
            row.note = row.note or "Parsed row but could not detect IP/login/password columns by header matching."
        result.append(row)
    return result


def extract_device_from_table(page_html: str, marsha: str) -> DeviceRow:
    """Backward-compatible helper returning the first parsed device."""
    return extract_devices_from_table(page_html, marsha)[0]
