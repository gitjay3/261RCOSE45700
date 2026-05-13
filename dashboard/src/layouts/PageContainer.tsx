import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface PageContainerProps {
  children: ReactNode;
  className?: string;
}

/** 모든 페이지의 외곽 wrapper — 3-col main 안에서 동일 호흡 (`var(--pad-page)`). */
export function PageContainer({ children, className }: PageContainerProps) {
  return (
    <div
      className={cn('mx-auto flex w-full max-w-[1300px] flex-col', className)}
      style={{
        // 하단에 safe-area-bottom 추가 — iOS 홈 인디케이터 침범 회피.
        padding: 'var(--pad-page)',
        paddingBottom: 'calc(var(--pad-page) + var(--sab))',
      }}
    >
      {children}
    </div>
  );
}
