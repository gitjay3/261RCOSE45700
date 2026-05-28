import { type FormEvent, useState } from 'react';
import { BellRing, CheckCircle2, ExternalLink, FlaskConical, RadioTower, RotateCw } from 'lucide-react';
import { toast } from 'sonner';

import {
  useCreateNotificationChannelMutation,
  useNotificationChannelsQuery,
  useTestNotificationChannelMutation,
} from '@/api/notifications';
import { Button } from '@/components/ui/button';
import { formatRelativeTime } from '@/lib/time';
import type { NotificationChannelType } from '@/types/api';
import { CHANNEL_GROUPS, CHANNEL_TYPES, metaForChannel } from './channelMeta';
import { LabeledInput } from './FormControls';

export function ChannelPanel() {
  const channelsQuery = useNotificationChannelsQuery();
  const channels = Array.isArray(channelsQuery.data) ? channelsQuery.data : [];
  const createChannel = useCreateNotificationChannelMutation();
  const testChannel = useTestNotificationChannelMutation();
  const [name, setName] = useState('');
  const [type, setType] = useState<NotificationChannelType>('DISCORD');
  const [webhookUrl, setWebhookUrl] = useState('');
  const selectedType = metaForChannel(type);

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    createChannel.mutate(
      { name, type, webhookUrl, enabled: true },
      {
        onSuccess: () => {
          toast.success('알림 채널을 저장했습니다');
          setName('');
          setWebhookUrl('');
        },
        onError: () => toast.error('알림 채널 저장에 실패했습니다'),
      },
    );
  };

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(280px,380px)_1fr]">
      <form onSubmit={onSubmit} className="bg-card flex flex-col gap-3 rounded-lg border p-4">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <RadioTower className="size-4" />
          채널 연결
        </div>
        <div className="text-muted-foreground rounded-md border bg-bg-overlay px-3 py-2 text-xs leading-relaxed">
          연동 방식은 Webhook URL입니다. 각 서비스에서 복사한 전체 URL을 붙여넣으면
          Tracker 서버가 해당 URL로 알림 JSON을 전송합니다.
        </div>
        <LabeledInput label="이름" value={name} onChange={setName} placeholder="보안팀 Discord" />
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-muted-foreground text-xs">채널 타입</span>
          <select
            value={type}
            onChange={(e) => setType(e.target.value as NotificationChannelType)}
            className="bg-background h-10 rounded-md border px-3"
          >
            {CHANNEL_GROUPS.map((group) => (
              <optgroup key={group} label={group}>
                {CHANNEL_TYPES.filter((item) => item.group === group).map((item) => (
                  <option key={item.value} value={item.value}>{item.label}</option>
                ))}
              </optgroup>
            ))}
          </select>
          <span className="text-muted-foreground text-xs leading-relaxed">
            {selectedType.helper}
          </span>
        </label>
        <div className="grid gap-2">
          <Button type="button" variant="outline" className="h-auto min-h-8 justify-start whitespace-normal py-2 text-left leading-snug" asChild>
            <a href={selectedType.setupUrl} target="_blank" rel="noreferrer">
              <ExternalLink className="mt-0.5 shrink-0" />
              <span className="min-w-0">{selectedType.setupLabel}</span>
            </a>
          </Button>
          <Button type="button" variant="secondary" className="h-auto min-h-8 justify-start whitespace-normal py-2 text-left leading-snug" asChild>
            <a href={selectedType.openUrl} target="_blank" rel="noreferrer">
              <ExternalLink className="mt-0.5 shrink-0" />
              <span className="min-w-0">{selectedType.openLabel}</span>
            </a>
          </Button>
        </div>
        <LabeledInput
          label="Webhook URL"
          value={webhookUrl}
          onChange={setWebhookUrl}
          placeholder={selectedType.placeholder}
        />
        <Button type="submit" disabled={!name || !webhookUrl || createChannel.isPending}>
          {createChannel.isPending ? <RotateCw className="animate-spin" /> : <CheckCircle2 />}
          저장
        </Button>
      </form>

      <div className="grid gap-3">
        {channelsQuery.isLoading ? (
          <div className="text-muted-foreground bg-card rounded-lg border p-6 text-sm">채널을 불러오는 중</div>
        ) : channels.length === 0 ? (
          <div className="text-muted-foreground bg-card rounded-lg border p-6 text-sm">연결된 알림 채널이 없습니다</div>
        ) : (
          channels.map((channel) => (
            <div key={channel.id} className="bg-card flex flex-col gap-3 rounded-lg border p-4 md:flex-row md:items-center md:justify-between">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <BellRing className="size-4 text-accent" />
                  <span className="font-medium">{channel.name}</span>
                  <span className="text-muted-foreground rounded border px-1.5 py-0.5 text-xs">{metaForChannel(channel.type).label}</span>
                </div>
                <div className="text-muted-foreground mt-1 font-mono text-xs">{channel.configPreview}</div>
                <div className="text-muted-foreground mt-1 text-xs">
                  마지막 성공 {channel.lastSuccessAt ? formatRelativeTime(channel.lastSuccessAt) : '없음'}
                  {' · '}
                  마지막 실패 {channel.lastFailureAt ? formatRelativeTime(channel.lastFailureAt) : '없음'}
                </div>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={testChannel.isPending}
                onClick={() => testChannel.mutate(channel.id, {
                  onSuccess: (result) => {
                    if (result.success) toast.success('테스트 알림을 보냈습니다');
                    else toast.error(result.errorMessage ?? '테스트 알림 발송 실패');
                  },
                  onError: () => toast.error('테스트 요청에 실패했습니다'),
                })}
              >
                <FlaskConical />
                테스트
              </Button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
