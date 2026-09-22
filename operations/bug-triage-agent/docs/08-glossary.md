# Glossary

Terms that mean something specific here.

| Term | Meaning |
| --- | --- |
| **Disposition** | What kind of thing a ticket is: defect, expected behaviour, config or data, duplicate, voice-of-customer, insufficient information. Decided *before* any priority |
| **Voice-of-customer** | The system does what it was designed to do and the reporter wants different behaviour. A request for change, not a defect, however frustrated the reporter |
| **Information gate** | Stage 0. Refuses to triage a ticket lacking a description, component, and a repro step or error |
| **Envelope** | The uniform wrapper every source returns: source, mode, status, as_of, latency, data, notes. Identical whether live or recorded |
| **Mode** | `live`, `fixture` or `off`, per source, per team |
| **Fixture** | A recorded envelope, validated against the same shape a live adapter produces. Not a parallel code path |
| **Unavailable** | A source switched off or not configured. A normal state. Distinct from `error`, which means configured and failed |
| **Blast radius** | How many accounts are affected, and how many are enterprise tier |
| **Escalation class** | The category a signal belongs to: release, code, history, impact, blast. **One escalation per class**, so one observation cannot be counted three ways |
| **Cap** | Total escalation is limited to two levels, and P1 is never reached by escalation. P1 requires meeting a P1 criterion directly |
| **At-risk floor** | An at-risk client sets a P2 minimum. The floor **consumes the blast class**, so enterprise tier adds nothing on top |
| **Base precedence** | When several criteria match, a practical *customer* workaround caps the base at P3; otherwise take the highest match |
| **Customer workaround** | Something the customer or support can do. An engineer-run script is **not** one, and does not count as practical for the rubric |
| **Confirmed regression** | A metric spike at or above the configured ratio **and** a deploy inside the window. A spike alone is "trending" |
| **Rolling baseline** | Median over several days, not the prior day. Prior-day baselines produce false regressions across weekends |
| **Honest negative** | Reporting that no release in the window touched the area. A finding, not a failure |
| **Provenance line** | The line on every output naming which sources were live, fixture or unavailable |
| **Unanswered question** | A classification question whose source was off or errored. Lowers confidence; never raises priority |
| **Zero-setup tier** | Running with the tracker and releases only. The adoption path, not a degraded mode |
| **Shared core** | `skills/` and `reference/`. Versioned, never forked, and never names a product or customer |
| **Team config** | The single file a team owns under `teams/` |
| **Override** | A human correcting a recommendation, recorded without altering the original. The gap between them is the measurement |
| **Calibration set** | Real tickets with the disposition an expert gave, used to measure agreement per class |
