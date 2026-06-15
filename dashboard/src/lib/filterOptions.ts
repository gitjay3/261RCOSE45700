import { LANG_OPTIONS, TYPE_OPTIONS } from '@/components/tracker/labels';
import { SOURCE_META } from './sources';
import type { Tier } from '@/types/api';

export interface FilterSelectOption {
  value: string;
  label: string;
  className?: string;
}

export function detectionFilterOptions() {
  const tierOptions: { value: Tier; label: string }[] = [
    { value: 'T1', label: 'T1 긴급' },
    { value: 'T2', label: 'T2 높음' },
    { value: 'T3', label: 'T3 보통' },
    { value: 'T4', label: 'T4 낮음' },
  ];

  return {
    siteOptions: SOURCE_META.map((source) => ({
      value: source.id,
      label: source.name,
      className: 'font-mono text-xs',
    })),
    typeOptions: TYPE_OPTIONS.map((type) => ({
      value: type.value,
      label: type.label,
    })),
    langOptions: LANG_OPTIONS.map((lang) => ({
      value: lang.value,
      label: lang.label,
    })),
    tierOptions,
  } satisfies Record<string, FilterSelectOption[]>;
}
