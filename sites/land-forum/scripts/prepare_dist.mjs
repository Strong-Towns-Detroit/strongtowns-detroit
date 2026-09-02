import { existsSync } from "node:fs";
import { cp, mkdir } from "node:fs/promises";

if (existsSync(".openai/hosting.json")) {
  await mkdir("dist/.openai", { recursive: true });
  await cp(".openai/hosting.json", "dist/.openai/hosting.json");
}
