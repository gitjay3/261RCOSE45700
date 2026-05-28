import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { PageContainer } from '@/layouts/PageContainer';
import { ChannelPanel } from './ChannelPanel';
import { DeliveryPanel } from './DeliveryPanel';
import { RulePanel } from './RulePanel';

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
