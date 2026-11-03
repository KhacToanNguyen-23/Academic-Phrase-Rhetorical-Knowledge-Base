import { useState } from "react";

import { Badge } from "@/shared/ui";
import { HighlightedSentence, MaskedFrame } from "./MaskedFrame";
import type { Phrase } from "./types";

type Props = {
  phrase: Phrase;
  checked: boolean;
  busy: boolean;
  onCheck: (checked: boolean) => void;
  onDecide: (decision: "accept" | "reject") => void;
};

export function PhraseCard({ phrase, checked, busy, onCheck, onDecide }: Props) {
  const pending = phrase.status === "pending";
  const [expanded, setExpanded] = useState(false);
  const totalSources = phrase.sources.length;
  const visibleSources = expanded ? phrase.sources : phrase.sources.slice(0, 2);
  const hiddenCount = totalSources - 2;

  return (
    <article
      className={`phrase-card ${checked ? "phrase-card--selected" : ""} ${phrase.blocked ? "phrase-card--blocked" : ""} phrase-card--${phrase.status}`}
    >
      <header className="phrase-card-header">
        <div className="phrase-card-lead">
          {pending && (
            <label className="phrase-card-checkbox-label" title="Chọn phrase này để thao tác hàng loạt">
              <input
                type="checkbox"
                checked={checked}
                aria-label={`Chọn phrase ${phrase.canonical_frame}`}
                onChange={(event) => onCheck(event.target.checked)}
              />
            </label>
          )}
          <h3 className="phrase-card-heading">
            <MaskedFrame frame={phrase.canonical_frame} />
          </h3>
        </div>

        <div className="phrase-card-badges">
          {totalSources > 2 && !expanded && (
            <Badge tone="neutral" title={`${totalSources} câu nguồn xuất hiện phrase này`}>
              {totalSources} câu nguồn
            </Badge>
          )}
          {phrase.epistemic_strength && (
            <span
              className={`badge phrase-strength-badge phrase-strength-badge--${phrase.epistemic_strength.toLowerCase()}`}
              title={`Epistemic claim strength: ${phrase.epistemic_strength}`}
            >
              <span className="phrase-strength-dot" aria-hidden="true" />
              {phrase.epistemic_strength}
            </span>
          )}
          {phrase.blocked && (
            <Badge tone="bad" title="Không thể chấp nhận: thiếu nguồn, thiếu quyền mining hoặc slot không hợp lệ">
              ⚠ Bị chặn
            </Badge>
          )}
          {!pending && (
            <Badge tone={phrase.status === "accepted" ? "ok" : "bad"}>
              {phrase.status === "accepted" ? "✓ Đã chấp nhận" : "✕ Đã từ chối"}
            </Badge>
          )}
        </div>
      </header>

      <div className="phrase-card-body">
        {totalSources === 0 ? (
          <div className="phrase-notice phrase-notice--warn">
            <span className="phrase-notice-icon" aria-hidden="true">⚠</span>
            <p>Không hiển thị được câu nguồn (thiếu nguồn hoặc bài không có quyền mining).</p>
          </div>
        ) : (
          <>
            {visibleSources.map((source) => (
              <div key={source.sentence_id} className="phrase-source-panel">
                <div className="phrase-source-text-wrap">
                  <span className="phrase-source-quotemark" aria-hidden="true">“</span>
                  <p className="phrase-source-text">
                    <HighlightedSentence text={source.text} spans={source.slot_spans} />
                  </p>
                </div>
                <footer className="phrase-source-footer">
                  <div className="phrase-source-tags">
                    {source.section && (
                      <span className="phrase-meta-tag phrase-meta-tag--section" title="Mục trong bài báo">
                        {source.section}
                      </span>
                    )}
                    {source.journal && (
                      <span className="phrase-meta-tag phrase-meta-tag--journal" title="Journal">
                        {source.journal}
                      </span>
                    )}
                  </div>
                  <div className="phrase-source-citation" title={source.article_title ?? undefined}>
                    <svg
                      className="phrase-citation-icon"
                      viewBox="0 0 16 16"
                      width="13"
                      height="13"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.5"
                      aria-hidden="true"
                    >
                      <path d="M3 2.5A1.5 1.5 0 0 1 4.5 1h5.879a1.5 1.5 0 0 1 1.06.44l2.122 2.12a1.5 1.5 0 0 1 .439 1.061V13.5a1.5 1.5 0 0 1-1.5 1.5h-8A1.5 1.5 0 0 1 3 13.5v-11Z" />
                      <path d="M9 1v3.5a.5.5 0 0 0 .5.5H13" />
                    </svg>
                    <span className="phrase-source-title-text">{source.article_title ?? "Không có tiêu đề bài báo"}</span>
                  </div>
                </footer>
              </div>
            ))}
            {totalSources > 2 && (
              <div className="phrase-sources-toggle-wrap">
                <button
                  type="button"
                  className="btn btn-ghost btn-sm phrase-toggle-sources-btn"
                  onClick={() => setExpanded((prev) => !prev)}
                >
                  {expanded ? "Thu gọn câu nguồn" : `Xem thêm ${hiddenCount} câu nguồn`}
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {pending && (
        <footer className="phrase-card-footer">
          <div className="phrase-card-footer-note">
            {phrase.blocked && (
              <span className="phrase-blocked-hint">
                Chưa đủ điều kiện: cần bài có quyền mining và slot hợp lệ để chấp nhận.
              </span>
            )}
          </div>
          <div className="phrase-card-footer-actions">
            <button
              type="button"
              className="btn btn-sm btn-ghost btn-decision-reject"
              disabled={busy}
              onClick={() => onDecide("reject")}
              title="Từ chối phrase candidate này"
            >
              <span className="phrase-btn-symbol" aria-hidden="true">✕</span>
              Từ chối
            </button>
            <button
              type="button"
              className="btn btn-sm btn-primary btn-decision-accept"
              disabled={busy || phrase.blocked}
              title={
                phrase.blocked
                  ? "Không thể chấp nhận: thiếu nguồn, thiếu quyền mining hoặc slot không hợp lệ"
                  : "Chấp nhận phrase này và lưu vào cơ sở tri thức"
              }
              onClick={() => onDecide("accept")}
            >
              <span className="phrase-btn-symbol" aria-hidden="true">✓</span>
              Chấp nhận
            </button>
          </div>
        </footer>
      )}
    </article>
  );
}
