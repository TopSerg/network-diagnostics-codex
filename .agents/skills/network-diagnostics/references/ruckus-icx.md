# Ruckus / Brocade ICX read-only diagnostics

ICX/FastIron syntax differs somewhat across generations and releases. If a command is rejected, use `?`/CLI help or a close documented variant rather than guessing a mutating command.

## Identification / stack

```text
show version
show chassis
show stack
show stack detail
show system
```

## Interfaces

```text
show interfaces brief
show interfaces ethernet <port>
show interfaces ethernet <port> statistics
```

## VLAN / MAC

```text
show vlan
show vlan <vlan>
show mac-address
show mac-address <mac>
show mac-address ethernet <port>
```

On some releases MAC syntax/format differs; search by normalized MAC variants if needed.

## STP

```text
show span
show span detail
show span vlan <vlan>
```

MSTP/PVST-specific commands can vary by release.

## LAG / LACP

```text
show lag
show lag brief
show lacp
```

## LLDP

```text
show lldp neighbors
show lldp neighbors detail
```

## L3

```text
show arp
show ip route
show ip interface
show ip interface brief
```

## Typical client trace

1. `show mac-address <mac>`
2. Inspect learned port and VLAN.
3. `show interfaces ethernet <port>`
4. Check VLAN membership.
5. If the port is an uplink, inspect LLDP/LAG and follow the neighbor.
6. At the gateway, correlate client IP with ARP and route/policy state.

## Avoid

Do not clear MAC/ARP tables, bounce ports, manipulate stack roles, change STP, or write memory without explicit approval.
