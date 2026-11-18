import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
const require = createRequire(new URL("../package.json", import.meta.url));
/** Bundle actual TSX for Node contract tests without maintaining a parallel implementation. */
export function actualSource(path) {
  const output = require("esbuild").buildSync({
    entryPoints: [fileURLToPath(new URL(path, import.meta.url))],
    bundle: true,
    platform: "node",
    format: "cjs",
    write: false,
    logLevel: "silent",
    jsx: "automatic",
    external: [
      "react",
      "react-dom",
      "react-dom/server",
      "react-dom/client",
      "react/jsx-runtime",
      "react-router",
    ],
  }).outputFiles[0].text;
  const module = { exports: {} };
  new Function("require", "module", "exports", output)(
    require,
    module,
    module.exports,
  );
  return module.exports;
}
