// Component UI dùng chung — semantic HTML + ARIA, điều hướng được bằng bàn phím (NFR-08).
import type { ReactNode } from "react";

import type { EvidenceClass, FallbackTier, Provenance, Severity } from "@/shared/api";
import { parseFrame } from "@/shared/lib";

export function PageHeader({ code, title, lead, actions }: { code: string; title: string; lead?: string; actions?: ReactNode }) {
  return (
    <header className="page-header">
      <div>
        <p className="eyebrow">{code}</p>
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

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="field-hint">{hint}</span>}
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
      {confirm && <div className="confirm">{confirm}</div>}
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
