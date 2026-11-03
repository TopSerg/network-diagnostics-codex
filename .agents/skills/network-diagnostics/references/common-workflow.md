# Common network troubleshooting workflow

Use this reference to decide what to inspect and in what order.

## Phase A — Define scope

Establish whether the symptom affects:

- one client;
- one access port/AP;
- one VLAN/SSID;
- one switch/site;
- one destination/service;
- all internet/WAN traffic;
- only one direction of a flow.

A single-client problem should not immediately trigger site-wide firewall investigation. A whole-VLAN problem should not begin with replacing the client cable.

## Phase B — Layer 1

Check:

- admin vs operational state;
- link flaps;
- speed/duplex/autonegotiation;
- CRC/FCS/input/output errors;
- drops/discards;
- optics levels where available;
- PoE state for APs/phones/cameras;
- stack member/port ownership.

If L1 is unstable, resolve or explain it before trusting higher-layer symptoms.

## Phase C — Layer 2

Check:

- access/untagged/native VLAN;
- tagged/allowed VLANs on trunks;
- MAC learning and age/source port;
- STP state and blocked links;
- LAG/LACP membership and consistency;
- LLDP/CDP neighbors;
- duplicate MAC or MAC moving/flapping symptoms;
- port-security/802.1X when relevant.

For a known client MAC, use the MAC table as the primary breadcrumb through the switching topology.

## Phase D — Layer 3

Check:

- gateway/SVI/VE/interface state;
- correct subnet/mask;
- ARP/ND resolution;
- route to destination;
- return route to source;
- VRRP/HSRP/active gateway role;
- PBR/route maps when relevant;
- asymmetric routing clues.

Never conclude "routing is fine" from a single forward route; verify the return path when possible.

## Phase E — Services

### DHCP

Check:

- client obtained expected subnet/options;
- relay/helper configuration path;
- pool exhaustion;
- lease/binding visibility;
- DHCP snooping/trust if deployed.

### DNS

Separate name-resolution failure from connectivity failure. If IP connectivity works but FQDN fails, inspect DNS specifically.

### NAT

Verify the source/destination translation that should apply and whether a conflicting rule shadows it.

### VPN

Check control-plane SA/session state first, then data-plane/IPsec counters, routes, NAT exemption, split tunnel and filters.

### Wi-Fi

Correlate SSID → VLAN/tunnel → AP → access switch → gateway. Do not assume association equals internet reachability.

## Phase F — Policy

Inspect relevant ACL/firewall policy for the exact direction and interface. Prefer counters/hit information where available.

Do not paste huge ACLs into the report unless necessary; identify the rule that matches or fails to match the flow.

## Phase G — Validation

Choose tests that mirror the failed flow:

- ping from the correct source/interface;
- ARP presence;
- route lookup;
- firewall packet simulation where supported;
- session/NAT table entry;
- DNS query;
- VPN counter increase;
- MAC learning at the expected port.

Avoid treating generic `ping 8.8.8.8` from the device management plane as proof that a client VLAN works.

## Stop conditions

Stop and ask for explicit authorization before:

- entering persistent configuration mode to fix an issue;
- shutting/no-shutting interfaces as a test;
- clearing broad session/ARP/MAC tables;
- resetting VPN tunnels;
- restarting services/processes;
- reloading/rebooting devices;
- saving configuration.
