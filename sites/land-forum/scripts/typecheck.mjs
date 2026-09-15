import { readFile, writeFile } from "node:fs/promises";
import { spawnSync } from "node:child_process";

// Next generates the route declarations, but must not remove vinext's augmentation.
const original = await readFile("next-env.d.ts", "utf8");
let result;
try {
  result = spawnSync(process.execPath, ["node_modules/next/dist/bin/next", "typegen"], { stdio: "inherit" });
} finally {
  await writeFile("next-env.d.ts", original);
}
if (result.status !== 0) process.exit(result.status ?? 1);
const checked = spawnSync(process.execPath, ["node_modules/typescript/bin/tsc", "--noEmit", "--incremental", "false"], { stdio: "inherit" });
process.exit(checked.status ?? 1);
