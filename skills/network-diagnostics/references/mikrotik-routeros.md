# MikroTik RouterOS read-only diagnostics

Commands below are intended for RouterOS terminal. Prefer `print`, `monitor ... once`, and read-only inspection.

## Identification

```text
/system identity print
/system resource print
/system package print
```

## Interfaces / bridge

```text
/interface print detail
/interface ethernet print detail
/interface bridge print detail
/interface bridge port print detail
/interface bridge host print
```

For live interface state, use a bounded `monitor ... once` form when appropriate.

## VLAN

Depending on the design:

```text
/interface bridge vlan print detail
/interface vlan print detail
```

## L3

```text
/ip address print detail
/ip arp print detail
/ip route print detail
```

On newer RouterOS versions the routing view may differ; use the platform's read-only print form.

## DHCP / DNS

```text
/ip dhcp-server lease print detail
/ip dhcp-client print detail
/ip dns print
```

## Firewall / NAT

```text
/ip firewall filter print stats detail
/ip firewall nat print stats detail
/ip firewall mangle print stats detail
```

Use counters to correlate the exact flow.

## Avoid

Do not use `set`, `add`, `remove`, `disable`, `enable`, `reset-*`, `/system reboot`, or table flush operations without explicit approval.
