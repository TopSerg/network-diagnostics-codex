# Cisco ASA read-only diagnostics

Syntax varies by ASA release/context. Prefer the narrowest command that answers the question.

## Identification / HA

```text
show hostname
show version
show failover
show inventory
show clock
```

## Interfaces

```text
show interface ip brief
show interface <nameif>
show running-config interface <physical-or-subinterface>
```

Reading running configuration is read-only, but avoid dumping the full config unless necessary because it may contain sensitive material.

## Routing / ARP

```text
show route
show route <destination>
show arp
show arp | include <ip-or-mac>
```

## ACL / policy

```text
show access-group
show access-list
show access-list <acl-name>
```

Use hit counts and the interface/direction binding to determine whether a rule is relevant.

## NAT / connections

```text
show nat
show xlate
show conn
show local-host <ip>
```

Filter when possible instead of dumping large tables.

## VPN

```text
show vpn-sessiondb summary
show vpn-sessiondb anyconnect
show vpn-sessiondb detail anyconnect
show crypto ikev2 sa
show crypto ipsec sa
show running-config tunnel-group
show running-config group-policy
```

Do not expose PSKs/secrets if output contains sensitive configuration.

## Packet simulation

`packet-tracer` is non-persistent and useful for a precisely defined flow.

Example shape:

```text
packet-tracer input <inside-nameif> tcp <src-ip> <src-port> <dst-ip> <dst-port> detailed
```

Use realistic source/destination/interfaces. Interpret every phase; do not report only the final ALLOW/DROP line.

## Avoid unless explicitly justified

- broad `debug`;
- `clear conn` / `clear xlate` / `clear crypto ...`;
- failover forcing;
- interface shutdown;
- configuration changes;
- `write memory` / configuration save.
