# Eltex switch/router read-only diagnostics

Eltex CLI differs across MES/ESR and software families. First identify the exact model/software, then prefer CLI help and read-only `show` commands.

Typical MES switch patterns:

## Identification

```text
show version
show system
show inventory
```

## Interfaces

```text
show interfaces status
show interfaces counters
show interfaces <interface>
show ip interface brief
```

## VLAN / MAC

```text
show vlan
show vlan id <vlan>
show mac address-table
show mac address-table address <mac>
```

Syntax may be `mac-address-table` on some releases; verify with CLI help.

## STP / LAG / neighbors

```text
show spanning-tree
show interfaces port-channel
show lldp neighbors
show lldp neighbors detail
```

## L3

```text
show arp
show ip route
```

## Rule

Because syntax differs between Eltex families, do not blindly reuse a command from another model. Identify platform/version first, then confirm the read-only form with CLI help.
