# Disposition taxonomy (shared, do not fork)

Answered **before** any priority scoring. A ticket that is not a defect never gets a
priority. This is the judgment that currently lives with a few people.

| Disposition | Definition | Evidence that supports it | Where it goes |
| --- | --- | --- | --- |
| `defect` | System behaves differently from its documented or intended behaviour. | Spec, docs or a prior ticket showing the intended behaviour, plus an observed deviation. | Priority rubric. |
| `expected_behavior` | System is working as designed. The reporter's expectation differs from the design. | A specification, release note, help doc, or a prior ticket closed as works-as-designed describing this exact behaviour. | Close with explanation. Offer the workaround. Consider a docs gap ticket. |
| `config_or_data` | Behaviour caused by a tenant's configuration, permissions, or bad data, not by code. | Config or data value that explains the symptom, and the behaviour is correct given that value. | Route to support or implementation. Not engineering. |
| `duplicate` | Same underlying problem as an existing open ticket. | An open ticket with the same component and the same failure mode. Similar wording alone is not enough. | Link and close. Priority of the parent may need raising. |
| `voice_of_customer` | Working as designed, but the design is wrong or insufficient. A request for change. | No deviation from intended behaviour, and the reporter is asking for different behaviour rather than reporting breakage. | `jira.voc_destination`. Never scored as a defect. |
| `insufficient_information` | Cannot be classified. | Missing repro, component, or error. | Return to reporter with the specific missing items. |

## Rules

1. **Evidence or abstain.** Every disposition other than `defect` must cite something:
   a document, a ticket key, a config value. A disposition with no citation is
   downgraded to `defect` with confidence `low`, because wrongly closing a real bug is
   the expensive error.
2. **`voice_of_customer` is the most commonly missed call.** The test: is the system
   doing what it was built to do? If yes and the customer wants something else, it is
   VoC, however frustrated the reporter is. Severity of frustration is not evidence of
   defect.
3. **`expected_behavior` requires a source the reporter could have read.** If the
   behaviour is correct but undocumented anywhere, the disposition is
   `expected_behavior` **and** a documentation gap is flagged.
4. **Confidence is reported separately from disposition.** Never present a low
   confidence disposition as settled.

## Output

```json
{
  "disposition": "defect",
  "confidence": "high | medium | low",
  "evidence": [{"kind":"doc|ticket|config|spec","ref":"","quote":""}],
  "alternative_considered": "voice_of_customer",
  "why_not": "Behaviour contradicts the documented API contract, so not a design preference."
}
```
