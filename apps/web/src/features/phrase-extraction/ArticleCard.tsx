import { useQuery } from "@tanstack/react-query";

import { slrImportClient, unwrap } from "@/features/slr-import/api/client";
import { Badge, Card, Loading, StatusBadge } from "@/shared/ui";
import type { ArticleRow, ArticleText } from "./types";

type Props = {
  article: ArticleRow;
  open: boolean;
  /** True when the phrase list is filtered to this article. */
  filtered: boolean;
  /** Sentences that produced one of the phrases currently listed. */
  sourceSentenceIds: Set<string>;
  onToggle: () => void;
  onFilter: () => void;
};

export function ArticleCard({ article, open, filtered, sourceSentenceIds, onToggle, onFilter }: Props) {
  const api = slrImportClient();
  const text = useQuery({
    queryKey: ["extract-article-text", article.id],
    enabled: open,
    queryFn: async (): Promise<ArticleText> =>
      unwrap(await api.GET("/v1/admin/corpus/articles/{article_id}/text", { params: { path: { article_id: article.id } } })) as ArticleText,
  });
  const total = article.phrases.pending + article.phrases.accepted + article.phrases.rejected;
  return (
    <Card
      className={`article-card ${filtered ? "article-card--filtered" : ""}`}
      title={<span className="extract-article-title">{article.title || "Chưa có tiêu đề"}</span>}
      aside={<StatusBadge status={article.mining_status} />}
    >
      <p className="entry-meta extract-article-meta">
        <span className="extract-article-meta-text">
          {article.journal ?? "chưa có journal"} · {article.ingest_status !== "ready" ? `ingest: ${article.ingest_status} · ` : ""}{total} phrase
        </span>
        {article.phrases.pending > 0 && <Badge tone="warn">{article.phrases.pending} chờ duyệt</Badge>}
        {article.phrases.accepted > 0 && <Badge tone="ok">{article.phrases.accepted} đã nhận</Badge>}
      </p>
      <div className="gold-actions extract-article-actions">
        <button type="button" className="btn btn-ghost btn-sm" aria-expanded={open} onClick={onToggle}>
          {open ? "Đóng bài" : "Mở bài"}
        </button>
        {(total > 0 || filtered) && (
          <button
            type="button"
            className={`btn btn-sm btn-chip-toggle ${filtered ? "is-active" : ""}`}
            aria-pressed={filtered}
            onClick={onFilter}
          >
            {filtered ? "Bỏ lọc phrase" : "Chỉ xem phrase bài này"}
          </button>
        )}
      </div>
      {open && (
        <div className="extract-article-text custom-scrollbar">
          {text.isPending ? <Loading /> : text.isError ? <p className="notice notice-bad" role="alert">{text.error.message}</p> : (
            text.data.sections.map((section, index) => (
              <section key={index}>
                {section.heading && <h3>{section.heading}</h3>}
                <p>
                  {section.sentences.map((sentence) => (
                    <span key={sentence.id} className={sourceSentenceIds.has(sentence.id) ? "extract-source-sentence" : undefined}>
                      {sentence.text}{" "}
                    </span>
                  ))}
                </p>
              </section>
            ))
          )}
        </div>
      )}
    </Card>
  );
}
