export const STATUS_LABELS: Record<string, string> = {
  below: "Would require relief under today's standard",
  meets: "Meets the minimum as measured",
  unknown: "Not enough information to evaluate",
  outside: "Outside R1–R6, or the rule does not apply",
};

/** Keep identifiers verbatim and distinguish absent evidence from recorded zero. */
export function formatMeasure(
  value: unknown,
  format: string | undefined,
  allowZero = false,
): string {
  if (value == null || value === "") return "Not recorded";
  if (format === "text" || format === undefined) return String(value);
  if (format === "status") return STATUS_LABELS[String(value)] ?? String(value);
  const n = Number(value);
  if (!Number.isFinite(n) || n < 0 || (n === 0 && !allowZero && format !== "currency" && format !== "integer")) return "Not recorded";
  if (format === "sqft") return `${n.toLocaleString()} sq. ft.`;
  if (format === "feet") return `${n.toLocaleString()} ft.`;
  if (format === "currency") return `$${n.toLocaleString()}`;
  return String(value);
}
