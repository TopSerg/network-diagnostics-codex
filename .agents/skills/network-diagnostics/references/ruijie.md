# Ruijie / Reyee enterprise CLI read-only diagnostics

Ruijie command sets vary considerably by product line and software release. Use CLI help to confirm read-only syntax when necessary.

Common enterprise switch patterns include:

## Identification

```text
show version
show device
show clock
```

## Interfaces

```text
show interfaces status
show interfaces <interface>
show ip interface brief
```

## VLAN / MAC

```text
show vlan
show vlan id <vlan>
show mac-address-table
show mac-address-table address <mac>
```

Some releases use spelling closer to Cisco IOS, others differ.

## STP / aggregation / neighbors

```text
show spanning-tree
show aggregatePort summary
show lldp neighbors
show lldp neighbors detail
```

Validate exact aggregation command on the target OS before use.

## L3

```text
show arp
show ip route
```

## Rule

If exact syntax is uncertain, use `show ?` or contextual help and select a clearly read-only inspection command. Never guess by entering configuration mode.
