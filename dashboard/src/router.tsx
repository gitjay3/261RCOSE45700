import { lazy } from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { ErrorBoundary } from './components/common/ErrorBoundary';
import { RootLayout } from './layouts/RootLayout';
import { DashboardPage } from './pages/Dashboard';

// Dashboard는 첫 진입 LCP라 eager. 나머지는 lazy split — RootLayout의 Suspense가 fallback 책임.
const DetectionListPage = lazy(() =>
  import('./pages/DetectionList').then((m) => ({ default: m.DetectionListPage })),
);
const DetectionDetailPage = lazy(() =>
  import('./pages/DetectionDetail').then((m) => ({ default: m.DetectionDetailPage })),
);
const NotificationsPage = lazy(() =>
  import('./pages/Notifications').then((m) => ({ default: m.NotificationsPage })),
);

export const router = createBrowserRouter([
  {
    path: '/',
    element: <RootLayout />,
    errorElement: <ErrorBoundary />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'detections', element: <DetectionListPage /> },
      { path: 'detections/:id', element: <DetectionDetailPage /> },
      { path: 'stats', element: <Navigate to="/" replace /> },
      { path: 'notifications', element: <NotificationsPage /> },
    ],
  },
]);
