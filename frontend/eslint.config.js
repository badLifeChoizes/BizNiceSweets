// ABOUTME: ESLint 10 flat config for the frontend — composes @eslint/js recommended,
// ABOUTME: typescript-eslint recommended, react-hooks recommended and react-refresh (Vite),
// ABOUTME: preserving the underscore-prefixed unused-args tweak from the legacy .eslintrc.cjs.

import js from '@eslint/js'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['dist', 'coverage'] },
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
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
