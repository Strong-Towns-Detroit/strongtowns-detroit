/**
 * The frozen poster layout, at the same 1600×1100 geometry as the printed
 * conference exhibits.
 *
 * The chrome is real DOM text rather than the generated SVG strings in
 * exhibit_components.py, so it stays selectable, translatable, and screen-
 * readable — but the composition (title at x=52/y=116, map at 48,205 sized
 * 1015×680, legend baseline 918, right column at x=1120, sources from y=1038)
 * is deliberately identical, so a frozen export drops into the existing
 * exhibit set without looking retrofitted.
 */

import type { ReactNode } from "react";
import { exhibit } from "../tokens";
import type { LegendEntry, MapMetric } from "./types";

const { width, height, map, column } = exhibit;

export function Masthead() {
  return (
    <div className="ex-masthead">
      {/* The Detroit flag sprite cropped from the official lockup, matching
          exhibit_brand.py rather than approximating it with CSS. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img className="ex-flag" src="/strong-towns-flag.png" alt="" width={27} height={27} />
      <span className="ex-kicker">
        STRONG TOWNS DETROIT · DETROIT LAND USE FORUM
      </span>
    </div>
  );
}

export function TitleBlock({
  title,
  subtitle,
}: {
  title: string;
  subtitle: string;
}) {
  return (
    <div className="ex-title-block">
      <h1 className="ex-title">{title}</h1>
      <p className="ex-dek">{subtitle}</p>
    </div>
  );
}

export function MetricBlock({ metric }: { metric: MapMetric }) {
  return (
    <div className="ex-metric-block">
      <div className="ex-metric">{metric.value}</div>
      {metric.label.map((line) => (
        <div className="ex-metric-label" key={line}>
          {line}
        </div>
      ))}
      {metric.detail && <p className="ex-note ex-metric-detail">{metric.detail}</p>}
      {metric.note && (
        <p className="ex-note ex-metric-note">{metric.note.join(" ")}</p>
      )}
    </div>
  );
}

/**
 * Legend entries carry an optional note because the accessibility rule for
 * this project is that rule status is never encoded by colour alone.
 *
 * The board suppresses the notes: at fixed column positions they run into the
 * next entry, and each label already states the status in words. The
 * interactive panel, which has room to stack, shows them.
 */
export function Legend({
  entries,
  columns,
  rows,
  showNotes = true,
}: {
  entries: LegendEntry[];
  columns?: number[];
  /**
   * Column positions per row, entries consumed in order. A seven-band
   * choropleth does not fit on one line at board width, and the printed
   * exhibits wrap it rather than shrinking the type.
   */
  rows?: number[][];
  showNotes?: boolean;
}) {
  if (rows) {
    let cursor = 0;
    return (
      <>
        {rows.map((positions, rowIndex) => {
          const slice = entries.slice(cursor, cursor + positions.length);
          cursor += positions.length;
          return (
            <ul
              className="ex-legend"
              key={rowIndex}
              style={{ top: 918 + rowIndex * 40 }}
            >
              {slice.map((entry, index) => (
                <li key={entry.label} style={{ left: `${positions[index]}px` }}>
                  <span
                    className="ex-swatch"
                    style={{ background: entry.color }}
                  />
                  <span>{entry.label}</span>
                </li>
              ))}
            </ul>
          );
        })}
      </>
    );
  }
  return (
    <ul className="ex-legend">
      {entries.map((entry, index) => (
        <li
          key={entry.label}
          style={columns ? { left: `${columns[index]}px` } : undefined}
        >
          <span className="ex-swatch" style={{ background: entry.color }} />
          <span>
            {entry.label}
            {showNotes && entry.note && (
              <em className="ex-legend-note"> — {entry.note}</em>
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function SourceLines({ lines }: { lines: string[] }) {
  return (
    <div className="ex-sources">
      {lines.map((line) => (
        <p key={line}>{line}</p>
      ))}
    </div>
  );
}

/**
 * `scale` renders the poster smaller on screen without changing its layout —
 * the export mounts it at scale 1 and captures at 2× device pixel ratio to
 * reach the 3200px wide PNG the print bundle already produces.
 */
export default function ExhibitFrame({
  title,
  subtitle,
  metric,
  legend,
  legendColumns,
  legendRows,
  legendNotes = false,
  sources,
  children,
  aside,
  scale = 1,
}: {
  title: string;
  subtitle: string;
  metric?: MapMetric;
  legend: LegendEntry[];
  legendColumns?: number[];
  legendRows?: number[][];
  legendNotes?: boolean;
  sources: string[];
  children: ReactNode;
  aside?: ReactNode;
  scale?: number;
}) {
  return (
    <div
      className="ex-frame-outer"
      style={{
        width: width * scale,
        height: height * scale,
      }}
    >
      <div
        className="ex-frame"
        style={{
          width,
          height,
          transform: scale === 1 ? undefined : `scale(${scale})`,
        }}
      >
        <Masthead />
        <TitleBlock title={title} subtitle={subtitle} />

        <div
          className="ex-map"
          style={{
            left: map.x,
            top: map.y,
            width: map.width,
            height: map.height,
          }}
        >
          {children}
        </div>

        <Legend
          entries={legend}
          columns={legendColumns}
          rows={legendRows}
          showNotes={legendNotes}
        />

        <div className="ex-column" style={{ left: column.x }}>
          {metric && <MetricBlock metric={metric} />}
          {aside}
        </div>

        <SourceLines lines={sources} />
      </div>
    </div>
  );
}
