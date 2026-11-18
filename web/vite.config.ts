import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath } from "node:url";
const outDir = process.env.SIRE_BUILD_DIR || "dist";
if (!["dist", "dist-v3"].includes(outDir))
  throw new Error("SIRE_BUILD_DIR must be dist or dist-v3");
export default defineConfig({
  plugins: [tailwindcss()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  build: { assetsDir: "static", outDir },
  server: { proxy: { "/api": { target: "http://127.0.0.1:8000", ws: true } } },
});
