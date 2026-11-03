// Component UI dùng chung — semantic HTML + ARIA, điều hướng được bằng bàn phím (NFR-08).
import { useId, useRef, type KeyboardEvent, type ReactNode } from "react";

import type { EvidenceClass, FallbackTier, Provenance, Severity } from "@/shared/api";
import { parseFrame } from "@/shared/lib";

export function PageHeader({ code, title, lead, actions }: { code?: string; title: ReactNode; lead?: string; actions?: ReactNode }) {
  return (
    <header className="page-header">
      <div>
        {code && <p className="eyebrow">{code}</p>}
        <h1>{title}</h1>
        {lead && <p className="lead">{lead}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  );
}

export function Badge({ children, tone = "neutral", title }: { children: ReactNode; tone?: "neutral" | "ok" | "warn" | "bad" | "info"; title?: string }) {
  return <span className={`badge badge-${tone}`} title={title}>{children}</span>;
}

const EVIDENCE: Record<EvidenceClass, { label: string; hint: string }> = {
  required: { label: "Required by journal", hint: "Verified rule from the author guidelines (source link + access date)" },
  observed: { label: "Observed in corpus", hint: "Descriptive corpus statistic — not a journal rule" },
  suggested: { label: "Model suggestion", hint: "Model inference with confidence — not a journal rule" },
};

/** Nhãn bắt buộc để tách rule / quan sát / suy luận (BR-04, BR-09, Gate C). */
export function EvidenceLabel({ kind }: { kind: EvidenceClass }) {
  return <span className={`evidence evidence-${kind}`} title={EVIDENCE[kind].hint}>{EVIDENCE[kind].label}</span>;
}

const PROVENANCE: Record<Provenance, string> = {
  authored: "Authored",
  adapted_permission: "Adapted with permission",
  corpus_inferred: "Corpus-inferred",
};

/** FR-02.7: UI luôn hiển thị nguồn gốc. */
export function ProvenanceTag({ value }: { value: Provenance }) {
  return <Badge tone={value === "corpus_inferred" ? "info" : "neutral"} title="Provenance">{PROVENANCE[value]}</Badge>;
}

const TIERS: Record<FallbackTier, string> = {
  journal_genre: "Journal + genre",
  similar_journal: "Similar journal",
  subfield: "Subfield",
  field: "Field",
  generic: "Generic",
};

/** FR-07.4 / FR-05.6: luôn nêu rõ fallback_tier và lý do. */
export function FallbackNotice({ tier, reason }: { tier: FallbackTier; reason?: string }) {
  return (
    <div className={`notice ${tier === "journal_genre" ? "notice-ok" : "notice-warn"}`} role="status">
      <strong>Fallback tier — {TIERS[tier]}.</strong>
      {reason && <span> {reason}</span>}
    </div>
  );
}

export function SeverityBadge({ value }: { value: Severity }) {
  const map = { pass: ["ok", "Pass"], warn: ["warn", "Warn"], block: ["bad", "Block"] } as const;
  return <Badge tone={map[value][0]}>{map[value][1]}</Badge>;
}

/** Hiển thị canonical frame với slot được làm nổi bật. */
export function Frame({ frame, values }: { frame: string; values?: Record<string, string> }) {
  return (
    <span className="frame">
      {parseFrame(frame).map((p, i) =>
        p.kind === "text" ? (
          <span key={i}>{p.value}</span>
        ) : values?.[p.name]?.trim() ? (
          <mark key={`${i}-${values[p.name]}`} className="slot slot-filled">{values[p.name]}</mark>
        ) : (
          <mark key={i} className="slot" aria-label={`unfilled slot ${p.name}`}>{`{${p.name}}`}</mark>
        ),
      )}
    </span>
  );
}

export function Field({ label, children, hint, error }: { label: string; children: ReactNode; hint?: string; error?: string }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {error ? <span className="field-error" role="alert">{error}</span> : hint ? <span className="field-hint">{hint}</span> : null}
    </label>
  );
}

/**
 * Một "section" kiểu bài báo. `confirm` là hành động chính,
 * chỉ hiện khi hover/focus vào section (luôn hiện trên thiết bị cảm ứng).
 */
export function Card({ title, aside, confirm, children }: { title?: ReactNode; aside?: ReactNode; confirm?: ReactNode; children: ReactNode }) {
  return (
    <section className="card">
      {(title || aside) && (
        <div className="card-head">
          {title && <h2>{title}</h2>}
          {aside}
        </div>
      )}
      {children}
      {confirm && <div className="confirm"><div className="confirm-inner">{confirm}</div></div>}
    </section>
  );
}

export function Meter({ value, label }: { value: number; label: string }) {
  return (
    <div className="meter" role="meter" aria-valuemin={0} aria-valuemax={1} aria-valuenow={value} aria-label={label}>
      <span style={{ width: `${Math.round(value * 100)}%` }} />
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="empty">{children}</p>;
}

export function Loading() {
  return <div className="loading" aria-busy="true" aria-label="Loading"><span /><span /><span /></div>;
}

export function ErrorState({ onRetry, message = "Data could not be loaded." }: { onRetry: () => void; message?: string }) {
  return (
    <div className="notice notice-warn" role="alert">
      <p>{message}</p>
      <button type="button" className="btn btn-ghost" onClick={() => void onRetry()}>Try again</button>
    </div>
  );
}

/** Ô số liệu tổng quan (Admin/Overview). */
export function Stat({ label, value, note, tone }: { label: string; value: ReactNode; note?: string; tone?: "ok" | "warn" | "bad" }) {
  return (
    <div className={`stat ${tone ? `stat-${tone}` : ""}`}>
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
      {note && <span className="stat-note">{note}</span>}
    </div>
  );
}

/** Khối JSON request/response — tài liệu sống cho nhóm Writing. */
export function JsonBlock({ title, value }: { title: string; value: unknown }) {
  return (
    <figure className="json">
      <figcaption>{title}</figcaption>
      <pre><code>{JSON.stringify(value, null, 2)}</code></pre>
    </figure>
  );
}

export function Tabs<T extends string>({ value, onChange, items, label, children }: { value: T; onChange: (v: T) => void; items: { id: T; label: string; count?: number }[]; label: string; children: ReactNode }) {
  const id = useId();
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const focusTab = (index: number) => {
    const nextIndex = (index + items.length) % items.length;
    onChange(items[nextIndex].id);
    tabRefs.current[nextIndex]?.focus();
  };
  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (event.key === "ArrowRight") {
      event.preventDefault();
      focusTab(index + 1);
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      focusTab(index - 1);
    } else if (event.key === "Home") {
      event.preventDefault();
      focusTab(0);
    } else if (event.key === "End") {
      event.preventDefault();
      focusTab(items.length - 1);
    }
  };

  return (
    <>
      <div className="tabs" role="tablist" aria-label={label}>
        {items.map((t, index) => (
          <button
            key={t.id}
            ref={(element) => { tabRefs.current[index] = element; }}
            id={`${id}-tab-${t.id}`}
            type="button"
            role="tab"
            aria-selected={t.id === value}
            aria-controls={`${id}-panel`}
            tabIndex={t.id === value ? 0 : -1}
            className="tab"
            onClick={() => onChange(t.id)}
            onKeyDown={(event) => onKeyDown(event, index)}
          >
            {t.label}{t.count !== undefined && <span className="tab-count">{t.count}</span>}
          </button>
        ))}
      </div>
      <div id={`${id}-panel`} className="tab-panel" role="tabpanel" aria-labelledby={`${id}-tab-${value}`} tabIndex={0}>
        {children}
      </div>
    </>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const tone = ({
    approved: "ok",
    active: "ok",
    succeeded: "ok",
    done: "ok",
    pending: "warn",
    in_review: "warn",
    revision: "warn",
    queued: "warn",
    running: "info",
    draft: "neutral",
    rejected: "bad",
    retired: "bad",
    suspended: "bad",
    failed: "bad",
  } as const)[status] ?? "neutral";
  return <Badge tone={tone}>{status.replace("_", " ")}</Badge>;
}

export const fmtTime = (iso: string) =>
  new Date(iso).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
