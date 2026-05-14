/// <reference types="vitest/config" />
import { unlinkSync } from 'node:fs'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig, type PluginOption } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

/**
 * MSW worker(`public/mockServiceWorker.js`)는 dev 전용이지만 vite는 `public/` 자산을
 * 자동으로 dist/에 복사. workbox `globIgnores`로 precache에서는 빠지지만 파일 자체는
 * 50KB로 dist/에 남는다 → production에서 dev-only worker가 공개 경로에 노출됨.
 * build closeBundle 훅에서 실제 파일을 제거해 dist/에 흔적이 안 남도록 한다.
 *
 * 단 VITE_USE_MOCK=true 빌드는 의도적으로 MSW를 prod에 포함하는 데모 모드 →
 * worker 파일을 dist/에 보존해 클라이언트에서 MSW가 정상 등록되도록 한다.
 */
const removeDevMswWorker = (): PluginOption => ({
  name: 'tracker:remove-dev-msw-worker',
  apply: 'build',
  // `order: 'pre'`로 vite-plugin-pwa(enforce: 'post')보다 먼저 실행되도록 명시 →
  // workbox가 dist/를 스캔하기 전에 파일이 사라져 globIgnores는 redundant safety net.
  closeBundle: {
    order: 'pre',
    handler() {
      if (process.env.VITE_USE_MOCK === 'true') return;
      try {
        unlinkSync(fileURLToPath(new URL('./dist/mockServiceWorker.js', import.meta.url)))
      } catch {
        // 파일이 이미 없으면 무시 (다른 빌드 환경 호환).
      }
    },
  },
})

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      // 사용자에게 업데이트 prompt — 운영 도구 특성상 silent auto-update보다 명시적 갱신이 안전.
      registerType: 'prompt',
      // MSW dev worker(public/mockServiceWorker.js)는 dev only. production SW와 scope 다름.
      includeAssets: ['favicon.svg'],
      manifest: {
        name: 'Tracker — 불법 프로그램 탐지',
        short_name: 'Tracker',
        description: '게임 커뮤니티 불법 프로그램 유포 탐지 운영 도구',
        theme_color: '#0a5273', // brand cyan deep (oklch 0.50 0.08 215 근사값)
        background_color: '#f6f5f8', // light bg token 근사값
        display: 'standalone',
        orientation: 'portrait',
        lang: 'ko',
        scope: '/',
        start_url: '/',
        icons: [
          { src: 'favicon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any maskable' },
        ],
      },
      workbox: {
        // dev-only MSW worker는 production precache에 포함하지 않음. glob convention상
        // 디렉토리 무관 매칭을 위해 `**/` 접두 사용 (workbox-build glob 표준).
        globIgnores: ['**/mockServiceWorker.js'],
        // API 응답은 캐시 X — 운영 데이터는 항상 최신. 정적 자산만 캐시.
        navigateFallbackDenylist: [/^\/api/],
        runtimeCaching: [
          {
            urlPattern: ({ request }) => request.destination === 'image' || request.destination === 'font',
            handler: 'CacheFirst',
            options: {
              cacheName: 'static-assets',
              expiration: { maxEntries: 60, maxAgeSeconds: 60 * 60 * 24 * 30 },
            },
          },
        ],
      },
      devOptions: {
        enabled: false, // dev에서는 MSW worker가 우선. PWA SW는 prod build에서만.
      },
    }),
    removeDevMswWorker(),
  ],
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
