# njagents

Claude plugins for engineering and delivery operations. Each plugin packages the
skills, agents, commands and configuration needed to run a repeatable workflow in
Claude Cowork.

Author: Navjyot Nishant

## Plugin index

| Plugin | What it includes | Status |
| --- | --- | --- |
| `operations/bug-triage-agent` | Disposition gate, release correlation, workaround discovery and priority scoring, with a shared rubric and per-team configuration | Draft, not yet exercised |

### bug-triage-agent

Triage bug tickets with judgment, not just severity. The agent classifies a ticket as
defect, expected behaviour, config or data issue, duplicate, or voice-of-customer
**before** any priority is assigned, identifies which release touched the affected
area over a full release-cycle lookback, and surfaces a workaround the customer can
use today.

One shared rubric governs every team; a team owns exactly one configuration file. See
`operations/bug-triage-agent/README.md` for setup and
`operations/bug-triage-agent/STATUS.md` for an honest account of what is built, what
is written but unexercised, and what does not exist yet.

## Repository structure

```
njagents/
├── README.md
├── LICENSE
├── .gitignore
├── package-plugin.sh              packaging script
├── .claude-plugin/
│   └── marketplace.json           marketplace manifest
├── .specify/                      Spec Kit artifacts (repo root, never inside a plugin)
├── .claude/skills/                Spec Kit skills
└── operations/
    └── bug-triage-agent/
        ├── README.md
        ├── STATUS.md
        ├── .claude-plugin/plugin.json
        ├── .mcp.json
        ├── skills/                SHARED judgment
        ├── reference/             SHARED rubric, taxonomy, templates
        ├── agents/                one enrichment subagent per source
        ├── commands/
        ├── teams/                 PER TEAM: the only files a team edits
        ├── fixtures/              recorded envelopes, contract-validated
        ├── scripts/validate_config.py
        └── logs/
```

Spec Kit lives at the repository root, not inside a plugin. A plugin ZIP must never
contain `.specify/` or `.claude/`; `package-plugin.sh` strips them defensively.

## Installing

### Via marketplace

1. Claude Cowork, Customize, Browse plugins, Add marketplace
2. Enter `github.com/navjyotnishant/njagents`
3. Sync, then install

### Via ZIP

```bash
./package-plugin.sh operations/bug-triage-agent
```

The script runs the plugin's own validator first and refuses to package a plugin that
fails it. Upload the resulting ZIP via Customize, Browse plugins, Upload custom plugin.

## Spec-driven development

This repository uses [Spec Kit](https://github.com/github/spec-kit). Run the skills
from the repository root:

```
/speckit-constitution   once per repository
/speckit-specify        per feature
/speckit-plan
/speckit-tasks
/speckit-implement
/speckit-converge
```

## License

Apache-2.0. See LICENSE.
