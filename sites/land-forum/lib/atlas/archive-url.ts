/** Large archives can be served by a range-enabled static/object host. */
export function parcelArchiveUrl(configured?: string): string {
  if (!configured) return "/data/zoning/parcels.pmtiles";
  const url = new URL(configured);
  if (url.protocol !== "https:" || url.username || url.password) {
    throw new Error("NEXT_PUBLIC_PARCEL_ARCHIVE_URL must be an HTTPS URL without credentials.");
  }
  return url.href;
}
export const PARCEL_ARCHIVE_URL = parcelArchiveUrl(process.env.NEXT_PUBLIC_PARCEL_ARCHIVE_URL);
