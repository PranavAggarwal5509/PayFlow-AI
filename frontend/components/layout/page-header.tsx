import type { ReactNode } from "react";

/** Page title block. It sits on the dark hero band rendered by the root layout. */
export function PageHeader({
  title,
  description,
  actions,
  eyebrow,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  eyebrow?: string;
}) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div className="max-w-3xl">
        {eyebrow && (
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-indigo-300">{eyebrow}</p>
        )}
        <h1 className="text-[28px] font-semibold leading-tight tracking-tight text-white sm:text-[32px]">{title}</h1>
        {description && <p className="mt-2 text-[14.5px] leading-relaxed text-slate-300">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
