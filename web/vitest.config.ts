import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

export default defineConfig({
  plugins: [react()],
  resolve: {
    // Mirror the `@/* -> ./*` path alias from tsconfig.json so imports like
    // `@/lib/api` resolve the same way in tests as they do in the Next.js app.
    alias: {
      "@": fileURLToPath(new URL("./", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    // Only pick up unit tests under lib/; Playwright owns the e2e/ dir.
    include: ["lib/**/*.test.ts", "lib/**/*.test.tsx"],
    coverage: {
      provider: "v8",
      reportsDirectory: "./coverage",
      include: ["lib/**/*.ts"],
      exclude: ["lib/demo-data.ts", "lib/mosaic-cases.ts", "lib/**/*.test.ts"],
    },
  },
});
