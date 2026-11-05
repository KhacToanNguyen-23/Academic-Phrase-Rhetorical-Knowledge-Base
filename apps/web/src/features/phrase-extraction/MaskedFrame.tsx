import type { ReactNode } from "react";

import { PhraseFrame } from "@/components/domain/PhraseFrame";

/** A mined frame such as "[X] report that [Y]." with each slot highlighted. */
export function MaskedFrame({ frame }: { frame: string }) {
  const normalized = frame.replace(/\[([A-Z])\]/g, "{$1}");
  return <PhraseFrame frame={normalized} />;
}

/** The source sentence with each slot's character range highlighted. */
export function HighlightedSentence({ text, spans }: { text: string; spans: Record<string, number[]> }) {
  const ranges = Object.entries(spans)
    .map(([name, [start, end]]) => ({ name, start, end }))
    .filter(
      (range) =>
        Number.isInteger(range.start) &&
        Number.isInteger(range.end) &&
        range.start >= 0 &&
        range.end > range.start &&
        range.end <= text.length,
    )
    .sort((a, b) => a.start - b.start);
  const parts: ReactNode[] = [];
  let cursor = 0;

  for (const range of ranges) {
    if (range.start < cursor) continue;
    if (range.start > cursor) {
      parts.push(<span key={`text-${cursor}`}>{text.slice(cursor, range.start)}</span>);
    }
    parts.push(
      <mark
        key={`mark-${range.start}`}
        className="rounded-[2px] bg-primary/10 px-1 text-foreground"
        title={`Slot [${range.name}]`}
      >
        {text.slice(range.start, range.end)}
      </mark>,
    );
    cursor = range.end;
  }

  if (cursor < text.length) parts.push(<span key="tail">{text.slice(cursor)}</span>);
  return <>{parts}</>;
}
