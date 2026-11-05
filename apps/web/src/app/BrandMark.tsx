/** The product mark: one solid slot square, the same shape a phrase frame leaves open. */
export function BrandMark({ className = "size-6" }: { className?: string }) {
  return <span aria-hidden className={`inline-block shrink-0 rounded-[2px] bg-[var(--slot)] ${className}`} />;
}
