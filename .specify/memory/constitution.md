# njagents Constitution

Principles governing every plugin in this repository. A plugin that violates one of
these is not ready to publish, however well it works in a demo.

**Version**: 1.0.0 | **Ratified**: 2026-09-21 | **Last amended**: 2026-09-21

## Core Principles

### I. Organized by type of work, not by client or technology

Top-level directories name the **kind of work** a plugin serves, so anyone can find
the right plugin by asking what job they are doing:

| Directory | Work it serves |
| --- | --- |
| `development/` | Writing, reviewing and shipping code |
| `operations/` | Triage, incidents, releases, running systems |
| `qa/` | Test strategy, coverage, defect analysis |
| `business-analyst/` | Requirements, process mapping, stakeholder analysis |
| `release/` | Release planning, notes, change management |

Add a category when a genuinely new kind of work appears, not for a new client, a new
vendor, or a new technology. A plugin named after a customer or a product dates
immediately and cannot be reused; a plugin named after the work outlives both.

Nothing inside a plugin's shared layer may name a product, a schema, a repository or a
customer. Domain detail lives in per-team configuration. This is what lets one plugin
serve two teams at different quality bars.

### II. Shared judgment, thin configuration

Within a plugin, the reasoning is shared and versioned; the wiring is per team and
small. A team owns exactly one configuration file and never a copy of the rubric,
taxonomy or output format.

Forking the shared layer is the failure mode this repository exists to prevent. When
two teams hold different copies of a rubric, they grade the same input differently and
neither is wrong by its own configuration. Enforce the boundary in continuous
integration, not by convention.

### III. Absent capability lowers confidence, never raises severity

When a data source is switched off, unconfigured or failing, the agent reports which
questions it could not answer and lowers its stated confidence. It does not escalate,
round up, or otherwise penalise the user for incomplete setup.

Escalation must be tied to evidence in the input, never to the absence of a connector.
A tool that punishes partial adoption does not get adopted.

### IV. Nothing is written without explicit confirmation

Agents in this repository read. Any write to an external system — a comment, a field,
a ticket, a message — requires per-action confirmation from the person. Read-only
guarantees are enforced by tool allowlists and query validation where the host
supports them, and stated plainly where it does not.

### V. Claims require evidence, and execution is the only evidence

Most of what these plugins contain is instructions an agent follows at runtime, not
code that executes deterministically. Writing an instruction is not knowing it works.

A component that has never been run is documented as unproven, whatever its apparent
completeness. Every plugin carries a `STATUS.md` separating what is verified, what is
written but unexercised, and what does not exist. Expected-output files state whether
they are recorded transcripts or predictions.

## Portability

Plugins target the portable [Agent Plugins](https://agent-plugins.org) standard and
carry client manifests alongside it:

| Manifest | Client | Components loaded |
| --- | --- | --- |
| `plugin.json` at root | Codex, ChatGPT, Copilot, VS Code, Kiro and other conformant clients | Skills, MCP servers |
| `.claude-plugin/plugin.json` | Claude Code and Cowork | Skills, agents, commands, MCP, hooks |
| `.cursor-plugin/plugin.json` | Cursor | Skills, agents, commands, MCP, rules, hooks |

The manifests must agree on name, version and description. Skills are the portable
core and exist in one copy. Where a client cannot load a component, the degradation is
documented in that plugin's `STATUS.md` rather than discovered by a user.

Spec Kit artifacts live at the repository root and never inside a plugin directory. A
plugin archive containing `.specify/` or `.claude/skills/` is a packaging defect.

## Quality gates

- A plugin that ships a validator must pass it before packaging. The packaging script
  enforces this.
- Validation distinguishes errors from unconfigured placeholders: the full suite stays
  green so it can gate continuous integration, while a named configuration refuses to
  certify on an unfilled value.
- No credentials in the repository, ever. Credential-shaped keys fail validation.
- Fixtures are recordings of a live contract, validated against the same shape the live
  adapter produces. A fixture that needs a special case in the validator means demo and
  production have quietly diverged.

## Governance

This constitution takes precedence over convenience. Amendments are made in a commit
that states what changed and why, with the version bumped: major for a removed or
redefined principle, minor for a new one, patch for clarification.

Every plan and review checks compliance. Complexity that violates a principle must be
justified in writing or removed.
