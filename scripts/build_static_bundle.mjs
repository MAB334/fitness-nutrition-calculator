import { cp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..");
const staticRoot = path.join(repoRoot, "nutrition_app", "static");
const publicRoot = path.join(repoRoot, "public");

async function main() {
  await rm(publicRoot, { recursive: true, force: true });
  await mkdir(path.join(publicRoot, "static"), { recursive: true });

  const indexSource = path.join(staticRoot, "index.html");
  const indexTarget = path.join(publicRoot, "index.html");
  const rawIndex = await readFile(indexSource, "utf8");
  await writeFile(indexTarget, rawIndex, "utf8");

  for (const entry of await listEntries(staticRoot)) {
    if (entry === "index.html") {
      continue;
    }
    await cp(path.join(staticRoot, entry), path.join(publicRoot, "static", entry), {
      recursive: true,
    });
  }

  console.log("Prepared EdgeOne static bundle.");
}

async function listEntries(directory) {
  const { readdir } = await import("node:fs/promises");
  return readdir(directory);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
