import type { FormResult } from '../lib/standings';

const WORD: Record<FormResult, string> = { W: 'win', D: 'draw', L: 'loss' };

export function FormPills({ form }: { form: FormResult[] }) {
  if (form.length === 0) return <span className="muted">&ndash;</span>;
  return (
    <span className="form" aria-label={`Last ${form.length}: ${form.map((f) => WORD[f]).join(', ')}`}>
      {form.map((c, i) => (
        <span key={i} className={`form__pill form__pill--${c}`} aria-hidden="true">
          {c}
        </span>
      ))}
    </span>
  );
}
