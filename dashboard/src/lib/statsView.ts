import { colorForType } from '@/components/charts/colors';
import { getLangLabel, getTypeLabel } from '@/components/tracker/labels';
import type {
  LangDistributionEntry,
  SiteDistributionEntry,
  TypeDistributionEntry,
} from '@/types/api';

/** Distribution entries → chart `{ name, value }` series. Dashboard/Stats 공유. */

export const typeDistributionToSeries = (entries: readonly TypeDistributionEntry[]) =>
  entries.map((e) => ({ name: getTypeLabel(e.type), value: e.count }));

export const typeDistributionToColors = (entries: readonly TypeDistributionEntry[]) =>
  entries.map((e) => colorForType(e.type));

export const siteDistributionToSeries = (entries: readonly SiteDistributionEntry[]) =>
  entries.map((e) => ({ name: e.site, value: e.count }));

export const langDistributionToSeries = (entries: readonly LangDistributionEntry[]) =>
  entries.map((e) => ({ name: getLangLabel(e.lang), value: e.count }));
