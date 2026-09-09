import { existsSync } from "node:fs";
import { cp, mkdir, rm } from "node:fs/promises";

if (existsSync(".openai/hosting.json")) {
  await mkdir("dist/.openai", { recursive: true });
  await cp(".openai/hosting.json", "dist/.openai/hosting.json");
}

if (process.env.NEXT_PUBLIC_PARCEL_ARCHIVE_URL) {
  const url = new URL(process.env.NEXT_PUBLIC_PARCEL_ARCHIVE_URL);
  if (url.protocol !== "https:" || url.username || url.password) throw new Error("Invalid parcel archive URL");
  // The browser uses the configured archive; omit the oversized local duplicate.
  await rm("dist/client/data/zoning/parcels.pmtiles", { force: true });
}
