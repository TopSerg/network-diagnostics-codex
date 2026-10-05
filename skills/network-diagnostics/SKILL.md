---
name: network-diagnostics
description: Diagnose switches, routers, firewalls, gateways, VPNs, VLANs, DHCP, Wi-Fi paths, ACLs, routing, MAC/ARP issues, and general connectivity through safe read-only SSH troubleshooting. Use when a user asks Codex to connect to network equipment, trace a client or MAC address, inspect VLANs/interfaces/uplinks, investigate loss of connectivity, or collect evidence from Cisco, Ruckus, Aruba, Fortinet, MikroTik, Huawei, Ruijie, or Eltex devices.
---

# Network diagnostics

Use this skill for infrastructure troubleshooting where the goal is to understand a fault from device state and command output.

Follow the repository `AGENTS.md` safety contract at all times.

## 1. Convert the request into a diagnostic target

Extract whatever is already known:

- site/property/customer;
- symptom;
- affected client/device;
- MAC address;
- IP address/subnet;
- VLAN/SSID;
- relevant hostname or management address;
- source and destination for a failed flow;
- expected behavior;
- observed behavior.

Do not stop to ask for data that can be discovered safely from accessible infrastructure.

If multiple interpretations remain, begin with the least invasive checks that distinguish between them.

## 2. Identify the first network device

Before deep troubleshooting, determine as much as possible about:

- hostname;
- vendor;
- platform/model;
- OS/software version;
- uptime;
- stack/HA role;
- management path;
- device role (access, distribution, core, firewall, WLC, gateway, etc.).

Then read only the relevant vendor reference from `references/`.

Do not load every vendor reference unless the path actually contains multiple vendors.

## 3. Work from lower layers upward

Use the detailed procedure in `references/common-workflow.md`.

Default order:

1. L1 — link/admin/oper state, speed/duplex, optics/PoE/errors.
2. L2 — VLAN membership, MAC learning, STP, LAG/LACP, neighbors.
3. L3 — ARP/ND, SVI/VE/interface addressing, routes, FHRP.
4. Services — DHCP, DNS, NAT, WLAN/controller state, VPN.
5. Policy — ACL/firewall/security policy/PBR.
6. End-to-end validation.

Skip irrelevant stages when strong evidence already narrows the problem, but never jump to configuration changes merely because one hypothesis looks plausible.

## 4. Trace the traffic path

For client/VLAN/connectivity issues, do not assume the first device is the fault domain.

Follow evidence across the path when possible:

```text
client
→ AP / access port
→ access switch
→ distribution/core
→ gateway/firewall
→ upstream/WAN/service
```

Useful pivots include:

- MAC address → learned interface/VLAN;
- interface → LLDP/CDP neighbor/uplink;
- client IP → ARP entry;
- VLAN → gateway/SVI/VE;
- destination IP → route/next hop;
- flow → ACL/firewall/NAT/VPN state.

At each hop, record the observation that justifies moving to the next hop.

## 5. Prefer read-only commands

Use `show`, `display`, `get`, bounded diagnostic views, and other non-mutating equivalents from the vendor references.

Session-only terminal formatting commands may be used when required to prevent pagination, but do not enter configuration mode for convenience.

Avoid unrestricted debug commands. If a debug/capture is genuinely necessary:

- explain why;
- scope it to the smallest interface/host/protocol possible;
- time-bound it;
- ensure it is stopped/disabled afterward;
- never leave a persistent debug enabled.

## 6. Handle configuration changes separately

If diagnostics prove that a configuration change is required, stop the diagnostic phase and present:

- root cause;
- exact proposed change;
- expected effect;
- blast radius;
- rollback;
- verification procedure.

Do not apply the change unless the user explicitly authorizes it.

A request such as "diagnose", "check", "find the issue", or "look at the switch" is not authorization to modify configuration.

## 7. Evidence quality

Separate facts from hypotheses.

Good:

```text
MAC 3c52.8237.6dac is learned dynamically on VLAN 215 via 1/1/18.
Port 1/1/18 is untagged in VLAN 210.
This mismatch explains why the client cannot reach the VLAN 215 gateway.
```

Bad:

```text
Probably a VLAN problem. Change the port to VLAN 215 and see.
```

Do not claim root cause when the evidence only establishes correlation.

## 8. Final response

Use `assets/report-template.md` as the shape for substantial incidents.

Minimum sections:

### Finding
Strongest supported conclusion.

### Evidence
Important outputs/observations, summarized rather than dumping entire device configurations.

### Path checked
Devices, interfaces, VLANs and services examined.

### Fix
Recommended remediation, explicitly marked as proposed if not authorized/applied.

### Verification
Exact checks that prove recovery.

### Unknowns
Only unresolved facts that matter.
