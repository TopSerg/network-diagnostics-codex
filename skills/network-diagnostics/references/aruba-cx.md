# Aruba AOS-CX read-only diagnostics

## Identification

```text
show version
show system
show inventory
show clock
```

## Interfaces

```text
show interface brief
show interface <interface>
show interface <interface> statistics
show interface transceiver <interface>
```

## VLAN / MAC

```text
show vlan
show vlan <vlan>
show mac-address-table
show mac-address-table address <mac>
show mac-address-table port <interface>
```

## STP / LAG

```text
show spanning-tree
show spanning-tree vlan <vlan>
show lacp interfaces
show lacp aggregates
```

## Neighbors

```text
show lldp neighbor-info
show lldp neighbor-info <interface>
```

## L3

```text
show arp
show ip route
show ip route <destination>
show vrrp
```

Command detail can vary by AOS-CX version. Prefer CLI help for a read-only variant rather than entering configuration mode.

## Avoid

Do not bounce interfaces, clear tables, modify VSX/VRRP/STP/LAG state, or save configuration without authorization.
