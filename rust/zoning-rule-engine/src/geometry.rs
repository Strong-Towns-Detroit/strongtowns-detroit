//! Geometry wrappers carrying shape and coordinate-reference types.

use std::marker::PhantomData;

use serde::{Deserialize, Serialize};

/// Marker implemented by coordinate-reference-system types.
pub trait CoordinateReferenceSystem: Clone + Copy + std::fmt::Debug {
    /// EPSG identifier for the coordinate system.
    const EPSG: u32;
}

/// WGS 84 longitude and latitude.
#[derive(Clone, Copy, Debug)]
pub struct Epsg4326;

impl CoordinateReferenceSystem for Epsg4326 {
    const EPSG: u32 = 4326;
}

/// Michigan South State Plane, the projected CRS used by Detroit source data.
#[derive(Clone, Copy, Debug)]
pub struct Epsg2898;

impl CoordinateReferenceSystem for Epsg2898 {
    const EPSG: u32 = 2898;
}

/// Polygon geometry marker.
#[derive(Clone, Copy, Debug)]
pub struct Polygon;

/// Stable identity of the legal/geospatial measurement method in use.
#[derive(Clone, Debug, Eq, Hash, Ord, PartialEq, PartialOrd, Serialize, Deserialize)]
#[serde(transparent)]
pub struct SpatialPolicyId(pub String);

/// Common distance targets. A policy may further define geometry repair,
/// projection, topology, and boundary inclusion.
#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum DistanceTarget {
    /// Shortest distance between the boundaries of two geometries.
    BoundaryToBoundary,
    /// Distance from a site boundary to a separately defined feature.
    BoundaryToFeature,
    /// Distance between representative centroids.
    CentroidToCentroid,
    /// Radial distance under the named spatial policy.
    Radial,
}

/// Complete identity of a legal spatial measurement method.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SpatialMeasurementPolicy {
    /// Stable policy identity.
    pub id: SpatialPolicyId,
    /// Projected coordinate reference system used for measurement.
    pub epsg: u32,
    /// Geometric objects between which distance is measured.
    pub target: DistanceTarget,
    /// Whether equality with the legal boundary counts as within it.
    pub boundary_inclusive: bool,
}

/// Geometry whose shape and CRS are part of its compile-time type.
#[derive(Clone, Debug)]
pub struct Geometry<Shape, Crs: CoordinateReferenceSystem> {
    coordinates: Vec<[f64; 2]>,
    shape: PhantomData<Shape>,
    crs: PhantomData<Crs>,
}

impl<Shape, Crs: CoordinateReferenceSystem> Geometry<Shape, Crs> {
    /// Constructs a typed geometry from coordinates already expressed in `Crs`.
    #[must_use]
    pub fn new(coordinates: Vec<[f64; 2]>) -> Self {
        Self {
            coordinates,
            shape: PhantomData,
            crs: PhantomData,
        }
    }

    /// Returns the geometry coordinates without erasing their CRS type.
    #[must_use]
    pub fn coordinates(&self) -> &[[f64; 2]] {
        &self.coordinates
    }
}

#[cfg(test)]
mod tests {
    use super::{Epsg2898, Geometry, Polygon};

    #[test]
    fn geometry_retains_coordinates() {
        let parcel = Geometry::<Polygon, Epsg2898>::new(vec![[1.0, 2.0], [3.0, 4.0]]);
        assert_eq!(parcel.coordinates().len(), 2);
    }
}
