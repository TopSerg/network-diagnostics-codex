"""Bounded check registry. Command examples are plans, never executed here."""
from __future__ import annotations

from dataclasses import dataclass
import re

from .models import Check, Device, PolicyError, ReadGrant, Request, Source, Status

PLANS = {
    "connectivity": (Check.LINK, Check.VLAN, Check.MAC, Check.ARP, Check.ROUTE),
    "vlan": (Check.LINK, Check.VLAN, Check.MAC, Check.ARP, Check.ROUTE),
    "vpn": (Check.ROUTE, Check.VPN),
    "wifi": (Check.WLAN, Check.LINK, Check.VLAN, Check.ARP),
}

# Small, reviewed example catalog. Model/firmware families require a future live pilot.
CATALOG = {
    "routeros": {Check.IDENTITY: "/system resource print", Check.LINK: "/interface ethernet print detail",
                 Check.VLAN: "/interface vlan print detail", Check.MAC: "/interface bridge host print",
                 Check.ARP: "/ip arp print", Check.ROUTE: "/ip route print",
                 Check.VPN: "/ip ipsec active-peers print"},
    "icx": {Check.IDENTITY: "show version", Check.LINK: "show interfaces brief",
            Check.VLAN: "show vlan", Check.MAC: "show mac-address", Check.ARP: "show arp",
            Check.ROUTE: "show ip route"},
    "asa": {Check.IDENTITY: "show version", Check.LINK: "show interface ip brief",
            Check.ARP: "show arp", Check.ROUTE: "show route", Check.VPN: "show crypto ipsec sa"},
    "smartzone": {Check.IDENTITY: "show version", Check.WLAN: "show ap all"},
}


def profile(device: Device) -> str:
    if not all((device.vendor, device.model, device.firmware)):
        raise PolicyError("Vendor, model and firmware required; no speculative commands")
    vendor, model, firmware = device.vendor.lower(), device.model.lower(), device.firmware
    if "mikrotik" in vendor and re.search(r"\b(ccr|crs|rb)\w*", model) and re.match(r"^[67]\.\d", firmware):
        return "routeros"
    if "ruckus" in vendor and re.search(r"\bicx\s*\d", model) and re.match(r"^(?:0?[89]\.\d|10\.\d)", firmware):
        return "icx"
    if "cisco" in vendor and "asa" in model and re.match(r"^9\.\d", firmware):
        return "asa"
    if "ruckus" in vendor and re.search(r"sz[- ]?100|smartzone", model) and re.match(r"^[567]\.\d", firmware):
        return "smartzone"
    raise PolicyError("Unsupported model/firmware; consult vendor reference and pilot first")


def select_checks(request: Request) -> tuple[Check, ...]:
    if request.action != "diagnose":
        raise PolicyError("Changes, reboot and ticket closure are unavailable")
    if not 0 < request.timeout_sec <= 15:
        raise PolicyError("Timeout must be bounded to 0..15 seconds")
    if request.symptom not in PLANS:
        raise PolicyError("Unsupported symptom; use connectivity, vlan, vpn or wifi")
    return (Check.IDENTITY,) + PLANS[request.symptom]


def authorize(device: Device, checks: tuple[Check, ...], grant: ReadGrant) -> None:
    if (device.site_id, device.device_id) != (grant.site_id, grant.device_id):
        raise PolicyError("Read grant does not match exact target")
    if any(not isinstance(c, Check) or c not in grant.checks for c in checks):
        raise PolicyError("Read grant does not allow every planned check")
    key = profile(device)
    if any(c not in CATALOG[key] for c in checks):
        raise PolicyError("A planned check is unsupported on this platform; no partial execution")


@dataclass(frozen=True)
class Observation:
    status: Status
    source: Source
    facts: dict


class FixtureDiagnostics:
    """Only installed backend. Fixture values are not live evidence.

    No execute(command), SSH credentials, browser, shell or mutation API exists.
    A missing fixture is UNKNOWN, never an empty successful result.
    """
    def __init__(self, records: dict[tuple[str, Check], Observation]):
        self.records = records

    def inspect(self, device: Device, check: Check, timeout_sec: float) -> Observation:
        if not isinstance(check, Check):
            raise PolicyError("Only typed registered checks accepted")
        if not 0 < timeout_sec <= 15:
            raise PolicyError("Unbounded inspection refused")
        item = self.records.get((device.device_id, check))
        if item is None:
            return Observation(Status.UNKNOWN, Source("fixture:missing", device.source.observed_at, "fixture"),
                               {"reason": "No fixture supplied; live connector unavailable"})
        if item.source.kind != "fixture":
            raise PolicyError("Fixture backend cannot assert live provenance")
        return item
