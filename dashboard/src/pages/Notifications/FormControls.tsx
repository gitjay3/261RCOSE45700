import type { InputHTMLAttributes } from 'react';

export function LabeledInput({
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
