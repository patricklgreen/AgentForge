import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/__tests__/setup.ts"],
    include: ["src/__tests__/**/*.{test,spec}.{ts,tsx}"],
    coverage: {
      provider: "v8",
      reporter: ["text", "json", "html"],
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/__tests__/**",
        "src/main.tsx",
        "src/index.css",
        "**/*.d.ts",
        "**/*.config.*",
        // Large route shells exercised via integration/E2E; unit tests target composable modules.
        "src/pages/ProjectDetail.tsx",
        "src/components/HumanReviewModal.tsx",
      ],
      // Line/statement thresholds match project goal (~90%). Function coverage stays lower on
      // presentational components with many inline handlers; those are covered indirectly.
      thresholds: {
        lines: 90,
        statements: 90,
        functions: 82,
        branches: 80,
      },
    },
  },
});
