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
