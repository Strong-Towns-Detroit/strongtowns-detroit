# §50-3-386 approval-lapse experiment

Nine pairings exercise automatic lapse at six calendar months, one authorized
extension ending no later than month 18, the absolute extension bar for an
unlawfully established/expanded use later legalized through a hearing, and the
new-application-plus-hearing route after expiration.

```sh
cargo test --offline
cargo clippy --offline --all-targets -- -D warnings
```

The fixture uses month offsets because exact end-of-month behavior needs a
named civil-calendar policy. It treats the deadline instant as inclusive and
the grant as null and void immediately afterward when no timely permit exists.
