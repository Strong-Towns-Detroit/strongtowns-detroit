# Semantic core promoted from statement experiments

The six statement experiments produced repeated requirements that now live in
the Rust core. Surface-language syntax remains experimental.

| Requirement | Core representation | Source fixture |
|---|---|---|
| Concept specialization | `Ontology::declare_specialization` | §50-2-78 |
| Runtime-typed scalar facts | `DataPropertyDefinition`, `DataValue` | §§50-2-78, 50-2-79, 50-3-443 |
| Exact count fractions | `WholeCountThreshold` | §50-2-78 |
| Named civil calendars | `CalendarOffset`, `CalendarPolicyId` | §§50-2-79, 50-3-386 |
| Named spatial methods | `SpatialMeasurementPolicy` | §50-3-341 |
| Identity-aware aggregation | `count_distinct_by_identity` | §50-3-341 |
| Scoped closed-world reasoning | `KnowledgePolicy` | §§50-3-341, 50-3-443 |
| Normative force | `LegalModality` | all fixtures |
| Automatic state changes | `LegalEffect::StateTransition` | §50-3-386 |
| Discretionary authority | `LegalModality::Power` and `LegalEffect::Authorize` | §§50-3-386, 50-3-443 |
| Explicit precedence | `PrecedenceGraph` and `PrecedenceBasis` | §§50-2-78, 50-3-386 |
| Source/interpretation separation | `CoordinationSignal`, `ReviewedCoordination` | §50-3-443 |
| Execution blocked by ambiguity | `Interpretation::Unresolved` | §50-3-443 |

## Deliberate boundaries

- Calendar IDs identify a required policy; the engine does not pretend that
  Monday–Friday arithmetic is a complete Detroit business calendar.
- Spatial policy identifies CRS, measurement target, and boundary inclusion;
  geometry repair and distance execution remain provider responsibilities.
- Closed-world negation is predicate- and authority-specific. Missing facts are
  otherwise unknown.
- Precedence must be sourced or reviewed. The engine does not infer legal
  hierarchy merely from rule order.
- Unresolved interpretations cannot execute. Both source signals and candidate
  meanings remain serializable for later review.
- Data properties are unary scalar facts. Measurements involving several legal
  entities should currently be represented as qualified measurement
  individuals rather than prematurely adding arbitrary n-ary properties.

## Still experimental

The provision, labeled-frame, and Datalog syntaxes are not production parsers.
The next fixtures should pressure district/use tables, dimensional geometry,
accessory-use inheritance, enumerated approval criteria, and cross-article rule
composition before the canonical rule-expression AST is frozen.
