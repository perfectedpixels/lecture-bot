# 4.0 Calibration

One JSON file per assignment, anchoring what a 4.0 actually looks like so
suggested scores stay stable across a grading session and across terms.

Files are named by slug (`persona-development.json`, `wireframes.json`, …) and
matched to an assignment by their `assignment` field, which must exactly equal
a section name from the grading handbook. `src/grading.py` loads these; a
missing file simply means that assignment grades on the handbook rubric alone.

## Why files, not a database

These are curated instructor artifacts that should be **reviewed before they
take effect** — they change what students get graded against. Keeping them in
git means every change is diffable, reviewable, and revertable. The tradeoff is
that adding one requires a redeploy.

## Shape

```json
{
  "assignment": "Assignment 2.1: Persona Development",
  "derived_rules": {
    "what_4_0_looks_like": "Prose description of the bar for full marks.",
    "distinguishing_markers": ["What separates 4.0 from 3.x here"],
    "common_failure_modes": ["What repeatedly costs students points"]
  },
  "exemplar": {
    "text": "Optional. A de-identified submission that earned 4.0.",
    "score": 4.0,
    "deidentified": true,
    "provenance": "How this was obtained and cleared for reuse."
  }
}
```

`derived_rules` is the important half and is safe to keep indefinitely — it's
rubric language, not student work. `exemplar` is optional; omit the key
entirely if you don't want to store submission text.

## Before storing an exemplar

An exemplar is a real student's work, retained indefinitely and used to
evaluate their classmates. Two things are worth checking:

1. **Permission.** Student work is an educational record. Get explicit consent
   for reuse as a teaching/calibration artifact.
2. **De-identification is more than the name.** A persona or journey map is
   *about* the student's chosen project — the domain, the research site, and
   the interview details can identify them within a cohort even with the name
   stripped. Read it as a classmate would before saving.

If either is awkward, use `derived_rules` alone, or write a synthetic exemplar.
Calibration still works; it just leans on the rules instead of the sample.

## Generating derived rules

The `derive_calibration` MCP tool turns a 4.0 submission into draft
`derived_rules` for you to edit. It is a drafting aid — read and correct the
output before saving it here, since whatever lands in this directory shapes
every subsequent grade for that assignment.
