// Tiện ích dùng chung.

export type FramePart = { kind: "text"; value: string } | { kind: "slot"; name: string };

/** Tách canonical_frame thành text + slot `{name}` (FR-02.1). */
export function parseFrame(frame: string): FramePart[] {
  return frame.split(/(\{[a-z_]+\})/g).filter(Boolean).map((s) =>
    s.startsWith("{") ? { kind: "slot", name: s.slice(1, -1) } : { kind: "text", value: s },
  );
}

/** Render frame; slot trống giữ nguyên `{name}` — không tự chế nội dung (BR-02, FR-07.5). */
export function renderFrame(frame: string, values: Record<string, string>): string {
  return frame.replace(/\{([a-z_]+)\}/g, (m, name: string) => values[name]?.trim() || m);
}

export const pct = (n: number) => `${Math.round(n * 100)}%`;

/** "just now", "3 h ago", "2 days ago"; older than 30 days falls back to the date. */
export function relativeTime(iso: string, now: Date = new Date()): string {
  const diff = now.getTime() - new Date(iso).getTime();
  if (Number.isNaN(diff)) return "";
  const minutes = Math.round(diff / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  if (days <= 30) return `${days} ${days === 1 ? "day" : "days"} ago`;
  return new Date(iso).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}
