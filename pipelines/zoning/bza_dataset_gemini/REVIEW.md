# BZA Gemini dataset: acceptance review

## Result

All 164 source PDFs have an independent Gemini extraction. The 537 raw records
reconcile to 520 case occurrences. The targeted review queue is empty after
source review and explicit treatment of agenda records.

## Review decisions

- Twenty-four records come from agendas/dockets rather than adjudicative
  minutes. They are retained as `record_type=agenda_case` with
  `decision_status=not_recorded`; they must not enter approval-rate statistics.
- Repeated blocks for one case are reconciled so that secondary motions (for
  example, a fee refund) do not overwrite the principal action.
- Duplicate PDF versions are reconciled rather than counted as separate case
  occurrences.
- The November 26, 2019 minutes print case number `76-19` for two different
  matters. Both are retained with distinct `occurrence_id` values.
- Case `84-24` on April 14, 2025 lacks a printed final disposition line, but the
  minutes record a motion to grant, nine affirmative votes, and zero negative
  votes. It is classified as granted with
  `decision_basis=inferred_from_motion_and_vote`.
- Case `87-19` on February 11, 2020 records “NO ACTION TAKEN DUE TO MORATORIUM”
  and is classified as `no_action`.

## Analytical denominator

For outcome analysis, begin with `record_type == "minutes_case"` and select the
decision statuses relevant to the question. Do not treat `agenda_case`,
`postponed`, `under_advisement`, or `no_action` as approvals or denials.

`decision_basis` distinguishes printed dispositions from the small number of
outcomes inferred from an unambiguous recorded motion and vote.

