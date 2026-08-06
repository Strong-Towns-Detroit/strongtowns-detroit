# §50-2-79 decision-finality experiment

All nine ontology/rule pairings encode the ordinary finality date and the
certified immediate-effect exception.

```sh
cargo test --offline
cargo clippy --offline --all-targets -- -D warnings
```

The fixture treats the vote timestamp as the rendering timestamp and counts the
next three Monday-through-Friday dates as business days; it does not yet model
City holidays or exceptional closures. “Immediate” means the rendering/vote
timestamp. Those are explicit interpretive assumptions, not claims supplied by
the ordinance text.

The exception requires all three factual elements: a Board finding, necessity
for preserving property or personal rights, and certification on the record.
