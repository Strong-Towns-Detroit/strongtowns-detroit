//! Exact, content-addressed provenance for legal propositions.

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use thiserror::Error;

/// SHA-256 digest of an exact legal source span.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(transparent)]
pub struct SpanDigest(String);

impl SpanDigest {
    /// Digests an exact source quote.
    #[must_use]
    pub fn of(quote: &str) -> Self {
        Self(format!("{:x}", Sha256::digest(quote.as_bytes())))
    }
}

/// A half-open range in one immutable source block.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SourceSpan {
    /// Immutable source snapshot identifier.
    pub snapshot: String,
    /// Source document identifier.
    pub document: String,
    /// Stable source node identifier.
    pub node_id: String,
    /// Character offset at which the quote begins.
    pub start: usize,
    /// Character offset immediately after the quote.
    pub end: usize,
    /// Exact source text.
    pub quote: String,
    /// Content digest of `quote`.
    pub digest: SpanDigest,
}

/// A source span no longer matches its immutable declaration.
#[derive(Clone, Debug, Error, Eq, PartialEq)]
pub enum ProvenanceError {
    /// Range does not select a nonempty portion of the source block.
    #[error("source range is invalid")]
    InvalidRange,
    /// Text or digest differs from the reviewed declaration.
    #[error("source span changed or was occluded")]
    SourceChanged,
}

impl SourceSpan {
    /// Creates a cited span from an immutable source block.
    ///
    /// # Errors
    ///
    /// Returns [`ProvenanceError::InvalidRange`] when the offsets do not select
    /// a nonempty UTF-8 substring of `source`.
    pub fn cite(
        snapshot: impl Into<String>,
        document: impl Into<String>,
        node_id: impl Into<String>,
        source: &str,
        start: usize,
        end: usize,
    ) -> Result<Self, ProvenanceError> {
        let quote = source
            .get(start..end)
            .filter(|value| !value.is_empty())
            .ok_or(ProvenanceError::InvalidRange)?
            .to_owned();
        let digest = SpanDigest::of(&quote);
        Ok(Self {
            snapshot: snapshot.into(),
            document: document.into(),
            node_id: node_id.into(),
            start,
            end,
            quote,
            digest,
        })
    }

    /// Verifies this span against its source block.
    ///
    /// # Errors
    ///
    /// Returns [`ProvenanceError::SourceChanged`] when the range is absent or
    /// its quote or digest differs from the reviewed declaration.
    pub fn verify(&self, source: &str) -> Result<(), ProvenanceError> {
        let actual = source
            .get(self.start..self.end)
            .ok_or(ProvenanceError::SourceChanged)?;
        if actual == self.quote && SpanDigest::of(actual) == self.digest {
            Ok(())
        } else {
            Err(ProvenanceError::SourceChanged)
        }
    }
}
