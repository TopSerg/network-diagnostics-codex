# Network diagnostic report template

## Finding

State the strongest conclusion supported by evidence.

## Evidence

- Device / command / observation.
- Device / command / observation.
- Explain why each item matters.

## Path checked

```text
client → access/AP → distribution/core → gateway/firewall → destination
```

Mark each checked hop and the relevant interface/VLAN when known.

## Fix

Describe the smallest remediation that addresses the root cause.

If configuration has not been authorized, prefix commands with **Proposed change — not applied**.

Include rollback for any configuration change.

## Verification

List exact post-fix tests, ideally mirroring the original failure.

## Unknowns

List only unresolved facts that materially affect confidence or the next action.
