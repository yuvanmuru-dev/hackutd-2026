// Copies the six @vladmandic/human models the face check uses into public/face-models (gitignored),
// so the browser loads them from this site instead of a CDN. Never fails the build.
import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { join } from "node:path";

const src = join("node_modules", "@vladmandic", "human", "models");
const dst = join("public", "face-models");
const models = ["blazeface", "facemesh", "faceres", "antispoof", "liveness", "iris"];
try {
  if (!existsSync(src)) process.exit(0);
  mkdirSync(dst, { recursive: true });
  for (const m of models) for (const ext of [".json", ".bin"]) copyFileSync(join(src, m + ext), join(dst, m + ext));
} catch (e) {
  console.warn("face models not copied:", e.message);
}
