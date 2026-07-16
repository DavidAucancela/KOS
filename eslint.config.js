// Config compartida de ESLint (doc 09 §3). Cubre apps/web; los paquetes JS
// futuros añaden aquí sus propios bloques.
import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    ignores: [
      "**/dist/**",
      "**/node_modules/**",
      "**/coverage/**",
      "apps/web/src/api/schema.d.ts",
    ],
  },
  {
    files: ["apps/web/**/*.{ts,tsx}"],
    extends: [
      js.configs.recommended,
      ...tseslint.configs.recommended,
      reactHooks.configs["recommended-latest"],
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2023,
      globals: globals.browser,
    },
  },
  {
    // Convención shadcn/ui: estos módulos exportan también variantes (cva),
    // no solo componentes.
    files: ["apps/web/src/components/ui/**"],
    rules: { "react-refresh/only-export-components": "off" },
  },
);
