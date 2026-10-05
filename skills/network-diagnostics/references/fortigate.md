# FortiGate read-only diagnostics

FortiOS has powerful `diagnose` commands; some can alter state. Use only known read-only forms and keep output bounded.

## Identification / HA

```text
get system status
get system ha status
get system performance status
```

## Interfaces

```text
get system interface physical
get system interface
```

For a specific NIC, use platform-appropriate read-only `diagnose hardware deviceinfo nic <interface>` only when needed.

## Routing / ARP

```text
get router info routing-table all
get router info routing-table details <destination>
diagnose ip arp list
```

## Sessions / policy correlation

```text
diagnose sys session list
```

Large session tables can be expensive and noisy. Prefer FortiOS session filters before listing when investigating a specific host/flow.

## VPN

```text
get vpn ipsec tunnel summary
diagnose vpn tunnel list
get vpn ssl monitor
```

Command availability varies by FortiOS release and VPN type.

## Packet flow / sniffer

A packet sniffer can be useful but must be narrowly filtered and count-limited. Never run an unbounded capture on a busy firewall.

Flow debug must be carefully filtered, short-lived, and disabled afterward. Do not use it when routing/session/policy evidence is already sufficient.

## Configuration inspection

`show` / `show full-configuration` are read-only but may expose secrets and generate huge output. Inspect only the relevant policy/object/interface sections.

## Avoid

Do not clear sessions, restart daemons, reset tunnels, change HA state, modify policies, or execute broad debug commands without explicit authorization.
