import type { Language } from '@/types/api';

export interface SourceMeta {
  name: string;
  lang: Language;
}

/**
 * 알려진 소스 사이트. 백엔드가 `/sources` 엔드포인트 노출 전까지 단일점.
 * MSW mock data, RightRail health 표시, FilterBar 옵션이 모두 이 목록 참조.
 */
export const SOURCE_META: SourceMeta[] = [
  { name: 'tailstar.net', lang: 'ko' },
  { name: 'ptt.cc', lang: 'zh-TW' },
  { name: 'dcard.tw', lang: 'zh-TW' },
  { name: 'tieba.baidu.com', lang: 'zh-CN' },
  { name: '52pojie.cn', lang: 'zh-CN' },
  { name: 'bbs.nga.cn', lang: 'zh-CN' },
];

export const KNOWN_SOURCES = SOURCE_META.map((source) => source.name);
