# Cisco IOS / IOS-XE / Catalyst read-only diagnostics

Command availability varies by platform and release.

## Identification

```text
show hostname
show version
show inventory
show switch
show clock
```

## Interfaces

```text
show interfaces status
show ip interface brief
show interfaces <interface>
show interfaces counters errors
show interfaces switchport
show interfaces <interface> switchport
```

## VLAN / MAC

```text
show vlan brief
show vlan id <vlan>
show mac address-table
show mac address-table address <mac>
show mac address-table interface <interface>
```

Some older releases use `show mac-address-table`.

## STP / EtherChannel

```text
show spanning-tree vlan <vlan>
show spanning-tree interface <interface> detail
show etherchannel summary
show lacp neighbor
```

## Neighbors

```text
show lldp neighbors
show lldp neighbors detail
show cdp neighbors
show cdp neighbors detail
```

## L3

```text
show arp
show ip arp <ip>
show ip route
show ip route <destination>
show standby brief
show vrrp brief
```

## DHCP / security features

```text
show ip dhcp binding
show ip dhcp snooping
show ip dhcp snooping binding
show authentication sessions
show port-security interface <interface>
```

Use only commands supported by the specific platform.

## Avoid

Do not use shutdown/no shutdown, clear counters/tables, reload, config changes, or saves as diagnostic shortcuts without explicit authorization.
