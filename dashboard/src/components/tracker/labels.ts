import type { DetectionType, Language } from '@/types/api';

const TYPE_LABEL: Record<DetectionType, string> = {
  핵_치트: '핵·치트',
  사설서버: '사설서버',
  불법프로그램_배포: '불법 프로그램',
  계정_거래: '계정 거래',
  매크로_판매: '매크로 판매',
  리세마라: '리세마라',
  현금화: '현금화',
  광고_도배: '광고 도배',
  기타: '기타',
};

const LANG_LABEL: Record<Language, string> = {
  ko: '한국어',
  en: '영어',
  'zh-CN': '중국어 (간체)',
  'zh-TW': '중국어 (번체)',
  vi: '베트남어',
};

export function getTypeLabel(type: DetectionType): string {
  return TYPE_LABEL[type] ?? type;
}

export function getLangLabel(lang: Language): string {
  return LANG_LABEL[lang] ?? lang;
}

export const TYPE_OPTIONS: { value: DetectionType; label: string }[] = (
  Object.keys(TYPE_LABEL) as DetectionType[]
).map((value) => ({ value, label: TYPE_LABEL[value] }));

export const LANG_OPTIONS: { value: Language; label: string }[] = (
  Object.keys(LANG_LABEL) as Language[]
).map((value) => ({ value, label: LANG_LABEL[value] }));
