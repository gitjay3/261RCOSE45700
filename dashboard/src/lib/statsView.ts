import { colorForType } from '@/components/charts/colors';
import { getLangLabel, getTypeLabel } from '@/components/tracker/labels';
import { getSiteLabel } from '@/lib/sources';
import type {
  LangDistributionEntry,
  SiteDistributionEntry,
  TypeDistributionEntry,
} from '@/types/api';

/** Distribution entries → chart `{ name, value }` series with original filter values. */

export const typeDistributionToSeries = (entries: readonly TypeDistributionEntry[]) =>
  entries.map((e) => ({ name: getTypeLabel(e.type), value: e.count, type: e.type }));

export const typeDistributionToColors = (entries: readonly TypeDistributionEntry[]) =>
  entries.map((e) => colorForType(e.type));

export const siteDistributionToSeries = (entries: readonly SiteDistributionEntry[]) =>
  entries.map((e) => ({ name: getSiteLabel(e.site), value: e.count, site: e.site }));

export const langDistributionToSeries = (entries: readonly LangDistributionEntry[]) =>
  entries.map((e) => ({ name: getLangLabel(e.lang), value: e.count, lang: e.lang }));
