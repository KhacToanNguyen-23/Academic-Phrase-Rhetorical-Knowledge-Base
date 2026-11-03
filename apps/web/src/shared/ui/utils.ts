export type ClassValue = string | false | null | undefined;

/** Small, dependency-free equivalent of the `cn` helper used by shadcn/ui. */
export function cn(...values: ClassValue[]) {
  return values.filter(Boolean).join(" ");
}
