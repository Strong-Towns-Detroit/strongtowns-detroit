/**
 * A map is described as data, not written as code.
 *
 * The same MapSpec drives the interactive route and the frozen poster export,
 * which is the only reliable way to stop the two drifting the way the
 * matplotlib exhibits and the website already had.
 */

/** How a feature's colour is derived from its properties. */
export type ColorRule =
  | { kind: "constant"; color: string }
  | {
      kind: "categorical";
      /** Feature property to switch on. */
      field: string;
      palette: Record<string, string>;
      /** Used when the value is missing or unlisted — never silently transparent. */
      fallback: string;
      /**
       * Painting order, bottom first. Assessor parcels overlap (condo splits,
       * related parcels), so whichever is drawn last wins those pixels. Left to
       * tile order, "not evaluated" grey paints over classified parcels and the
       * map under-reports them — measurably: navy fell to 0.84x red when the
       * true area ratio is 1.00. List the states that must never be buried
       * last.
       */
      drawOrder?: string[];
    }
  | {
      /**
       * A binned choropleth: assessed value per acre, land value, and the rest
       * of the quantity maps.
       *
       * The previous shape said "first stop whose `below` exceeds the value
       * wins", which the MapLibre translation implemented backwards — it read
       * as `step`, where anything under the first edge takes the default. The
       * two disagreed in opposite directions and nothing caught it because no
       * published rule used a threshold yet. This shape has one reading.
       */
      kind: "threshold";
      field: string;
      /** Colour for values below `bins[0].from`. */
      belowFirst: string;
      /** Ascending bin edges; each `from` is inclusive. */
      bins: { from: number; color: string }[];
      /** Missing or non-numeric values. Never silently folded into a bin. */
      fallback: string;
    };

export type TileSource = {
  kind: "pmtiles";
  /** Served as a static file; read over HTTP range requests. */
  url: string;
  sourceLayer: string;
};

export type LayerSpec = {
  id: string;
  label: string;
  source: TileSource;
  /** Polygons render filled; lines render stroked. */
  geometry: "polygon" | "line";
  fill?: ColorRule;
  stroke?: { color: ColorRule; widthPx: number };
  opacity?: number;
  /** Extruding turns the same spec into a 3D massing study. */
  extrude?: { field: string; scale: number };
  pickable?: boolean;
  minZoom?: number;
  maxZoom?: number;
};

/** One row of the legend. `note` carries the meaning colour cannot. */
export type LegendEntry = {
  label: string;
  color: string;
  note?: string;
};

/** A field surfaced in the parcel inspector. */
export type InspectField = {
  /** Property name on the picked feature. */
  field: string;
  label: string;
  /** `status` maps a four-state code to its plain-language sentence. */
  format?: "text" | "integer" | "sqft" | "feet" | "currency" | "status";
};

export type ViewState = {
  longitude: number;
  latitude: number;
  zoom: number;
  bearing?: number;
  pitch?: number;
};

export type MapSpec = {
  id: string;
  /** Poster title, also the interactive page heading. */
  title: string;
  subtitle: string;
  view: ViewState;
  /** Optional camera limits, independent of the source tile pyramid. */
  minZoom?: number;
  maxZoom?: number;
  /** Fixed authored tile zoom, when MapLibre overscales one display level. */
  displayTileZoom?: number;
  /**
   * [west, south, east, north]. When present the camera fits these bounds
   * instead of using `view`, so the same spec frames correctly in both the
   * page's flexible viewport and the poster's fixed 1015×680 well.
   */
  bounds?: [number, number, number, number];
  /** Inset in pixels when fitting bounds. */
  fitPadding?: number;
  layers: LayerSpec[];
  legend: LegendEntry[];
  inspect?: {
    /** Layer whose features respond to hover and click. */
    layerId: string;
    /** Property uniquely identifying a feature, for URL state. */
    idField: string;
    titleField: string;
    fields: InspectField[];
    /** Optional full-detail source used only for coordinate lookup. The map
        may paint a separately authored citywide archive. */
    lookupSource?: TileSource;
    lookupZoom?: number;
  };
  /** Source and method lines, rendered at the foot of the poster. */
  sources: string[];
};

/**
 * Numbers the map reports. Computed once in Python and read by both outputs so
 * a figure can never differ between the poster and the page.
 */
export type MapMetric = {
  value: string;
  label: string[];
  detail?: string;
  note?: string[];
};
