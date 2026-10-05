# Network Engineering Agent Rules

This repository is intended for Codex-assisted network diagnostics.

## Safety contract

1. Start with read-only diagnostics.
2. Never change persistent device configuration unless the user explicitly asks for a change.
3. Never save configuration automatically.
4. Never reboot, reload, erase, format, reset, upgrade, downgrade, or factory-reset a device without explicit approval.
5. Never disable security controls, AAA, logging, spanning tree, routing protocols, firewall rules, VPN policy, or interfaces merely to "test" a theory.
6. Do not run destructive or high-impact commands such as `reload`, `reboot`, `write erase`, `erase startup-config`, `format`, `factory-reset`, `delete`, or equivalents.
7. Treat packet captures, debug commands, table dumps, and session dumps as potentially expensive. Scope and time-bound them.
8. Do not place passwords, private keys, API tokens, SNMP communities, or enable secrets in this repository, prompts, logs, or generated reports.
9. Prefer SSH keys via `ssh-agent` and aliases in `~/.ssh/config`. Respect normal host-key verification.
10. If a required diagnostic action would alter state, stop and explain why approval is needed.

## Default troubleshooting method

Work from evidence, not trial-and-error changes:

1. Define the symptom and scope.
2. Identify the device, vendor, model, OS/version, hostname, and role.
3. Check Layer 1.
4. Check Layer 2: VLAN, MAC learning, STP, LAG/LACP, LLDP/CDP.
5. Check Layer 3: ARP/ND, SVI/VE/VLAN interface, routing, VRRP/HSRP where relevant.
6. Check services: DHCP, DNS, NAT, VPN, captive portal, WLAN/controller state, etc.
7. Check policy: ACLs, firewall policy, security profiles, route maps/PBR.
8. Trace the traffic path across devices when the problem is not local to one box.
9. Correlate findings before proposing a fix.

Do not ask the user for information that can be safely discovered from the infrastructure already available to you.

## Configuration changes

When a change is requested:

1. Show the exact proposed commands first.
2. Explain the expected effect and blast radius.
3. Provide rollback commands or a rollback method.
4. Call out management-plane lockout risk.
5. Apply only the requested change; do not bundle opportunistic cleanup.
6. Verify service after the change.
7. Do not save the running configuration unless the user explicitly requests it.

## Reporting format

For completed diagnostics, report:

### Finding
The most likely fault or the strongest current conclusion.

### Evidence
The important command outputs and observations that support the conclusion.

### Path checked
The devices/interfaces/VLANs or service chain that were examined.

### Fix
The recommended remediation. If it changes configuration, clearly mark it as proposed unless already approved.

### Verification
The commands/tests to confirm the problem is fixed.

### Unknowns
Only unresolved facts that materially affect confidence or next steps.

## Skill usage

For SSH/network troubleshooting, use the `network-diagnostics` skill in `skills/network-diagnostics/` and load only the relevant vendor/reference files instead of reading every reference by default.
