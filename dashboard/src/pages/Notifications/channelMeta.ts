import type { NotificationChannelType, Tier } from '@/types/api';

export interface ChannelTypeMeta {
  value: NotificationChannelType;
  label: string;
  helper: string;
  group: '빠른 연결' | '고급 연결';
  setupLabel: string;
  setupUrl: string;
  openLabel: string;
  openUrl: string;
  placeholder: string;
}

export const CHANNEL_TYPES: ChannelTypeMeta[] = [
  {
    value: 'DISCORD',
    label: 'Discord',
    helper: 'Discord 채널의 Webhook URL로 알림을 보냅니다.',
    group: '빠른 연결',
    setupLabel: 'Discord Webhook 가이드 보기',
    setupUrl: 'https://support.discord.com/hc/articles/228383668-Intro-to-Webhooks',
    openLabel: 'Discord 열기',
    openUrl: 'https://discord.com/channels/@me',
    placeholder: 'https://discord.com/api/webhooks/...',
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
    placeholder: 'https://chat.googleapis.com/v1/spaces/.../messages?key=...&token=...',
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
    placeholder: 'https://hooks.slack.com/triggers/...',
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
    placeholder: 'https://prod-...logic.azure.com/workflows/...',
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
    placeholder: 'https://hooks.slack.com/services/...',
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
    placeholder: 'https://example.com/tracker-alerts',
  },
];

export const CHANNEL_GROUPS: Array<ChannelTypeMeta['group']> = ['빠른 연결', '고급 연결'];

export const TIERS: Tier[] = ['T1', 'T2', 'T3', 'T4'];

export function metaForChannel(type: NotificationChannelType) {
  return CHANNEL_TYPES.find((item) => item.value === type) ?? CHANNEL_TYPES[0];
}
