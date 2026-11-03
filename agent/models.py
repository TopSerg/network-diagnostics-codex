"""Credential-free tool contracts; source provenance is mandatory."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class TargetError(ValueError):
    pass


class PolicyError(ValueError):
    pass


class Check(str, Enum):
    IDENTITY = "identity"
    LINK = "link"
    VLAN = "vlan"
    MAC = "mac"
    ARP = "arp"
    ROUTE = "route"
    VPN = "vpn"
    WLAN = "wlan"


class Status(str, Enum):
    OBSERVED = "observed"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"
    REFUSED = "refused"


@dataclass(frozen=True)
class Source:
    reference: str
    observed_at: str
    kind: str = "inventory"

    def __post_init__(self):
        if not self.reference or self.kind not in {"inventory", "fixture", "historic", "live"}:
            raise TargetError("Source reference and recognized provenance required")
        try:
            stamp = datetime.fromisoformat(self.observed_at)
        except ValueError as exc:
            raise TargetError("Source timestamp must be ISO-8601") from exc
        if stamp.tzinfo is None:
            raise TargetError("Source timestamp requires timezone")


@dataclass(frozen=True)
class Device:
    site_id: str
    device_id: str
    name: str
    address: str
    vendor: str | None
    model: str | None
    firmware: str | None
    role: str
    source: Source


@dataclass(frozen=True)
class AccessPoint:
    site_id: str
    controller_id: str
    ap_id: str
    name: str
    room: str
    mac: str
    source: Source


@dataclass(frozen=True)
class ReadGrant:
    site_id: str
    device_id: str
    checks: frozenset[Check]


@dataclass(frozen=True)
class Request:
    site_id: str
    device_query: str
    symptom: str
    room: str | None = None
    action: str = "diagnose"
    timeout_sec: float = 5.0
