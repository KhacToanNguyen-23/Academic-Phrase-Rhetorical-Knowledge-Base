type BarItem = { label: string; value: number; emphasis?: boolean };

/** A neutral horizontal bar chart. One hue; an emphasised row is darker, never coloured. */
function BarList({ items, label }: { items: BarItem[]; label: string }) {
  const max = Math.max(1, ...items.map((item) => item.value));
  return (
    <ul aria-label={label} className="flex flex-col gap-2.5">
      {items.map((item) => (
        <li key={item.label} className="grid grid-cols-[7rem_1fr_2.5rem] items-center gap-3 text-sm">
          <span className="truncate">{item.label}</span>
          <span aria-hidden className="h-2 bg-muted">
            <span
              className={`block h-full ${item.emphasis ? "bg-foreground" : "bg-foreground/35"}`}
              style={{ width: `${(item.value / max) * 100}%` }}
            />
          </span>
          <span className="text-right tabular-nums">{item.value}</span>
        </li>
      ))}
    </ul>
  );
}

export { BarList };
export type { BarItem };
