import type { ReactNode } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';

interface ChartCardProps {
  title: string;
  subtitle?: string;
  empty?: boolean;
  emptyMessage?: string;
  children: ReactNode;
  className?: string;
}

export function ChartCard({
  title,
  subtitle,
  empty = false,
  emptyMessage = '표시할 데이터가 없습니다',
  children,
  className,
}: ChartCardProps) {
  return (
    <Card className={cn('@container/chart flex flex-col', className)}>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold">{title}</CardTitle>
        {subtitle && (
          <div className="text-muted-foreground text-xs">{subtitle}</div>
        )}
      </CardHeader>
      <CardContent className="flex flex-1 items-center justify-center">
        {empty ? (
          <div className="text-muted-foreground flex h-[200px] w-full items-center justify-center text-sm @md/chart:h-[260px]">
            {emptyMessage}
          </div>
        ) : (
          <div className="w-full">{children}</div>
        )}
      </CardContent>
    </Card>
  );
}
