/** Accepts only same-origin relative paths. "/library?p=1" is kept; "//evil.com", "/\evil.com" and "https://evil.com" are dropped. */
export function safeNext(value: unknown): string | undefined {
  if (typeof value !== "string" || value.length === 0 || value.length > 2048) return undefined;
  if (!value.startsWith("/") || value.startsWith("//") || value.startsWith("/\\")) return undefined;
  // Browsers strip tab and newline, so "/\t/evil.com" would become "//evil.com".
  for (let i = 0; i < value.length; i += 1) {
    const code = value.charCodeAt(i);
    if (code < 0x20 || code === 0x7f) return undefined;
  }
  return value;
}
