import { useEffect, useState } from 'react';

const MOBILE_BREAKPOINT = 768; // Tailwind `md` 와 정렬

/**
 * 뷰포트가 모바일 너비(< md = 768px) 이하인지 반환.
 * Vite SPA(CSR)이므로 useState initializer가 항상 브라우저에서 실행 — SSR 가드 불요.
 * effect는 matchMedia 변경 구독만 담당 (synchronous setState 회피).
 */
export function useIsMobile(breakpoint: number = MOBILE_BREAKPOINT): boolean {
  const [isMobile, setIsMobile] = useState<boolean>(() =>
    window.matchMedia(`(max-width: ${breakpoint - 1}px)`).matches,
  );

  useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${breakpoint - 1}px)`);
    const onChange = () => setIsMobile(mql.matches);
    mql.addEventListener('change', onChange);
    return () => mql.removeEventListener('change', onChange);
  }, [breakpoint]);

  return isMobile;
}
