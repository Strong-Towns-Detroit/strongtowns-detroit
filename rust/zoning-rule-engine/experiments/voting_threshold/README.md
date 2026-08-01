# §50-2-78 voting-threshold experiment

This one-off experiment renders the BZA voting rule in all three ontology and
all three legal-rule styles. Its nine executable cells verify the same result
for every pairing without adding voting concepts to the permanent IR.

```sh
cargo test --offline
cargo clippy --offline --all-targets -- -D warnings
```

The fixture interprets “majority” as strictly more than half of all authorized
members and “two-thirds majority” as the least whole number not below two
thirds of all authorized members. For nine members, ordinary matters therefore
require five concurring votes and hardship-relief use variances require six.

## What this fixture exposed

- All three ontology styles need integer-valued data properties, not only
  object relations.
- Matter classification needs specialization: a hardship-relief use variance
  remains a variance while receiving the more-specific threshold.
- The default rule must explicitly exclude the override case, or the two rules
  derive conflicting required counts.
- `overrides` is clearest in the provision styles, while Datalog makes the
  executable exclusion clearest through stratified negation.
- Exact rational thresholds still require an explicit whole-number rounding
  rule; the ordinance does not spell that operation out.

The parser checks in this crate are deliberately fixture-specific. They confirm
that legally material syntax is present and normalize it for comparison; they
are not candidates for the production compiler.
