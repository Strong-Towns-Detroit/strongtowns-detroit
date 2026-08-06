//! Deterministic, source-addressed candidate extraction for legal text.
//!
//! Extraction does not create ontology declarations. It creates conservative
//! coverage obligations: every token is either recognized as structure or is
//! attached to at least one unresolved candidate requiring disposition.

use std::collections::{BTreeMap, BTreeSet};

use serde::{Deserialize, Serialize};

use crate::SpanDigest;

/// Version of the deterministic extraction algorithm.
pub const EXTRACTOR_VERSION: &str = "deterministic-legal-v1";

/// A half-open UTF-8 byte range in one immutable source document.
#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TextSpan {
    /// Inclusive starting byte.
    pub start: usize,
    /// Exclusive ending byte.
    pub end: usize,
}

/// Exact source supplied to the extraction pipeline.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SourceDocument {
    /// Stable source identity.
    pub id: String,
    /// Exact text.
    pub text: String,
    /// Content digest.
    pub digest: SpanDigest,
}

impl SourceDocument {
    /// Creates a content-addressed source document.
    #[must_use]
    pub fn new(id: impl Into<String>, text: impl Into<String>) -> Self {
        let text = text.into();
        Self {
            id: id.into(),
            digest: SpanDigest::of(&text),
            text,
        }
    }
}

/// Lexical token category. Whitespace is retained by source offsets rather
/// than emitted as tokens.
#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TokenKind {
    /// Alphabetic word, including internal apostrophes.
    Word,
    /// Integral or decimal numeral.
    Number,
    /// Section citation beginning with `§`.
    Citation,
    /// Syntactic punctuation.
    Punctuation,
    /// Other non-whitespace symbol.
    Symbol,
}

/// One exact source token.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Token {
    /// Stable within-document token index.
    pub id: usize,
    /// Exact source spelling.
    pub text: String,
    /// Case-folded lookup form.
    pub normalized: String,
    /// Token class.
    pub kind: TokenKind,
    /// Exact source range.
    pub span: TextSpan,
}

/// Reproducible lexical implications, not committed parts of speech.
#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum LexicalHint {
    /// May denote a concept, individual, or variable.
    Noun,
    /// May denote an action, relation, or legal effect.
    Verb,
    /// May denote a refinement, subtype, or predicate.
    Modifier,
    /// May require reference resolution.
    Coreference,
    /// No reliable lexical implication was established.
    Unknown,
}

/// Kind of source-bound review candidate.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case", tag = "kind")]
pub enum CandidateKind {
    /// `shall`, `may`, or another possible normative operator.
    LegalModality {
        /// Exact normalized marker.
        marker: String,
    },
    /// Conditional applicability marker.
    Condition {
        /// Exact normalized marker.
        marker: String,
    },
    /// Express exception marker.
    Exception {
        /// Exact normalized marker.
        marker: String,
    },
    /// Express priority marker.
    Priority {
        /// Exact normalized marker.
        marker: String,
    },
    /// `and`, `or`, or another coordination signal.
    Coordination {
        /// Exact normalized marker.
        marker: String,
    },
    /// Exact legal citation.
    Citation,
    /// Typed quantity candidate.
    Quantity {
        /// Exact numeric spelling.
        value: String,
        /// Adjacent recognized unit, when present.
        unit: Option<String>,
    },
    /// Temporal expression candidate.
    Temporal,
    /// Possible named entity.
    ProperName,
    /// Candidate grammatical subject surrounding a modal.
    SubjectPhrase,
    /// Candidate normative predicate following a modal.
    PredicatePhrase,
    /// Open-class lexical item with one or more possible roles.
    Lexical {
        /// Conservative possible lexical roles.
        hints: BTreeSet<LexicalHint>,
    },
}

/// Required disposition of a source candidate.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case", tag = "status")]
pub enum CandidateDisposition {
    /// No semantic decision has been recorded.
    Unreviewed,
    /// Reuses one or more canonical declarations.
    Mapped {
        /// Reused canonical identities.
        symbols: Vec<String>,
    },
    /// Requires a new canonical declaration.
    NewDeclaration {
        /// Proposed canonical identity.
        symbol: String,
    },
    /// Performs only grammatical or structural work.
    Grammatical,
    /// Resolves to another source expression.
    Coreference {
        /// Candidate containing the referent.
        candidate: String,
    },
    /// Is synonymous with another reviewed candidate in this context.
    Synonym {
        /// Candidate with the canonical contextual meaning.
        candidate: String,
    },
    /// Preserves an open-textured predicate or concept.
    InterpretiveGap {
        /// Typed interpretive declaration.
        symbol: String,
    },
    /// Meaning is supplied by an identified external authority.
    ExternalAuthority {
        /// Controlling source identity.
        source: String,
    },
    /// Reviewed as irrelevant to the legal proposition being encoded.
    LegallyIrrelevant {
        /// Reviewed explanation.
        rationale: String,
    },
    /// Review occurred but did not resolve the candidate.
    Unresolved {
        /// Question preventing resolution.
        question: String,
    },
}

/// One exact source span requiring semantic disposition.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Candidate {
    /// Stable within-extraction identity.
    pub id: String,
    /// Candidate category.
    pub kind: CandidateKind,
    /// Exact text.
    pub text: String,
    /// Source range.
    pub span: TextSpan,
    /// Every token participating in the candidate.
    pub token_ids: Vec<usize>,
    /// Semantic review state.
    pub disposition: CandidateDisposition,
}

/// Why one token is structurally accounted for without semantic review.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum StructuralRole {
    /// Punctuation or delimiter.
    Punctuation,
    /// Determiner, auxiliary, or other closed-class grammar.
    FunctionWord,
}

/// Coverage state for one source token.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", tag = "coverage")]
pub enum TokenCoverage {
    /// Automatically accounted for as syntax.
    Structural {
        /// Automatically recognized structural function.
        role: StructuralRole,
    },
    /// Attached to one or more review candidates.
    Candidates {
        /// Overlapping candidate identities covering the token.
        candidate_ids: Vec<String>,
    },
}

/// Token-level coverage record.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CoveredToken {
    /// Token identity.
    pub token_id: usize,
    /// Structural or candidate coverage.
    pub result: TokenCoverage,
}

/// Machine-checkable extraction coverage summary.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CoverageReport {
    /// Number of non-whitespace source tokens.
    pub token_count: usize,
    /// Tokens assigned either structure or candidate coverage.
    pub covered_token_count: usize,
    /// Total review candidates, including overlapping phrases.
    pub candidate_count: usize,
    /// Candidates without a reviewed disposition.
    pub unreviewed_candidate_count: usize,
    /// True only when every token is accounted for.
    pub lexical_coverage_complete: bool,
    /// True only when every candidate has a reviewed disposition.
    pub semantic_disposition_complete: bool,
}

/// Complete deterministic extraction artifact.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Extraction {
    /// Extractor contract version.
    pub extractor_version: String,
    /// Immutable source.
    pub source: SourceDocument,
    /// Exact tokens.
    pub tokens: Vec<Token>,
    /// Overlapping review candidates.
    pub candidates: Vec<Candidate>,
    /// Disposition obligation for each token.
    pub token_coverage: Vec<CoveredToken>,
    /// Aggregate coverage state.
    pub coverage: CoverageReport,
}

/// Deterministically extracts structural markers and conservative lexical
/// candidates from one exact legal source.
#[must_use]
pub fn extract(source: SourceDocument) -> Extraction {
    let tokens = tokenize(&source.text);
    let mut builder = CandidateBuilder::new(&source.text, &tokens);
    builder.extract_markers();
    builder.extract_quantities_and_time();
    builder.extract_proper_names();
    builder.extract_modal_phrases();
    builder.cover_remaining_words();
    let (candidates, token_coverage) = builder.finish();
    let unreviewed_candidate_count = candidates
        .iter()
        .filter(|candidate| candidate.disposition == CandidateDisposition::Unreviewed)
        .count();
    let covered_token_count = token_coverage.len();
    Extraction {
        extractor_version: EXTRACTOR_VERSION.to_owned(),
        source,
        coverage: CoverageReport {
            token_count: tokens.len(),
            covered_token_count,
            candidate_count: candidates.len(),
            unreviewed_candidate_count,
            lexical_coverage_complete: covered_token_count == tokens.len(),
            semantic_disposition_complete: unreviewed_candidate_count == 0,
        },
        tokens,
        candidates,
        token_coverage,
    }
}

fn tokenize(source: &str) -> Vec<Token> {
    let mut tokens = Vec::new();
    let mut iterator = source.char_indices().peekable();
    while let Some((start, character)) = iterator.next() {
        if character.is_whitespace() {
            continue;
        }
        let (kind, end) = if character == '§' {
            let mut end = start + character.len_utf8();
            while let Some(&(index, next)) = iterator.peek() {
                if next.is_ascii_alphanumeric() || matches!(next, '-' | '–' | '(' | ')' | '.') {
                    iterator.next();
                    end = index + next.len_utf8();
                } else {
                    break;
                }
            }
            (TokenKind::Citation, end)
        } else if character.is_alphabetic() {
            let mut end = start + character.len_utf8();
            while let Some(&(index, next)) = iterator.peek() {
                if next.is_alphabetic() || matches!(next, '\'' | '’') {
                    iterator.next();
                    end = index + next.len_utf8();
                } else {
                    break;
                }
            }
            (TokenKind::Word, end)
        } else if character.is_ascii_digit() {
            let mut end = start + character.len_utf8();
            while let Some(&(index, next)) = iterator.peek() {
                if next.is_ascii_digit() || matches!(next, ',' | '.') {
                    iterator.next();
                    end = index + next.len_utf8();
                } else {
                    break;
                }
            }
            (TokenKind::Number, end)
        } else if matches!(character, '.' | ',' | ';' | ':' | '(' | ')' | '[' | ']') {
            (TokenKind::Punctuation, start + character.len_utf8())
        } else {
            (TokenKind::Symbol, start + character.len_utf8())
        };
        let text = source[start..end].to_owned();
        tokens.push(Token {
            id: tokens.len(),
            normalized: text.to_lowercase(),
            text,
            kind,
            span: TextSpan { start, end },
        });
    }
    tokens
}

struct CandidateBuilder<'a> {
    source: &'a str,
    tokens: &'a [Token],
    candidates: Vec<Candidate>,
    token_candidates: BTreeMap<usize, Vec<String>>,
}

impl<'a> CandidateBuilder<'a> {
    fn new(source: &'a str, tokens: &'a [Token]) -> Self {
        Self {
            source,
            tokens,
            candidates: Vec::new(),
            token_candidates: BTreeMap::new(),
        }
    }

    fn extract_markers(&mut self) {
        for token in self.tokens {
            let kind = match token.normalized.as_str() {
                "shall" | "may" | "must" => Some(CandidateKind::LegalModality {
                    marker: token.normalized.clone(),
                }),
                "where" | "if" | "when" | "provided" => Some(CandidateKind::Condition {
                    marker: token.normalized.clone(),
                }),
                "except" | "unless" => Some(CandidateKind::Exception {
                    marker: token.normalized.clone(),
                }),
                "notwithstanding" => Some(CandidateKind::Priority {
                    marker: token.normalized.clone(),
                }),
                "and" | "or" => Some(CandidateKind::Coordination {
                    marker: token.normalized.clone(),
                }),
                _ if token.kind == TokenKind::Citation => Some(CandidateKind::Citation),
                _ => None,
            };
            if let Some(kind) = kind {
                self.push(kind, token.id, token.id + 1);
            }
        }
    }

    fn extract_quantities_and_time(&mut self) {
        for index in 0..self.tokens.len() {
            let token = &self.tokens[index];
            if token.kind != TokenKind::Number {
                continue;
            }
            let unit = self.tokens.get(index + 1).and_then(|next| {
                matches!(
                    next.normalized.as_str(),
                    "day" | "days" | "foot" | "feet" | "months"
                )
                .then(|| next.text.clone())
            });
            let end = index + usize::from(unit.is_some()) + 1;
            self.push(
                CandidateKind::Quantity {
                    value: token.text.clone(),
                    unit,
                },
                index,
                end,
            );
            let temporal_start = index.saturating_sub(2);
            let temporal_end = (end + 2).min(self.tokens.len());
            let neighborhood = self.tokens[temporal_start..temporal_end]
                .iter()
                .map(|item| item.normalized.as_str())
                .collect::<Vec<_>>();
            if neighborhood
                .iter()
                .any(|word| matches!(*word, "before" | "prior" | "within" | "after" | "least"))
            {
                self.push(CandidateKind::Temporal, temporal_start, temporal_end);
            }
        }
    }

    fn extract_proper_names(&mut self) {
        let mut index = 0;
        while index < self.tokens.len() {
            if !is_proper_word(&self.tokens[index]) {
                index += 1;
                continue;
            }
            let start = index;
            index += 1;
            while index < self.tokens.len() && is_proper_word(&self.tokens[index]) {
                index += 1;
            }
            self.push(CandidateKind::ProperName, start, index);
        }
    }

    fn extract_modal_phrases(&mut self) {
        let modal_indexes = self
            .tokens
            .iter()
            .filter(|token| matches!(token.normalized.as_str(), "shall" | "may" | "must"))
            .map(|token| token.id)
            .collect::<Vec<_>>();
        for modal in modal_indexes {
            let sentence_start = self.tokens[..modal]
                .iter()
                .rposition(|token| token.text == "." || token.text == ";")
                .map_or(0, |index| index + 1);
            let subject_start = self.tokens[sentence_start..modal]
                .iter()
                .rposition(|token| token.text == ",")
                .map_or(sentence_start, |index| sentence_start + index + 1);
            if subject_start < modal {
                self.push(CandidateKind::SubjectPhrase, subject_start, modal);
            }
            let sentence_end = self.tokens[modal + 1..]
                .iter()
                .position(|token| token.text == "." || token.text == ";")
                .map_or(self.tokens.len(), |index| modal + 1 + index);
            if modal + 1 < sentence_end {
                self.push(CandidateKind::PredicatePhrase, modal + 1, sentence_end);
            }
        }
    }

    fn cover_remaining_words(&mut self) {
        for token in self.tokens {
            if token.kind != TokenKind::Word || is_legal_marker(&token.normalized) {
                continue;
            }
            let mut hints = BTreeSet::new();
            if is_pronoun(&token.normalized) {
                hints.insert(LexicalHint::Coreference);
            } else if is_function_word(&token.normalized) {
                continue;
            }
            if is_known_verb(&token.normalized)
                || token.normalized.ends_with("ing")
                || token.normalized.ends_with("ed")
            {
                hints.insert(LexicalHint::Verb);
            }
            if !is_pronoun(&token.normalized) {
                hints.insert(LexicalHint::Noun);
                if token.normalized.ends_with("al")
                    || token.normalized.ends_with("ive")
                    || token.normalized.ends_with("ous")
                    || token.normalized.ends_with("able")
                    || token.normalized.ends_with("ible")
                {
                    hints.insert(LexicalHint::Modifier);
                }
            }
            if hints.is_empty() {
                hints.insert(LexicalHint::Unknown);
            }
            self.push(CandidateKind::Lexical { hints }, token.id, token.id + 1);
        }
    }

    fn push(&mut self, kind: CandidateKind, start: usize, end: usize) {
        if start >= end || end > self.tokens.len() {
            return;
        }
        let id = format!("c{:04}", self.candidates.len() + 1);
        let span = TextSpan {
            start: self.tokens[start].span.start,
            end: self.tokens[end - 1].span.end,
        };
        for token in &self.tokens[start..end] {
            self.token_candidates
                .entry(token.id)
                .or_default()
                .push(id.clone());
        }
        self.candidates.push(Candidate {
            id,
            kind,
            text: self.source[span.start..span.end].to_owned(),
            span,
            token_ids: self.tokens[start..end]
                .iter()
                .map(|token| token.id)
                .collect(),
            disposition: CandidateDisposition::Unreviewed,
        });
    }

    fn finish(mut self) -> (Vec<Candidate>, Vec<CoveredToken>) {
        let mut coverage = Vec::with_capacity(self.tokens.len());
        for token in self.tokens {
            let result = self.token_candidates.remove(&token.id).map_or_else(
                || TokenCoverage::Structural {
                    role: if token.kind == TokenKind::Punctuation || token.kind == TokenKind::Symbol
                    {
                        StructuralRole::Punctuation
                    } else {
                        StructuralRole::FunctionWord
                    },
                },
                |candidate_ids| TokenCoverage::Candidates { candidate_ids },
            );
            coverage.push(CoveredToken {
                token_id: token.id,
                result,
            });
        }
        (self.candidates, coverage)
    }
}

fn is_proper_word(token: &Token) -> bool {
    token.kind == TokenKind::Word
        && token.text.chars().next().is_some_and(char::is_uppercase)
        && !matches!(token.normalized.as_str(), "where" | "at" | "the" | "in")
}

fn is_function_word(value: &str) -> bool {
    matches!(
        value,
        "a" | "an"
            | "the"
            | "of"
            | "for"
            | "to"
            | "by"
            | "in"
            | "on"
            | "within"
            | "before"
            | "after"
            | "prior"
            | "that"
            | "this"
            | "such"
            | "be"
            | "been"
            | "being"
            | "is"
            | "are"
            | "was"
            | "were"
            | "it"
            | "its"
            | "said"
            | "at"
            | "least"
    )
}

fn is_legal_marker(value: &str) -> bool {
    matches!(
        value,
        "shall"
            | "may"
            | "must"
            | "where"
            | "if"
            | "when"
            | "provided"
            | "except"
            | "unless"
            | "notwithstanding"
            | "and"
            | "or"
    )
}

fn is_known_verb(value: &str) -> bool {
    matches!(
        value,
        "apply"
            | "approve"
            | "authorize"
            | "certify"
            | "decide"
            | "determine"
            | "ensure"
            | "establish"
            | "extend"
            | "file"
            | "give"
            | "grant"
            | "hold"
            | "impose"
            | "obtain"
            | "permit"
            | "prohibit"
            | "publish"
            | "require"
            | "reverse"
            | "waive"
    )
}

fn is_pronoun(value: &str) -> bool {
    matches!(
        value,
        "he" | "her"
            | "hers"
            | "him"
            | "his"
            | "it"
            | "its"
            | "she"
            | "their"
            | "theirs"
            | "them"
            | "they"
            | "this"
            | "those"
            | "we"
            | "which"
            | "who"
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    const SOURCE: &str = include_str!("../examples/source_50_3_10.txt");

    #[test]
    fn extraction_is_deterministic_and_content_addressed() {
        let first = extract(SourceDocument::new("§50-3-10", SOURCE));
        let second = extract(SourceDocument::new("§50-3-10", SOURCE));
        assert_eq!(first, second);
        assert_eq!(first.extractor_version, EXTRACTOR_VERSION);
    }

    #[test]
    fn every_token_has_structural_or_candidate_coverage() {
        let result = extract(SourceDocument::new("§50-3-10", SOURCE));
        assert!(result.coverage.lexical_coverage_complete);
        assert_eq!(result.tokens.len(), result.token_coverage.len());
        assert!(!result.coverage.semantic_disposition_complete);
        assert_eq!(
            result.coverage.candidate_count,
            result.coverage.unreviewed_candidate_count
        );
    }

    #[test]
    fn extracts_normative_temporal_and_structural_candidates() {
        let result = extract(SourceDocument::new("§50-3-10", SOURCE));
        assert!(result.candidates.iter().any(|candidate| matches!(
            candidate.kind,
            CandidateKind::LegalModality { ref marker } if marker == "shall"
        )));
        assert!(
            result
                .candidates
                .iter()
                .any(|candidate| candidate.kind == CandidateKind::Temporal)
        );
        assert!(
            result
                .candidates
                .iter()
                .any(|candidate| candidate.kind == CandidateKind::SubjectPhrase)
        );
        assert!(
            result
                .candidates
                .iter()
                .any(|candidate| candidate.kind == CandidateKind::PredicatePhrase)
        );
    }

    #[test]
    fn every_candidate_span_round_trips_to_exact_source() {
        let result = extract(SourceDocument::new("§50-3-10", SOURCE));
        for candidate in &result.candidates {
            assert_eq!(
                candidate.text,
                result.source.text[candidate.span.start..candidate.span.end]
            );
        }
    }

    #[test]
    fn broad_phrase_coverage_does_not_hide_lexical_implications() {
        let result = extract(SourceDocument::new("§50-3-10", SOURCE));
        let lexical = |text: &str, hint: LexicalHint| {
            result.candidates.iter().any(|candidate| {
                candidate.text.eq_ignore_ascii_case(text)
                    && matches!(
                        &candidate.kind,
                        CandidateKind::Lexical { hints } if hints.contains(&hint)
                    )
            })
        };
        assert!(lexical("agency", LexicalHint::Noun));
        assert!(lexical("published", LexicalHint::Verb));
        assert!(lexical("it", LexicalHint::Coreference));
    }
}
