import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider } from 'react-router-dom';
import { toast } from 'sonner';
import { registerSW } from 'virtual:pwa-register';
import { Toaster } from '@/components/ui/sonner';
import { GlobalShortcutProvider } from '@/lib/shortcuts';
import { router } from './router';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

async function enableMocking() {
  if (!import.meta.env.DEV) return;
  const { worker } = await import('./mocks/browser');
  await worker.start({ onUnhandledRequest: 'bypass' });
}

// PWA service worker registration — prod 빌드에서만 active.
// dev에선 MSW가 fetch를 가로채야 하므로 SW 미등록 (vite.config의 devOptions.enabled=false).
const updateSW = registerSW({
  onNeedRefresh() {
    toast.info('새 버전이 있습니다', {
      duration: Infinity,
      action: { label: '업데이트', onClick: () => updateSW(true) },
    });
  },
  onOfflineReady() {
    toast.success('오프라인에서도 사용 가능합니다', { duration: 3000 });
  },
});

enableMocking().then(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <GlobalShortcutProvider>
          <RouterProvider router={router} />
          <Toaster position="top-right" richColors closeButton />
        </GlobalShortcutProvider>
      </QueryClientProvider>
    </StrictMode>,
  );
});
