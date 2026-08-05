"""Geometry model for ordinary rectangular single-family setback envelopes."""

from __future__ import annotations

from dataclasses import dataclass

from shapely.geometry import LineString, Polygon

FRONT_SETBACK_FT = 20
REAR_SETBACK_FT = 30
MINIMUM_SIDE_SETBACK_FT = 4
COMBINED_SIDE_SETBACK_FT = 14
MINIMUM_RECTANGULARITY = 0.90


@dataclass(frozen=True)
class SetbackEnvelope:
    option_left_4: Polygon
    option_right_4: Polygon
    aligned_width_ft: float
    aligned_depth_ft: float
    rectangularity: float


def _world_polygon(
    bounds: tuple[float, float, float, float],
    origin: tuple[float, float],
    tangent: tuple[float, float],
    normal: tuple[float, float],
) -> Polygon:
    min_s, min_d, max_s, max_d = bounds

    def world(s: float, d: float) -> tuple[float, float]:
        return (
            origin[0] + tangent[0] * s + normal[0] * d,
            origin[1] + tangent[1] * s + normal[1] * d,
        )

    return Polygon([
        world(min_s, min_d),
        world(max_s, min_d),
        world(max_s, max_d),
        world(min_s, max_d),
    ])


def single_family_setback_envelope(
    parcel: Polygon,
    front_edge: LineString,
) -> SetbackEnvelope | None:
    """Return the two legal 4/10-foot side-yard allocations.

    The model applies only when the parcel is well represented by a rectangle
    aligned to the identified front edge. The two alternatives reflect the
    ordinance's four-foot minimum on either side and 14-foot combined side
    yard. A proposed principal footprint complies if it fits either option.
    """
    if (
        parcel is None
        or parcel.is_empty
        or front_edge is None
        or front_edge.is_empty
        or front_edge.length <= 0
    ):
        return None
    if parcel.geom_type == "MultiPolygon":
        parcel = max(parcel.geoms, key=lambda part: part.area)
    elif parcel.geom_type != "Polygon":
        return None
    (x1, y1), (x2, y2) = front_edge.coords[0], front_edge.coords[-1]
    length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    tangent = ((x2 - x1) / length, (y2 - y1) / length)
    normal = (-tangent[1], tangent[0])
    origin = ((x1 + x2) / 2, (y1 + y2) / 2)
    representative = parcel.representative_point()
    inward_dot = (
        (representative.x - origin[0]) * normal[0]
        + (representative.y - origin[1]) * normal[1]
    )
    if inward_dot < 0:
        normal = (-normal[0], -normal[1])

    coordinates = list(parcel.exterior.coords)
    projected = [
        (
            (x - origin[0]) * tangent[0] + (y - origin[1]) * tangent[1],
            (x - origin[0]) * normal[0] + (y - origin[1]) * normal[1],
        )
        for x, y in coordinates
    ]
    min_s = min(value[0] for value in projected)
    max_s = max(value[0] for value in projected)
    min_d = min(value[1] for value in projected)
    max_d = max(value[1] for value in projected)
    width, depth = max_s - min_s, max_d - min_d
    if width <= 0 or depth <= 0:
        return None
    rectangularity = parcel.area / (width * depth)
    if rectangularity < MINIMUM_RECTANGULARITY:
        return None
    front = min_d + FRONT_SETBACK_FT
    rear = max_d - REAR_SETBACK_FT
    left_4 = min_s + MINIMUM_SIDE_SETBACK_FT
    right_10 = max_s - (
        COMBINED_SIDE_SETBACK_FT - MINIMUM_SIDE_SETBACK_FT
    )
    left_10 = min_s + (
        COMBINED_SIDE_SETBACK_FT - MINIMUM_SIDE_SETBACK_FT
    )
    right_4 = max_s - MINIMUM_SIDE_SETBACK_FT
    if rear <= front or right_10 <= left_4 or right_4 <= left_10:
        empty = Polygon()
        return SetbackEnvelope(
            empty, empty, width, depth, rectangularity
        )
    return SetbackEnvelope(
        option_left_4=_world_polygon(
            (left_4, front, right_10, rear),
            origin,
            tangent,
            normal,
        ).intersection(parcel),
        option_right_4=_world_polygon(
            (left_10, front, right_4, rear),
            origin,
            tangent,
            normal,
        ).intersection(parcel),
        aligned_width_ft=width,
        aligned_depth_ft=depth,
        rectangularity=rectangularity,
    )


def principal_footprint_outside_area(
    principal_footprint,
    envelope: SetbackEnvelope,
) -> float:
    """Return the smaller violation under the two permissible side options."""
    if principal_footprint is None or principal_footprint.is_empty:
        return float("nan")
    return min(
        principal_footprint.difference(envelope.option_left_4).area,
        principal_footprint.difference(envelope.option_right_4).area,
    )
