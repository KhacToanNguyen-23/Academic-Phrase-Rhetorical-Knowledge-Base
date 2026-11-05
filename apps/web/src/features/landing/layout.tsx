import type { CSSProperties, ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Delay index for the staggered entrance (see .reveal in landing.css). */
export const idx = (i: number) => ({ "--i": i }) as CSSProperties;

/** The one page width: 1280px, with the page margin on both sides. */
export function Wrap({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("mx-auto w-full max-w-[1280px] px-[var(--margin)]", className)}>{children}</div>;
}

/** Heading and its supporting text, always together in the left four columns. */
export function SectionHead({ title, children, sticky = false }: { title: string; children?: ReactNode; sticky?: boolean }) {
  return (
    <div className={cn("lg:col-span-5", sticky && "lg:sticky lg:top-28 lg:self-start")}>
      <h2 className="display reveal text-[clamp(30px,2.9vw,42px)]">{title}</h2>
      <div className="reveal mt-5 flex max-w-[28rem] flex-col gap-4 text-[20px] leading-[1.5]" style={idx(1)}>
        {children}
      </div>
    </div>
  );
}

/** Every section: the same vertical rhythm and the same 12-column grid. */
export const SECTION = "py-28";
export const GRID = "grid gap-x-8 gap-y-12 lg:grid-cols-12";
