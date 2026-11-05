import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataState } from "@/components/domain/DataState";
import { StatusBadge } from "@/components/domain/StatusBadge";
import { slrImportClient, unwrap } from "@/features/slr-import/api/client";
import { cn } from "@/lib/utils";
import type { ArticleRow, ArticleText } from "./types";

type Props = {
  article: ArticleRow;
  open: boolean;
  filtered: boolean;
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
      unwrap(
        await api.GET("/v1/admin/corpus/articles/{article_id}/text", {
          params: { path: { article_id: article.id } },
        }),
      ) as ArticleText,
  });
  const total = article.phrases.pending + article.phrases.accepted + article.phrases.rejected;

  return (
    <Card className={cn("min-w-0", filtered && "border-foreground")}>
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div className="min-w-0">
          <CardTitle className="truncate text-base">{article.title || "Untitled article"}</CardTitle>
          <p className="mt-1 truncate text-sm text-muted-foreground">
            {article.journal ?? "Journal not recorded"} ·{" "}
            {article.ingest_status !== "ready" ? `ingest: ${article.ingest_status} · ` : ""}
            <span className="tabular-nums">{total}</span> phrases
          </p>
        </div>
        <StatusBadge status={article.mining_status} />
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          {article.phrases.pending > 0 ? <Badge variant="warning">{article.phrases.pending} pending</Badge> : null}
          {article.phrases.accepted > 0 ? <Badge variant="success">{article.phrases.accepted} accepted</Badge> : null}
          <Button variant="outline" size="sm" aria-expanded={open} onClick={onToggle}>
            {open ? "Close article" : "Open article"}
          </Button>
          {total > 0 || filtered ? (
            <Button variant={filtered ? "secondary" : "ghost"} size="sm" aria-pressed={filtered} onClick={onFilter}>
              {filtered ? "Clear phrase filter" : "Show phrases from this article"}
            </Button>
          ) : null}
        </div>
        {open ? (
          <div className="max-h-96 overflow-y-auto rounded-[var(--radius)] bg-muted/40 px-4 py-3 text-sm leading-6">
            {text.isPending ? (
              <DataState state="loading" loadingLabel="Loading article text" />
            ) : text.isError ? (
              <DataState
                state="error"
                errorTitle="Could not load article text"
                errorDescription={text.error.message}
                onRetry={() => void text.refetch()}
              />
            ) : (
              text.data.sections.map((section, index) => (
                <section key={`${article.id}-${index}`} className="mb-4 last:mb-0">
                  {section.heading ? <h3 className="mb-1 font-medium">{section.heading}</h3> : null}
                  <p>
                    {section.sentences.map((sentence) => (
                      <span key={sentence.id}>
                        {sourceSentenceIds.has(sentence.id) ? (
                          <mark className="rounded-[2px] bg-primary/10 px-1 text-foreground">{sentence.text}</mark>
                        ) : (
                          sentence.text
                        )}{" "}
                      </span>
                    ))}
                  </p>
                </section>
              ))
            )}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
