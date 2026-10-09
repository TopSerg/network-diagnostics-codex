# Mikenopa network agent: integration architecture

**Current status:** this public repository contains a vendor diagnostic skill, a Mikenopa triage skill, security instructions and a tested **read-only KB search adapter**. It does not yet have a connected XNet/Daktela tool service, a safe executor for network changes, or a background agent.

```text
Codex (start in C:\gvn\Mikenopa)
  AGENTS.md
  .agents/skills/network-diagnostics/  <- copy complete directory from this repo
  .agents/skills/mikenopa-network/    <- copy from this repo
  agent_tools/kb_search.py            <- copy from this repo
  knowledge/network_agent_kb/         <- PRIVATE ZIP: extract locally, never commit
  mikenopa_utils/, tools/, tests/     <- existing local project
           |
  Proposed private adapter layer:
  inventory lookup -> typed read-only checks -> evidence/report
           |
        XNet / SSH / WLC / Daktela
```

## Engineering contracts

- Codex plans; typed, allowlisted tools execute. A regex-based SSH CLI filter is **not** a security boundary.
- Device-side read-only rights, SSH host-key checks and valid TLS trust are mandatory for unattended inspection.
- Local KB is a dated source, **not a live configuration**. Preference: current approved procedure / device evidence > applicable dated wiki > historic cases.
- Any state-changing operation needs verified target, scoped approval, prechecks, command plan/diff, rollback, operation ID, postchecks and an unknown-state stop.
- Daktela ticket resolution is a separate business operation, only after verified restoration and approved service-desk rules.

## Milestones in the private Mikenopa worktree

1. Merge root AGENTS.md, install full skills and extract the KB locally.
2. Adapt existing `mikenopa_utils` inventory and WLC readers into typed **read-only** tools.
3. Add source/timestamp metadata and distinguish device, AP, room and interface ambiguity.
4. Add offline fixtures, unit tests, op IDs and a sanitized evidence journal.
5. Pilot read-only network diagnostics on approved test equipment.
6. Only then add an approval-gated change executor, agent runner, and monitoring/Telegram triggers.

## Never publish

Knowledge DB/ZIP, `Hotels/`, `Knowledge Base/`, `Ru Dc/`, `logs/`, `.cache/`, browser profiles, MobaXterm exports, device inventory, config backups, credentials, keys or captures. A `.gitignore` does **not** remove secrets inside source files or existing Git history. Review an explicit staging manifest and run a secrets scan before any push.
