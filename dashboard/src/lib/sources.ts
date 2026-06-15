import type { Language } from '@/types/api';

export interface SourceMeta {
  id: string;   // site_id = sources.site_name in DB
  name: string; // display name
  lang: Language;
}

export const SOURCE_META: SourceMeta[] = [
  { id: 'inven_lineage_classic', name: '인벤 (리니지 클래식)', lang: 'ko' },
  { id: 'ptt', name: 'PTT (Lineage)', lang: 'zh-TW' },
  { id: 'ptt_mobile_game', name: 'PTT (Mobile-game)', lang: 'zh-TW' },
  { id: 'bahamut_lineage', name: '바하무트 (天堂)', lang: 'zh-TW' },
  { id: 'bahamut_lineage_m', name: '바하무트 (天堂M)', lang: 'zh-TW' },
  { id: 'bahamut_lineage_w', name: '바하무트 (天堂W)', lang: 'zh-TW' },
  { id: 'bahamut_lineage_classic', name: '바하무트 (天堂經典版)', lang: 'zh-TW' },
  { id: 'bahamut_aion', name: '바하무트 (永恆紀元)', lang: 'zh-TW' },
  { id: 'bahamut_aion2', name: '바하무트 (AION2)', lang: 'zh-TW' },
  { id: 'bahamut_bns', name: '바하무트 (劍靈)', lang: 'zh-TW' },
  { id: 'bahamut_tl', name: '바하무트 (TL)', lang: 'zh-TW' },
  { id: '52pojie', name: '52pojie', lang: 'zh-CN' },
  { id: 'github', name: 'GitHub', lang: 'en' },
];

export const KNOWN_SOURCES = SOURCE_META.map((source) => source.id);

export function getSiteLabel(siteId: string): string {
  return SOURCE_META.find((s) => s.id === siteId)?.name ?? siteId;
}
