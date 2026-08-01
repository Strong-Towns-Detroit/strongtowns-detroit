//! Runtime-defined, schema-checked legal ontologies.
//!
//! Rust fixes the ontology mechanics, not a municipality's vocabulary. A
//! corpus can declare its own concepts, individuals, and binary relations;
//! facts only enter the executable knowledge base after domain/range checking.

use std::collections::{BTreeMap, BTreeSet};

use serde::{Deserialize, Serialize};
use thiserror::Error;

use crate::{Area, Duration, Length, LocalDateTime};

macro_rules! identifier {
    ($name:ident, $docs:literal) => {
        #[doc = $docs]
        #[derive(Clone, Debug, Eq, Hash, Ord, PartialEq, PartialOrd, Serialize, Deserialize)]
        #[serde(transparent)]
        pub struct $name(pub String);

        impl From<&str> for $name {
            fn from(value: &str) -> Self {
                Self(value.to_owned())
            }
        }
    };
}

identifier!(
    ConceptId,
    "Stable identifier for an ontology concept or class."
);
identifier!(
    IndividualId,
    "Stable identifier for an ontology individual."
);
identifier!(
    RelationId,
    "Stable identifier for a binary ontology relation."
);
identifier!(
    DataPropertyId,
    "Stable identifier for a typed ontology data property."
);

/// The declared domain and range of a binary object relation.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RelationDefinition {
    /// Stable relation identity.
    pub id: RelationId,
    /// Required concept of the subject.
    pub domain: ConceptId,
    /// Required concept of the object.
    pub range: ConceptId,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
/// Runtime scalar types accepted by ontology data properties.
pub enum DataType {
    /// A nonnegative integral entity or vote count.
    WholeCount,
    /// Exact physical length.
    Length,
    /// Exact physical area.
    Area,
    /// Exact elapsed duration.
    Duration,
    /// Civil date and wall-clock time.
    LocalDateTime,
    /// Boolean truth value.
    Boolean,
    /// Unstructured text retained as data.
    Text,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case", tag = "type", content = "value")]
/// A scalar ontology value whose variant carries its runtime type.
pub enum DataValue {
    /// Whole-number count.
    WholeCount(u64),
    /// Exact length.
    Length(Length),
    /// Exact area.
    Area(Area),
    /// Exact duration.
    Duration(Duration),
    /// Local civil timestamp.
    LocalDateTime(LocalDateTime),
    /// Boolean value.
    Boolean(bool),
    /// Text value.
    Text(String),
}

impl DataValue {
    #[must_use]
    /// Returns the declared runtime type of this value.
    pub const fn data_type(&self) -> DataType {
        match self {
            Self::WholeCount(_) => DataType::WholeCount,
            Self::Length(_) => DataType::Length,
            Self::Area(_) => DataType::Area,
            Self::Duration(_) => DataType::Duration,
            Self::LocalDateTime(_) => DataType::LocalDateTime,
            Self::Boolean(_) => DataType::Boolean,
            Self::Text(_) => DataType::Text,
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
/// Domain and scalar range of one ontology data property.
pub struct DataPropertyDefinition {
    /// Stable property identity.
    pub id: DataPropertyId,
    /// Concept required of the subject.
    pub domain: ConceptId,
    /// Scalar type required of the value.
    pub value_type: DataType,
}

/// An individual and every concept it is directly asserted to instantiate.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Individual {
    /// Stable individual identity.
    pub id: IndividualId,
    /// Direct concept memberships.
    pub concepts: BTreeSet<ConceptId>,
}

/// A validated binary fact in an ontology.
#[derive(Clone, Debug, Eq, Ord, PartialEq, PartialOrd, Serialize, Deserialize)]
pub struct Fact {
    /// Subject individual.
    pub subject: IndividualId,
    /// Declared relation.
    pub relation: RelationId,
    /// Object individual.
    pub object: IndividualId,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
/// A validated scalar assertion about one ontology individual.
pub struct DataFact {
    /// Individual described by the value.
    pub subject: IndividualId,
    /// Declared data property.
    pub property: DataPropertyId,
    /// Dimensionally typed value.
    pub value: DataValue,
}

/// A custom ontology with a schema-checked fact set.
#[derive(Clone, Debug, Default, Eq, PartialEq, Serialize, Deserialize)]
pub struct Ontology {
    concepts: BTreeSet<ConceptId>,
    specializations: BTreeMap<ConceptId, BTreeSet<ConceptId>>,
    relations: BTreeMap<RelationId, RelationDefinition>,
    data_properties: BTreeMap<DataPropertyId, DataPropertyDefinition>,
    individuals: BTreeMap<IndividualId, Individual>,
    facts: BTreeSet<Fact>,
    data_facts: Vec<DataFact>,
}

impl Ontology {
    /// Creates an empty ontology.
    #[must_use]
    pub const fn new() -> Self {
        Self {
            concepts: BTreeSet::new(),
            specializations: BTreeMap::new(),
            relations: BTreeMap::new(),
            data_properties: BTreeMap::new(),
            individuals: BTreeMap::new(),
            facts: BTreeSet::new(),
            data_facts: Vec::new(),
        }
    }

    /// Declares a concept. Repeating the same declaration is idempotent.
    pub fn declare_concept(&mut self, concept: ConceptId) {
        self.concepts.insert(concept);
    }

    /// Declares that every instance of `child` is also an instance of `parent`.
    ///
    /// # Errors
    ///
    /// Returns an error for unknown concepts or a specialization cycle.
    pub fn declare_specialization(
        &mut self,
        child: ConceptId,
        parent: ConceptId,
    ) -> Result<(), OntologyError> {
        for concept in [&child, &parent] {
            if !self.concepts.contains(concept) {
                return Err(OntologyError::UnknownConcept(concept.clone()));
            }
        }
        if child == parent || self.concept_reaches(&parent, &child) {
            return Err(OntologyError::SpecializationCycle);
        }
        self.specializations
            .entry(child)
            .or_default()
            .insert(parent);
        Ok(())
    }

    /// Declares a binary object relation.
    ///
    /// # Errors
    ///
    /// Returns [`OntologyError::UnknownConcept`] if its domain or range has not
    /// been declared, or [`OntologyError::ConflictingRelation`] if the same ID
    /// already has a different signature.
    pub fn declare_relation(
        &mut self,
        definition: RelationDefinition,
    ) -> Result<(), OntologyError> {
        for concept in [&definition.domain, &definition.range] {
            if !self.concepts.contains(concept) {
                return Err(OntologyError::UnknownConcept(concept.clone()));
            }
        }
        if let Some(existing) = self.relations.get(&definition.id) {
            return if existing == &definition {
                Ok(())
            } else {
                Err(OntologyError::ConflictingRelation(definition.id))
            };
        }
        self.relations.insert(definition.id.clone(), definition);
        Ok(())
    }

    /// Declares a typed scalar property.
    ///
    /// # Errors
    ///
    /// Returns an error for an unknown domain or conflicting declaration.
    pub fn declare_data_property(
        &mut self,
        definition: DataPropertyDefinition,
    ) -> Result<(), OntologyError> {
        if !self.concepts.contains(&definition.domain) {
            return Err(OntologyError::UnknownConcept(definition.domain));
        }
        if let Some(existing) = self.data_properties.get(&definition.id) {
            return if existing == &definition {
                Ok(())
            } else {
                Err(OntologyError::ConflictingDataProperty(definition.id))
            };
        }
        self.data_properties
            .insert(definition.id.clone(), definition);
        Ok(())
    }

    /// Declares an individual with one or more direct concept memberships.
    ///
    /// # Errors
    ///
    /// Returns [`OntologyError::UnknownConcept`] for an undeclared concept, or
    /// [`OntologyError::ConflictingIndividual`] if the same ID is redeclared
    /// with different memberships.
    pub fn declare_individual(&mut self, individual: Individual) -> Result<(), OntologyError> {
        for concept in &individual.concepts {
            if !self.concepts.contains(concept) {
                return Err(OntologyError::UnknownConcept(concept.clone()));
            }
        }
        if let Some(existing) = self.individuals.get(&individual.id) {
            return if existing == &individual {
                Ok(())
            } else {
                Err(OntologyError::ConflictingIndividual(individual.id))
            };
        }
        self.individuals.insert(individual.id.clone(), individual);
        Ok(())
    }

    /// Validates and asserts a binary fact.
    ///
    /// # Errors
    ///
    /// The relation and both individuals must exist. The subject must instantiate
    /// the relation's domain and the object must instantiate its range.
    pub fn assert_fact(&mut self, fact: Fact) -> Result<(), OntologyError> {
        let relation = self
            .relations
            .get(&fact.relation)
            .ok_or_else(|| OntologyError::UnknownRelation(fact.relation.clone()))?;
        let subject = self
            .individuals
            .get(&fact.subject)
            .ok_or_else(|| OntologyError::UnknownIndividual(fact.subject.clone()))?;
        let object = self
            .individuals
            .get(&fact.object)
            .ok_or_else(|| OntologyError::UnknownIndividual(fact.object.clone()))?;
        if !self.individual_is(&subject.id, &relation.domain) {
            return Err(OntologyError::DomainMismatch {
                relation: fact.relation,
                expected: relation.domain.clone(),
                actual: fact.subject,
            });
        }
        if !self.individual_is(&object.id, &relation.range) {
            return Err(OntologyError::RangeMismatch {
                relation: fact.relation,
                expected: relation.range.clone(),
                actual: fact.object,
            });
        }
        self.facts.insert(fact);
        Ok(())
    }

    /// Type-checks and records a scalar fact.
    ///
    /// # Errors
    ///
    /// Returns an error for unknown properties, wrong domains, or wrong scalar types.
    pub fn assert_data_fact(&mut self, fact: DataFact) -> Result<(), OntologyError> {
        let definition = self
            .data_properties
            .get(&fact.property)
            .ok_or_else(|| OntologyError::UnknownDataProperty(fact.property.clone()))?;
        if !self.individual_is(&fact.subject, &definition.domain) {
            return Err(OntologyError::DataDomainMismatch {
                property: fact.property,
                expected: definition.domain.clone(),
                actual: fact.subject,
            });
        }
        if fact.value.data_type() != definition.value_type {
            return Err(OntologyError::DataTypeMismatch {
                property: fact.property,
                expected: definition.value_type,
                actual: fact.value.data_type(),
            });
        }
        self.data_facts.push(fact);
        Ok(())
    }

    /// Tests direct or specialization-inherited concept membership.
    #[must_use]
    pub fn individual_is(&self, individual: &IndividualId, concept: &ConceptId) -> bool {
        self.individuals.get(individual).is_some_and(|value| {
            value
                .concepts
                .iter()
                .any(|direct| direct == concept || self.concept_reaches(direct, concept))
        })
    }

    fn concept_reaches(&self, child: &ConceptId, ancestor: &ConceptId) -> bool {
        let mut pending = vec![child];
        let mut seen = BTreeSet::new();
        while let Some(current) = pending.pop() {
            if !seen.insert(current.clone()) {
                continue;
            }
            if let Some(parents) = self.specializations.get(current) {
                if parents.contains(ancestor) {
                    return true;
                }
                pending.extend(parents);
            }
        }
        false
    }

    /// Tests whether an exact validated fact is present.
    #[must_use]
    pub fn contains(&self, fact: &Fact) -> bool {
        self.facts.contains(fact)
    }

    /// Returns the validated fact set.
    #[must_use]
    pub fn facts(&self) -> impl ExactSizeIterator<Item = &Fact> {
        self.facts.iter()
    }

    /// Returns all validated scalar facts.
    #[must_use]
    pub fn data_facts(&self) -> impl ExactSizeIterator<Item = &DataFact> {
        self.data_facts.iter()
    }
}

/// A custom ontology declaration or fact failed schema validation.
#[derive(Clone, Debug, Error, Eq, PartialEq)]
pub enum OntologyError {
    /// A referenced concept has not been declared.
    #[error("unknown ontology concept: {0:?}")]
    UnknownConcept(ConceptId),
    /// A relation ID was reused with a different domain or range.
    #[error("relation has a conflicting declaration: {0:?}")]
    ConflictingRelation(RelationId),
    #[error("data property has a conflicting declaration: {0:?}")]
    /// A data-property ID was reused with a different signature.
    ConflictingDataProperty(DataPropertyId),
    #[error("ontology concept specialization forms a cycle")]
    /// Concept specialization would become cyclic.
    SpecializationCycle,
    /// An individual ID was reused with different concept memberships.
    #[error("individual has a conflicting declaration: {0:?}")]
    ConflictingIndividual(IndividualId),
    /// A referenced relation has not been declared.
    #[error("unknown ontology relation: {0:?}")]
    UnknownRelation(RelationId),
    #[error("unknown ontology data property: {0:?}")]
    /// A referenced data property has not been declared.
    UnknownDataProperty(DataPropertyId),
    /// A referenced individual has not been declared.
    #[error("unknown ontology individual: {0:?}")]
    UnknownIndividual(IndividualId),
    /// The subject is not an instance of the relation's domain.
    #[error("relation {relation:?} requires subject concept {expected:?}, not {actual:?}")]
    DomainMismatch {
        /// Relation whose domain was violated.
        relation: RelationId,
        /// Required subject concept.
        expected: ConceptId,
        /// Supplied subject individual.
        actual: IndividualId,
    },
    /// The object is not an instance of the relation's range.
    #[error("relation {relation:?} requires object concept {expected:?}, not {actual:?}")]
    RangeMismatch {
        /// Relation whose range was violated.
        relation: RelationId,
        /// Required object concept.
        expected: ConceptId,
        /// Supplied object individual.
        actual: IndividualId,
    },
    #[error("data property {property:?} requires subject concept {expected:?}, not {actual:?}")]
    /// The data-fact subject does not instantiate the required domain.
    DataDomainMismatch {
        /// Property being asserted.
        property: DataPropertyId,
        /// Required subject concept.
        expected: ConceptId,
        /// Actual subject individual.
        actual: IndividualId,
    },
    #[error("data property {property:?} requires {expected:?}, not {actual:?}")]
    /// The scalar value has the wrong physical or logical type.
    DataTypeMismatch {
        /// Property being asserted.
        property: DataPropertyId,
        /// Declared value type.
        expected: DataType,
        /// Supplied value type.
        actual: DataType,
    },
}

#[cfg(test)]
mod tests {
    use std::collections::BTreeSet;

    use super::{
        ConceptId, DataFact, DataPropertyDefinition, DataPropertyId, DataType, DataValue, Fact,
        Individual, IndividualId, Ontology, OntologyError, RelationDefinition, RelationId,
    };

    fn individual(id: &str, concepts: &[&str]) -> Individual {
        Individual {
            id: IndividualId::from(id),
            concepts: concepts
                .iter()
                .map(|value| ConceptId::from(*value))
                .collect(),
        }
    }

    #[test]
    fn accepts_only_facts_matching_custom_relation_types() {
        let mut ontology = Ontology::new();
        ontology.declare_concept(ConceptId::from("Agency"));
        ontology.declare_concept(ConceptId::from("Notice"));
        ontology
            .declare_relation(RelationDefinition {
                id: RelationId::from("responsibleFor"),
                domain: ConceptId::from("Agency"),
                range: ConceptId::from("Notice"),
            })
            .unwrap();
        ontology
            .declare_individual(individual("BSEED", &["Agency"]))
            .unwrap();
        ontology
            .declare_individual(individual("notice-1", &["Notice"]))
            .unwrap();

        let valid = Fact {
            subject: IndividualId::from("BSEED"),
            relation: RelationId::from("responsibleFor"),
            object: IndividualId::from("notice-1"),
        };
        ontology.assert_fact(valid.clone()).unwrap();
        assert!(ontology.contains(&valid));

        let reversed = Fact {
            subject: IndividualId::from("notice-1"),
            relation: RelationId::from("responsibleFor"),
            object: IndividualId::from("BSEED"),
        };
        assert!(matches!(
            ontology.assert_fact(reversed),
            Err(OntologyError::DomainMismatch { .. })
        ));
        assert_eq!(ontology.facts().len(), 1);
        assert_eq!(BTreeSet::from([valid]), ontology.facts().cloned().collect());
    }

    #[test]
    fn specialization_satisfies_parent_domains() {
        let mut ontology = Ontology::new();
        for concept in ["Matter", "Variance", "Decision"] {
            ontology.declare_concept(ConceptId::from(concept));
        }
        ontology
            .declare_specialization(ConceptId::from("Variance"), ConceptId::from("Matter"))
            .unwrap();
        ontology
            .declare_relation(RelationDefinition {
                id: RelationId::from("concerns"),
                domain: ConceptId::from("Decision"),
                range: ConceptId::from("Matter"),
            })
            .unwrap();
        ontology
            .declare_individual(individual("decision", &["Decision"]))
            .unwrap();
        ontology
            .declare_individual(individual("hardship_variance", &["Variance"]))
            .unwrap();
        ontology
            .assert_fact(Fact {
                subject: IndividualId::from("decision"),
                relation: RelationId::from("concerns"),
                object: IndividualId::from("hardship_variance"),
            })
            .unwrap();
        assert!(ontology.individual_is(
            &IndividualId::from("hardship_variance"),
            &ConceptId::from("Matter")
        ));
    }

    #[test]
    fn data_properties_reject_wrong_dimensions() {
        let mut ontology = Ontology::new();
        ontology.declare_concept(ConceptId::from("Board"));
        ontology
            .declare_individual(individual("BZA", &["Board"]))
            .unwrap();
        ontology
            .declare_data_property(DataPropertyDefinition {
                id: DataPropertyId::from("authorized_members"),
                domain: ConceptId::from("Board"),
                value_type: DataType::WholeCount,
            })
            .unwrap();
        ontology
            .assert_data_fact(DataFact {
                subject: IndividualId::from("BZA"),
                property: DataPropertyId::from("authorized_members"),
                value: DataValue::WholeCount(9),
            })
            .unwrap();
        let error = ontology
            .assert_data_fact(DataFact {
                subject: IndividualId::from("BZA"),
                property: DataPropertyId::from("authorized_members"),
                value: DataValue::Length(crate::Length::feet(9)),
            })
            .unwrap_err();
        assert!(matches!(error, OntologyError::DataTypeMismatch { .. }));
    }
}
