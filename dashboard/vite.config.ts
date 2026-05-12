/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import { fileURLToPath, URL } from 'node:url'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    // 무거운 vendor를 별 chunk로 분리 — 캐싱 친화 + route lazy split의 효과 극대화.
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('recharts')) return 'recharts';
            if (id.includes('radix-ui') || id.includes('@radix-ui')) return 'radix';
            if (id.includes('@tanstack')) return 'tanstack';
            if (id.includes('date-fns')) return 'date-fns';
          }
        },
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./vitest.setup.ts'],
    css: false,
    // Playwright e2e specs는 vitest 대상에서 제외 — playwright test 명령으로 별도 실행.
    exclude: ['node_modules', 'dist', 'e2e/**'],
  },
})
