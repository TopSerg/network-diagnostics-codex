# Huawei VRP read-only diagnostics

## Identification

```text
display version
display device
display clock
```

## Interfaces

```text
display interface brief
display interface <interface>
display counters error interface <interface>
```

## VLAN / MAC

```text
display vlan
display vlan <vlan>
display mac-address
display mac-address <mac>
display mac-address interface <interface>
```

## STP / Eth-Trunk

```text
display stp brief
display stp interface <interface>
display eth-trunk
display eth-trunk <id>
```

## LLDP

```text
display lldp neighbor brief
display lldp neighbor interface <interface>
```

## L3

```text
display arp
display arp | include <ip-or-mac>
display ip interface brief
display ip routing-table
display ip routing-table <destination>
display vrrp brief
```

## Configuration inspection

Use `display current-configuration ...` only for the relevant interface/feature and avoid full dumps that may contain credentials or sensitive topology details.

## Avoid

Do not enter `system-view`, reset protocols/tables, shutdown interfaces, restart boards/processes, or save configuration without authorization.
