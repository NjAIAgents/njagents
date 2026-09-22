# Fixtures

Recordings of the **live source contract**, not a parallel code path. Every file here
is a complete envelope and must validate against the `data` shape for its source in
`skills/data-sources/SKILL.md`, with no extra nesting. `scripts/validate_config.py`
enforces that.

## Layout

```
fixtures/tracker/<TICKET-KEY>.json        one envelope per ticket
fixtures/metrics/<TICKET-KEY>.json
fixtures/warehouse/<TICKET-KEY>.json
fixtures/code/<TICKET-KEY>.json
fixtures/releases.json                 not ticket-keyed, one envelope
```

A source whose `fixture` value is a **directory** resolves to
`<dir>/<TICKET-KEY>.json`. A missing file resolves to `status: "unavailable"`, which
is the same thing a switched-off source returns, so the code path is identical.

## Re-recording from live

Run the matching enrichment agent against a live environment and save its envelope
here verbatim. If a fixture stops validating, the contract changed and the live
adapter needs the same update in the same commit.

Outputs built on any fixture are banner-marked `DEMO DATA`.
