import type { ReactNode } from "react";

const SLOT = /^\[([A-Z])\]$/;

/** A mined frame such as "[X] report that [Y]." with each slot highlighted. */
export function MaskedFrame({ frame }: { frame: string }) {
  return (
    <span className="frame">
      {frame
        .split(/(\[[A-Z]\])/g)
        .filter(Boolean)
        .map((part, index) => {
          const slot = SLOT.exec(part);
          return slot ? (
            <mark key={index} className={`slot-badge slot-badge-${slot[1]}`}>{part}</mark>
          ) : (
            <span key={index} className="frame-text">{part}</span>
          );
        })}
    </span>
  );
}

/** The source sentence with each slot's character range highlighted; plain text if a range is invalid. */
export function HighlightedSentence({ text, spans }: { text: string; spans: Record<string, number[]> }) {
  const ranges = Object.entries(spans)
    .map(([name, [start, end]]) => ({ name, start, end }))
    .filter((r) => Number.isInteger(r.start) && Number.isInteger(r.end) && r.start >= 0 && r.end > r.start && r.end <= text.length)
    .sort((a, b) => a.start - b.start);
  const parts: ReactNode[] = [];
  let cursor = 0;
  for (const range of ranges) {
    if (range.start < cursor) continue;
    if (range.start > cursor) parts.push(<span key={`t${cursor}`}>{text.slice(cursor, range.start)}</span>);
    parts.push(
      <mark
        key={`m${range.start}`}
        className={`phrase-slot-span phrase-slot-span-${range.name}`}
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
