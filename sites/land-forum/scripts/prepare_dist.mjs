import { existsSync } from "node:fs";
import { cp, mkdir, rm } from "node:fs/promises";

if (existsSync(".openai/hosting.json")) {
  await mkdir("dist/.openai", { recursive: true });
  await cp(".openai/hosting.json", "dist/.openai/hosting.json");
}

// BZA-only deployment: omit preserved development assets for removed exhibits.
for (const directory of ["data/zoning", "data/parcel-geometry", "data/assessed-value", "vendor/maplibre-gl", "exhibits"]) {
  await rm(`dist/client/${directory}`, { recursive: true, force: true });
}
