# SDML-inspired ontology experiment

This executable spike keeps two reviewed modules separate:

- `ontology.sdmlish` declares reusable concepts, individuals, and typed relations.
- `article_iii.rules` declares the source-linked legal provision that imports the ontology.

Run it with `cargo test --manifest-path experiments/sdml_style/Cargo.toml` from the parent crate.

## What it tests

The parser compiles the ontology into the parent engine's runtime `Ontology`, validates every rule atom against relation domain/range declarations, and evaluates the exact inclusive 15-day boundary using the parent's integer `Duration`.

## Tradeoffs

The ontology syntax is pleasant for schemas and resembles SDML's modules, entities, and member definitions. The separate rule file makes reuse and versioned imports natural. The rule syntax is intentionally more conventional: explicit `&&` preserves Boolean structure without inventing English connectives.

This is not SDML and does not claim SDML compatibility. A full design would need imports with selected/versioned names, concept inheritance, source spans on every declaration, a real lexer/parser, typed temporal properties, exceptions and precedence, and diagnostic recovery.

## Source faithfulness

The provision preserves its stable proposition ID, both reviewed quotations, strict status, and explicit absence of exceptions. These are still quote values rather than character-addressed `SourceSpan` objects, and the model does not retain enough sentence structure to reproduce the ordinance. That requires the separate source-faithful legal AST discussed in the main design, followed by normalization into this executable shape.
