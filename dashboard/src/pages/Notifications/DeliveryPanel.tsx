import { useNotificationDeliveriesQuery } from '@/api/notifications';
import { formatRelativeTime } from '@/lib/time';

export function DeliveryPanel() {
  const deliveriesQuery = useNotificationDeliveriesQuery();
  const deliveries = Array.isArray(deliveriesQuery.data) ? deliveriesQuery.data : [];
  return (
    <div className="bg-card overflow-hidden rounded-lg border">
      {deliveries.length === 0 ? (
        <div className="text-muted-foreground p-6 text-sm">아직 발송 이력이 없습니다</div>
      ) : deliveries.map((delivery) => (
        <div key={delivery.id} className="border-border-1 flex flex-col gap-1 border-t p-4 first:border-t-0 md:flex-row md:items-center md:justify-between">
          <div>
            <span className={delivery.status === 'SUCCESS' ? 'text-emerald-500' : 'text-red-500'}>
              {delivery.status}
            </span>
            <span className="text-muted-foreground ml-2 text-sm">{delivery.channelName ?? '삭제된 채널'}</span>
          </div>
          <div className="text-muted-foreground text-xs">
            {formatRelativeTime(delivery.attemptedAt)}
            {delivery.responseCode ? ` · HTTP ${delivery.responseCode}` : ''}
            {delivery.errorMessage ? ` · ${delivery.errorMessage}` : ''}
          </div>
        </div>
      ))}
    </div>
  );
}
