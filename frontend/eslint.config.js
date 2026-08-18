// ABOUTME: ESLint 10 flat config for the frontend — composes @eslint/js recommended,
// ABOUTME: typescript-eslint recommended, react-hooks recommended and react-refresh (Vite),
// ABOUTME: preserving the underscore-prefixed unused-args tweak from the legacy .eslintrc.cjs.
// ABOUTME: A second block gates plain JS (this file included) so the config lints itself.

import js from '@eslint/js'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['dist', 'coverage'] },
  {
    // Plain JS/MJS/CJS — this config file is the only such file today, and until
    // this block existed it fell outside the `**/*.{ts,tsx}` block below, so NOT
    // ONE rule applied to it: the lint config was the one unlinted file in the
    // frontend, and any future .js/.mjs added anywhere here would have been
    // silently ungated too (v4.0 milestone audit, GAP-8).
    files: ['**/*.{js,mjs,cjs}'],
    extends: [js.configs.recommended],
    languageOptions: {
      ecmaVersion: 2020,
      sourceType: 'module',
    },
  },
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs['recommended-latest'],
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
    },
    rules: {
      // Preserve the legacy .eslintrc.cjs tweak: allow intentionally-unused
      // args/vars prefixed with an underscore.
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
    },
  },
)
