export type DetectionType =
  | '핵_치트'
  | '사설서버'
  | '불법프로그램_배포'
  | '계정_거래'
  | '매크로_판매'
  | '리세마라'
  | '현금화'
  | '광고_도배'
  | '기타';

export type Language = 'ko' | 'zh-CN' | 'zh-TW';

export interface Detection {
  id: number;
  isIllegal: boolean;
  type: DetectionType;
  confidence: number;
  reason: string;
  rawText: string;
  translatedText: string | null;
  postUrl: string;
  siteName: string;
  language: Language;
  detectedAt: string;
}

export interface DetectionListResponse {
  content: Detection[];
  page: number;
  size: number;
  totalElements: number;
}

export interface TypeDistributionEntry {
  type: DetectionType;
  count: number;
}

export interface SiteDistributionEntry {
  site: string;
  count: number;
}

export interface LangDistributionEntry {
  lang: Language;
  count: number;
}

export interface TrendEntry {
  date: string;
  count: number;
}

export interface StatsResponse {
  todayCount: number;
  deltaFromYesterday: number;
  typeDistribution: TypeDistributionEntry[];
  siteDistribution: SiteDistributionEntry[];
  langDistribution: LangDistributionEntry[];
  trend?: TrendEntry[];
}

export interface ProblemDetail {
  type: string;
  title: string;
  status: number;
  detail: string;
  instance?: string;
  errorCode: string;
}

export interface DetectionFilter {
  date?: string; // YYYY-MM-DD
  site?: string;
  type?: DetectionType;
  lang?: Language;
  page?: number;
  size?: number;
}

export interface CrawlTriggerResponse {
  status: 'triggered' | 'in_progress';
  estimatedMinutes: number;
}

export type StatsPeriod = 'weekly' | 'monthly';
