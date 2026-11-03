from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class DeviceRow:
    marsha: str
    ip: Optional[str] = None
    optional_ip: Optional[str] = None
    model: Optional[str] = None
    vendor: Optional[str] = None
    name: Optional[str] = None
    login: Optional[str] = None
    password: Optional[str] = None
    note: Optional[str] = None
