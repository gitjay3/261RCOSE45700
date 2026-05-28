import { type FormEvent, type InputHTMLAttributes, useState } from 'react';
import { BellRing, CheckCircle2, ExternalLink, FlaskConical, RadioTower, RotateCw, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';
import {
  useCreateNotificationChannelMutation,
  useCreateNotificationRuleMutation,
  useNotificationChannelsQuery,
  useNotificationDeliveriesQuery,
  useNotificationRulesQuery,
  useTestNotificationChannelMutation,
} from '@/api/notifications';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { TYPE_OPTIONS } from '@/components/tracker/labels';
import { PageContainer } from '@/layouts/PageContainer';
import { KNOWN_SOURCES } from '@/lib/sources';
import { formatRelativeTime } from '@/lib/time';
import type { DetectionType, NotificationChannelType, Tier } from '@/types/api';

const CHANNEL_TYPES: Array<{
  value: NotificationChannelType;
  label: string;
  helper: string;
  group: '빠른 연결' | '고급 연결';
  setupLabel: string;
  setupUrl: string;
  openLabel: string;
  openUrl: string;
}> = [
  {
    value: 'DISCORD',
    label: 'Discord',
    helper: 'Discord 채널의 Webhook URL로 알림을 보냅니다.',
    group: '빠른 연결',
    setupLabel: 'Discord Webhook 가이드 보기',
    setupUrl: 'https://support.discord.com/hc/articles/228383668-Intro-to-Webhooks',
    openLabel: 'Discord 열기',
    openUrl: 'https://discord.com/channels/@me',
  },
  {
    value: 'GOOGLE_CHAT',
    label: 'Google Chat',
    helper: 'Google Chat 스페이스에서 복사한 Webhook URL을 사용합니다.',
    group: '빠른 연결',
    setupLabel: 'Google Chat Webhook 가이드 보기',
    setupUrl: 'https://developers.google.com/workspace/chat/quickstart/webhooks?hl=ko',
    openLabel: 'Google Chat 열기',
    openUrl: 'https://chat.google.com/',
  },
  {
    value: 'SLACK_WORKFLOW',
    label: 'Slack Workflow URL',
    helper: 'Slack 앱 생성 없이 Workflow Builder에서 만든 요청 URL을 사용합니다.',
    group: '빠른 연결',
    setupLabel: 'Slack Workflow 가이드 보기',
    setupUrl: 'https://slack.com/intl/ko-kr/help/articles/360041352714-%EC%9B%8C%ED%81%AC%ED%94%8C%EB%A1%9C-%EA%B5%AC%EC%B6%95--Slack-%EC%99%B8%EB%B6%80%EC%97%90%EC%84%9C-%EC%8B%9C%EC%9E%91%ED%95%98%EB%8A%94-%EC%9B%8C%ED%81%AC%ED%94%8C%EB%A1%9C-%EB%A7%8C%EB%93%A4%EA%B8%B0',
    openLabel: 'Slack 열기',
    openUrl: 'https://app.slack.com/client',
  },
  {
    value: 'TEAMS_WORKFLOW',
    label: 'Teams Workflow URL',
    helper: 'Teams Workflows에서 만든 HTTP POST URL로 알림을 보냅니다.',
    group: '빠른 연결',
    setupLabel: 'Teams Workflow 가이드 보기',
    setupUrl: 'https://support.microsoft.com/ko-kr/office/create-incoming-webhooks-with-workflows-for-microsoft-teams-8ae491c7-0394-4861-ba59-055e33f75498',
    openLabel: 'Teams 열기',
    openUrl: 'https://teams.microsoft.com/v2/',
  },
  {
    value: 'SLACK_WEBHOOK',
    label: 'Slack Incoming Webhook',
    helper: 'Bot Token이 아니라 Slack 앱의 Incoming Webhook URL을 입력합니다.',
    group: '고급 연결',
    setupLabel: 'Slack Incoming Webhook 가이드 보기',
    setupUrl: 'https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks/',
    openLabel: 'Slack 앱 관리 열기',
    openUrl: 'https://api.slack.com/apps',
  },
  {
    value: 'GENERIC_WEBHOOK',
    label: '직접 연동',
    helper: '사내 시스템이나 자동화 도구가 제공하는 HTTP 수신 URL로 표준 JSON 알림을 보냅니다.',
    group: '고급 연결',
    setupLabel: 'Webhook 테스트 가이드 보기',
    setupUrl: 'https://docs.webhook.site/',
    openLabel: 'Webhook 테스트 URL 만들기',
    openUrl: 'https://webhook.site/',
  },
];

const TIERS: Tier[] = ['T1', 'T2', 'T3', 'T4'];

export function NotificationsPage() {
  return (
    <PageContainer className="gap-5">
      <title>알림 연동 · Tracker</title>
      <header className="flex flex-col gap-1">
        <h1
          className="text-foreground font-semibold tracking-tight"
          style={{ fontSize: 'var(--size-h1)', lineHeight: 'var(--lh-snug)' }}
        >
          알림 연동
        </h1>
        <p className="text-muted-foreground text-sm">
          Webhook URL은 서버에서 암호화 저장되고 화면에는 마스킹 값만 표시됩니다.
        </p>
      </header>

      <Tabs defaultValue="channels" className="gap-4">
        <TabsList>
          <TabsTrigger value="channels">채널</TabsTrigger>
          <TabsTrigger value="rules">규칙</TabsTrigger>
          <TabsTrigger value="history">이력</TabsTrigger>
        </TabsList>
        <TabsContent value="channels">
          <ChannelPanel />
        </TabsContent>
        <TabsContent value="rules">
          <RulePanel />
        </TabsContent>
        <TabsContent value="history">
          <DeliveryPanel />
        </TabsContent>
      </Tabs>
    </PageContainer>
  );
}

function ChannelPanel() {
  const channelsQuery = useNotificationChannelsQuery();
  const channels = Array.isArray(channelsQuery.data) ? channelsQuery.data : [];
  const isLoading = channelsQuery.isLoading;
  const createChannel = useCreateNotificationChannelMutation();
  const testChannel = useTestNotificationChannelMutation();
  const [name, setName] = useState('');
  const [type, setType] = useState<NotificationChannelType>('DISCORD');
  const [webhookUrl, setWebhookUrl] = useState('');
  const selectedType = CHANNEL_TYPES.find((item) => item.value === type) ?? CHANNEL_TYPES[0];

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
            {['빠른 연결', '고급 연결'].map((group) => (
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
          placeholder={placeholderFor(type)}
        />
        <Button type="submit" disabled={!name || !webhookUrl || createChannel.isPending}>
          {createChannel.isPending ? <RotateCw className="animate-spin" /> : <CheckCircle2 />}
          저장
        </Button>
      </form>

      <div className="grid gap-3">
        {isLoading ? (
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
                  <span className="text-muted-foreground rounded border px-1.5 py-0.5 text-xs">{labelFor(channel.type)}</span>
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

function RulePanel() {
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

function DeliveryPanel() {
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

function LabeledInput({
  label,
  value,
  onChange,
  ...props
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
} & Omit<InputHTMLAttributes<HTMLInputElement>, 'value' | 'onChange'>) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="text-muted-foreground text-xs">{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="bg-background h-10 rounded-md border px-3"
        {...props}
      />
    </label>
  );
}

function labelFor(type: NotificationChannelType) {
  return CHANNEL_TYPES.find((item) => item.value === type)?.label ?? type;
}

function placeholderFor(type: NotificationChannelType) {
  switch (type) {
    case 'SLACK_WEBHOOK':
      return 'https://hooks.slack.com/services/...';
    case 'SLACK_WORKFLOW':
      return 'https://hooks.slack.com/triggers/...';
    case 'TEAMS_WORKFLOW':
      return 'https://prod-...logic.azure.com/workflows/...';
    case 'DISCORD':
      return 'https://discord.com/api/webhooks/...';
    case 'GOOGLE_CHAT':
      return 'https://chat.googleapis.com/v1/spaces/.../messages?key=...&token=...';
    case 'GENERIC_WEBHOOK':
      return 'https://example.com/tracker-alerts';
  }
}
