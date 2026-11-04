/** "12 of 30 reviewed" with a neutral bar. Hidden when there is nothing to review. */
function ProgressLine({ done, total, label }: { done: number; total: number; label: string }) {
  if (total <= 0) return null;
  const share = Math.min(100, Math.round((done / total) * 100));
  return (
    <div className="flex items-center gap-4 text-sm">
      <span className="whitespace-nowrap tabular-nums">
        {done} of {total} {label}
      </span>
      <span
        role="progressbar"
        aria-label={`${label}: ${share}%`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={share}
        className="h-2 w-64 bg-muted"
      >
        <span className="block h-full bg-foreground/60" style={{ width: `${share}%` }} />
      </span>
      <span className="tabular-nums text-muted-foreground">{share}%</span>
    </div>
  );
}

export { ProgressLine };
