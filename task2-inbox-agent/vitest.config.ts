import { defineConfig } from "vitest/config";
import path from "node:path";

export default defineConfig({
  test: {
    globals: true,
    environment: "node",
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    deps: {
      external: [/^node:/],
    },
  },
  ssr: {
    external: ["node:sqlite"],
  },
});
