import { type FormEvent, useState } from 'react';
import { CheckCircle2, RotateCw, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';

import {
  useCreateNotificationRuleMutation,
  useNotificationChannelsQuery,
  useNotificationRulesQuery,
} from '@/api/notifications';
import { Button } from '@/components/ui/button';
import { TYPE_OPTIONS } from '@/components/tracker/labels';
import { KNOWN_SOURCES } from '@/lib/sources';
import type { DetectionType, Tier } from '@/types/api';
import { TIERS } from './channelMeta';
import { LabeledInput } from './FormControls';

export function RulePanel() {
  const channelsQuery = useNotificationChannelsQuery();
  const rulesQuery = useNotificationRulesQuery();
  const channels = Array.isArray(channelsQuery.data) ? channelsQuery.data : [];
  const rules = Array.isArray(rulesQuery.data) ? rulesQuery.data : [];
  const createRule = useCreateNotificationRuleMutation();
  const [name, setName] = useState('');
  const [channelId, setChannelId] = useState('');
  const [minConfidence, setMinConfidence] = useState('0.85');
  const [minTier, setMinTier] = useState<Tier | ''>('T2');
  const [detectionType, setDetectionType] = useState<DetectionType | ''>('');
  const [sourceSiteName, setSourceSiteName] = useState('');

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    createRule.mutate(
      {
        name,
        channelId: Number(channelId),
        enabled: true,
        minConfidence: minConfidence ? Number(minConfidence) : null,
        minTier: minTier || null,
        detectionType: detectionType || null,
        sourceSiteName: sourceSiteName || null,
      },
      {
        onSuccess: () => {
          toast.success('알림 규칙을 저장했습니다');
          setName('');
        },
        onError: () => toast.error('알림 규칙 저장에 실패했습니다'),
      },
    );
  };

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(280px,380px)_1fr]">
      <form onSubmit={onSubmit} className="bg-card flex flex-col gap-3 rounded-lg border p-4">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <ShieldCheck className="size-4" />
          규칙 추가
        </div>
        <LabeledInput label="규칙 이름" value={name} onChange={setName} placeholder="고위험 즉시 알림" />
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-muted-foreground text-xs">채널</span>
          <select value={channelId} onChange={(e) => setChannelId(e.target.value)} className="bg-background h-10 rounded-md border px-3">
            <option value="">채널 선택</option>
            {channels.map((channel) => (
              <option key={channel.id} value={channel.id}>{channel.name}</option>
            ))}
          </select>
        </label>
        <LabeledInput label="최소 신뢰도" value={minConfidence} onChange={setMinConfidence} placeholder="0.85" type="number" step="0.01" min="0" max="1" />
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-muted-foreground text-xs">최소 Tier</span>
          <select value={minTier} onChange={(e) => setMinTier(e.target.value as Tier | '')} className="bg-background h-10 rounded-md border px-3">
            <option value="">전체</option>
            {TIERS.map((tier) => <option key={tier} value={tier}>{tier}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-muted-foreground text-xs">유형</span>
          <select value={detectionType} onChange={(e) => setDetectionType(e.target.value as DetectionType | '')} className="bg-background h-10 rounded-md border px-3">
            <option value="">전체</option>
            {TYPE_OPTIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-muted-foreground text-xs">사이트</span>
          <select value={sourceSiteName} onChange={(e) => setSourceSiteName(e.target.value)} className="bg-background h-10 rounded-md border px-3">
            <option value="">전체</option>
            {KNOWN_SOURCES.map((source) => <option key={source} value={source}>{source}</option>)}
          </select>
        </label>
        <Button type="submit" disabled={!name || !channelId || createRule.isPending}>
          {createRule.isPending ? <RotateCw className="animate-spin" /> : <CheckCircle2 />}
          저장
        </Button>
      </form>

      <div className="grid gap-3">
        {rules.length === 0 ? (
          <div className="text-muted-foreground bg-card rounded-lg border p-6 text-sm">등록된 알림 규칙이 없습니다</div>
        ) : rules.map((rule) => (
          <div key={rule.id} className="bg-card rounded-lg border p-4">
            <div className="flex items-center justify-between gap-3">
              <span className="font-medium">{rule.name}</span>
              <span className="text-muted-foreground text-xs">{rule.channelName}</span>
            </div>
            <div className="text-muted-foreground mt-2 text-xs">
              confidence ≥ {rule.minConfidence ?? '전체'} · tier ≤ {rule.minTier ?? '전체'} · {rule.detectionType ?? '모든 유형'} · {rule.sourceSiteName ?? '모든 사이트'}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
