import type { LucideIcon } from 'lucide-react';
import {
  AlertTriangle, Banknote, Bot, Circle, Download,
  Megaphone, RefreshCw, Server, ShoppingCart,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { DetectionType } from '@/types/api';
import { getTypeLabel } from './labels';

const ICON_MAP: Record<DetectionType, LucideIcon> = {
  핵_치트: AlertTriangle,
  사설서버: Server,
  불법프로그램_배포: Download,
  계정_거래: ShoppingCart,
  매크로_판매: Bot,
  리세마라: RefreshCw,
  현금화: Banknote,
  광고_도배: Megaphone,
  기타: Circle,
};

interface TypeIconProps {
  type: DetectionType;
  /** Render icon with text label. Default true for accessibility. */
  showLabel?: boolean;
  className?: string;
}

export function TypeIcon({ type, showLabel = true, className }: TypeIconProps) {
  const Icon = ICON_MAP[type] ?? Circle; // 알 수 없는 타입은 Circle로 폴백
  const label = getTypeLabel(type) ?? type;

  if (!showLabel) {
    return (
      <Icon
        aria-label={label}
        className={cn('text-muted-foreground size-4', className)}
      />
    );
  }

  return (
    <span className={cn('inline-flex items-center gap-1.5 text-sm', className)}>
      <Icon aria-hidden className="text-muted-foreground size-4 shrink-0" />
      <span>{label}</span>
    </span>
  );
}
