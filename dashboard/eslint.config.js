import js from '@eslint/js'
import globals from 'globals'
import eslintReact from '@eslint-react/eslint-plugin'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
      // dom-recommended는 a11y(aria-*, role, alt, label) + React DOM 안전 룰 포함.
      eslintReact.configs['recommended-typescript'],
    ],
    languageOptions: {
      globals: globals.browser,
    },
  },
  {
    // shadcn/ui 컴포넌트는 cva variants를 컴포넌트와 함께 export하는 패턴이 표준.
    // router.tsx는 lazy()로 컴포넌트 변수 + router 객체를 동시 export (fast-refresh
    // 영향 없음, 모듈 단위 1회 평가). 두 파일군 모두 룰 완화.
    files: ['src/components/ui/**/*.{ts,tsx}', 'src/router.tsx'],
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
])
