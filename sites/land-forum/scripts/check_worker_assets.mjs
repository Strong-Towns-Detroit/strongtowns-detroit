import { readdir, stat } from "node:fs/promises";
import { join } from "node:path";
const root = process.argv[2] ?? "dist/client";
async function oversized(directory) {
  const failures = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) failures.push(...await oversized(path));
    else if ((await stat(path)).size > 25 * 1024 * 1024) failures.push(path);
  }
  return failures;
}
const failures = await oversized(root);
if (failures.length) {
  console.error(`Workers assets exceed 25 MiB:\n${failures.join("\n")}\nReduce or separately host oversized assets before deployment. No upload was attempted.`);
  process.exitCode = 1;
}
