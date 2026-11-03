"""Synthetic fixture: documentation addresses and invented identities only."""
from .diagnostics import FixtureDiagnostics, Observation, select_checks
from .inventory import LocalInventory
from .models import Check, Device, ReadGrant, Request, Source, Status


def make_demo():
    source = Source("fixture:demo", "2026-10-09T09:00:00+03:00", "fixture")
    device = Device("DEMO", "demo-gateway", "demo-gateway", "192.0.2.10", "MikroTik",
                    "CCR1009", "7.20", "gateway", source)
    request = Request("DEMO", "demo-gateway", "connectivity")
    states = {
        Check.IDENTITY: {"platform": "synthetic CCR1009", "firmware": "7.20"},
        Check.LINK: {"interface": "ether1", "oper_state": "up"},
        Check.VLAN: {"vlan": 215, "interface": "vlan215"},
        Check.MAC: {"mac": "02:00:00:00:00:01", "vlan": 215},
        Check.ARP: {"address": "192.0.2.20", "state": "reachable"},
        Check.ROUTE: {"destination": "198.51.100.0/24", "active": True},
    }
    transport = FixtureDiagnostics({(device.device_id, check): Observation(Status.OBSERVED, source, facts)
                                    for check, facts in states.items()})
    grant = ReadGrant(device.site_id, device.device_id, frozenset(select_checks(request)))
    return LocalInventory([device]), transport, request, grant
