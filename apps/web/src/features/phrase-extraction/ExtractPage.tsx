import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";

import { useAuth } from "@/features/auth/AuthProvider";
import { ApiError, slrImportClient, unwrap } from "@/features/slr-import/api/client";
import { Badge, Card, Empty, Loading, PageHeader, Stat, Tabs, fmtTime } from "@/shared/ui";
import { ArticleCard } from "./ArticleCard";
import { PhraseCard } from "./PhraseCard";
import {
  NO_BATCH,
  PAGE_SIZE,
  batchToken,
  toScope,
  type ArticleRow,
  type Batch,
  type PhrasePage,
  type PhraseStatus,
} from "./types";

type Notice = { tone: "ok" | "bad"; text: string };
const errorText = (error: unknown) => (error instanceof ApiError || error instanceof Error ? error.message : "Yêu cầu thất bại.");
const MINING_IN_PROGRESS = ["queued", "processing"];

export function ExtractPage({ initialBatch }: { initialBatch?: string }) {
  const api = slrImportClient();
  const qc = useQueryClient();
  const auth = useAuth();
  const canMine = auth.client?.role === "curator" || auth.client?.role === "admin";

  // `null` means "not chosen yet": the newest batch is used until the user picks one.
  const [picked, setPicked] = useState<string[] | null>(initialBatch ? initialBatch.split(",").filter(Boolean) : null);
  const [status, setStatus] = useState<PhraseStatus>("pending");
  const [articleFilter, setArticleFilter] = useState<string>();
  const [articleSearch, setArticleSearch] = useState("");
  const [miningFilter, setMiningFilter] = useState("all");
  const [openIds, setOpenIds] = useState<Set<string>>(new Set());
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [offset, setOffset] = useState(0);
  const [notice, setNotice] = useState<Notice>();

  const batches = useQuery({
    queryKey: ["extract-batches"],
    queryFn: async (): Promise<Batch[]> => (unwrap(await api.GET("/v1/admin/corpus/batches")) ?? []) as Batch[],
  });
  const selected = picked ?? (batches.data?.[0] ? [batchToken(batches.data[0])] : []);
  const scope = toScope(selected);

  const articles = useQuery({
    queryKey: ["extract-articles", selected],
    enabled: selected.length > 0,
    refetchInterval: (query) => (query.state.data?.some((a) => MINING_IN_PROGRESS.includes(a.mining_status)) ? 3000 : false),
    queryFn: async (): Promise<ArticleRow[]> =>
      (unwrap(await api.GET("/v1/admin/corpus/articles", { params: { query: scope } })) ?? []) as ArticleRow[],
  });
  const inProgress = articles.data?.some((a) => MINING_IN_PROGRESS.includes(a.mining_status)) ?? false;

  const phraseScope = articleFilter ? { article_id: [articleFilter], batch_id: [], unbatched: false } : scope;
  const phrases = useQuery({
    queryKey: ["extract-phrases", status, selected, articleFilter, offset],
    enabled: selected.length > 0,
    refetchInterval: inProgress ? 4000 : false,
    queryFn: async (): Promise<PhrasePage> =>
      unwrap(await api.GET("/v1/admin/extraction/phrases", { params: { query: { status, limit: PAGE_SIZE, offset, ...phraseScope } } })) as PhrasePage,
  });

  const refresh = () => {
    for (const key of ["extract-batches", "extract-articles", "extract-phrases"]) void qc.invalidateQueries({ queryKey: [key] });
  };

  // When the last mining job finishes, pull the final counts and phrases once.
  const wasInProgress = useRef(false);
  useEffect(() => {
    if (wasInProgress.current && !inProgress) {
      void qc.invalidateQueries({ queryKey: ["extract-batches"] });
      void qc.invalidateQueries({ queryKey: ["extract-phrases"] });
    }
    wasInProgress.current = inProgress;
  }, [inProgress, qc]);

  const mine = useMutation({
    mutationFn: async () =>
      unwrap(await api.POST("/v1/admin/corpus/mine", { body: { article_ids: [], batch_ids: scope.batch_id, unbatched: scope.unbatched } })),
    onSuccess: (result) => {
      setNotice({
        tone: "ok",
        text: `Đã đưa ${result?.job_ids.length ?? 0} bài vào hàng đợi trích xuất${result?.skipped_not_ready ? `, bỏ qua ${result.skipped_not_ready} bài chưa sẵn sàng` : ""}.`,
      });
      refresh();
    },
    onError: (error) => setNotice({ tone: "bad", text: errorText(error) }),
  });
  const decide = useMutation({
    mutationFn: async ({ id, decision }: { id: string; decision: "accept" | "reject" }) =>
      unwrap(await api.POST("/v1/admin/extraction/phrases/{candidate_id}/decision", { params: { path: { candidate_id: id } }, body: { decision } })),
    onSuccess: (_, { decision }) => {
      setNotice({ tone: "ok", text: decision === "accept" ? "Đã chấp nhận và lưu vào DB." : "Đã từ chối phrase." });
      refresh();
    },
    onError: (error) => setNotice({ tone: "bad", text: errorText(error) }),
  });
  const decideMany = useMutation({
    mutationFn: async (decision: "accept" | "reject") =>
      unwrap(await api.POST("/v1/admin/extraction/phrases/decisions", { body: { candidate_ids: [...checked], decision } })),
    onSuccess: (result) => {
      const failed = result?.failed.length ?? 0;
      setNotice({
        tone: failed ? "bad" : "ok",
        text: `${result?.results.length ?? 0} phrase đã xử lý${failed ? `, ${failed} phrase lỗi: ${result?.failed[0].reason}` : ""}.`,
      });
      setChecked(new Set());
      refresh();
    },
    onError: (error) => setNotice({ tone: "bad", text: errorText(error) }),
  });

  const chosenBatches = batches.data?.filter((b) => selected.includes(batchToken(b))) ?? [];
  const sum = (pick: (b: Batch) => number) => chosenBatches.reduce((total, b) => total + pick(b), 0);
  const counts = { pending: sum((b) => b.phrases.pending), accepted: sum((b) => b.phrases.accepted), rejected: sum((b) => b.phrases.rejected) };
  const ready = articles.data?.filter((a) => a.ingest_status === "ready") ?? [];
  const mineable = ready.filter((a) => a.mining_status === "not_started" || a.mining_status === "failed").length;
  // Once everything is mined the phrases are the point of the page, so they take the wide column.
  const phrasesFirst = ready.length > 0 && ready.every((a) => a.mining_status === "succeeded");
  const items = phrases.data?.items ?? [];
  const total = phrases.data?.total ?? 0;
  const sourceSentenceIds = new Set(items.flatMap((phrase) => phrase.sources.map((source) => source.sentence_id)));
  const busy = decide.isPending || decideMany.isPending;

  const filteredArticles = useMemo(() => {
    if (!articles.data) return [];
    return articles.data.filter((article) => {
      if (articleSearch.trim()) {
        const q = articleSearch.trim().toLowerCase();
        const title = (article.title ?? "").toLowerCase();
        const doi = (article.doi ?? "").toLowerCase();
        if (!title.includes(q) && !doi.includes(q)) return false;
      }
      if (miningFilter !== "all") {
        if (miningFilter === "not_started" && article.mining_status !== "not_started") return false;
        if (
          miningFilter === "running" &&
          article.mining_status !== "queued" &&
          article.mining_status !== "processing"
        )
          return false;
        if (miningFilter === "succeeded" && article.mining_status !== "succeeded") return false;
        if (miningFilter === "failed" && article.mining_status !== "failed") return false;
      }
      return true;
    });
  }, [articles.data, articleSearch, miningFilter]);

  const changeScope = (next: string[]) => {
    setPicked(next);
    setArticleFilter(undefined);
    setArticleSearch("");
    setMiningFilter("all");
    setChecked(new Set());
    setOffset(0);
  };
  const toggleBatch = (token: string) => changeScope(selected.includes(token) ? selected.filter((t) => t !== token) : [...selected, token]);
  const toggle = (set: Set<string>, id: string, on: boolean) => {
    const next = new Set(set);
    if (on) next.add(id);
    else next.delete(id);
    return next;
  };
  const changeStatus = (next: PhraseStatus) => {
    setStatus(next);
    setChecked(new Set());
    setOffset(0);
  };
  const allChecked = items.length > 0 && items.every((phrase) => checked.has(phrase.id));

  return (
    <div className="stack">
      <PageHeader
        code="CORPUS · PHRASE EXTRACTION"
        title="Trích xuất phrase"
        lead="Chọn một hoặc nhiều batch đã import, trích xuất phrase, rồi chấp nhận hoặc từ chối từng phrase. Phrase được chấp nhận sẽ được lưu vào DB cùng bài, câu nguồn và journal."
      />

      <Card
        title="Batch đã import"
        aside={
          <button
            type="button"
            className="btn btn-primary"
            disabled={!canMine || mine.isPending || mineable === 0}
            title={canMine ? undefined : "Cần quyền curator để trích xuất"}
            onClick={() => mine.mutate()}
          >
            {mine.isPending ? "Đang tạo job..." : `Trích xuất ${mineable} bài`} <span className="arrow">→</span>
          </button>
        }
      >
        {batches.isPending ? <Loading /> : batches.isError ? <p className="notice notice-bad" role="alert">{batches.error.message}</p> : batches.data.length === 0 ? (
          <Empty>Chưa có bài nào được import. Vào trang Import để lấy bài báo trước.</Empty>
        ) : (
          <ul className="extract-batches">
            {batches.data.map((batch) => {
              const token = batchToken(batch);
              return (
                <li key={token}>
                  <label className="choice">
                    <input type="checkbox" checked={selected.includes(token)} onChange={() => toggleBatch(token)} />
                    <span>
                      <strong>{batch.batch_id === null ? "Không thuộc batch" : `Import ${fmtTime(batch.imported_at)}`}</strong>
                      <span className="field-hint">
                        {batch.articles} bài · {batch.ready} sẵn sàng · {batch.mined} đã trích xuất · {batch.phrases.pending} phrase chờ duyệt
                      </span>
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
        )}
        {notice && <p className={`notice notice-${notice.tone}`} role="status">{notice.text}</p>}
        {inProgress && <p className="caption">Đang trích xuất... phrase sẽ xuất hiện khi worker xử lý xong (cần chạy <code>make worker</code>).</p>}
        {selected.includes(NO_BATCH) && (
          <p className="caption extract-batch-note">
            “Không thuộc batch” gồm các bài upload tay hoặc import trước khi có batch.
          </p>
        )}
      </Card>

      {selected.length > 0 && (
        <>
          <div className="stat-row">
            <Stat label="Bài đã chọn" value={sum((b) => b.articles)} note={`${sum((b) => b.ready)} sẵn sàng`} />
            <Stat label="Đã trích xuất" value={sum((b) => b.mined)} />
            <Stat label="Phrase chờ duyệt" value={counts.pending} tone={counts.pending ? "warn" : undefined} />
            <Stat label="Đã chấp nhận" value={counts.accepted} tone="ok" />
          </div>

          <div className={`extract-layout${phrasesFirst ? " extract-layout--phrases-first" : ""}`}>
            <div className="stack extract-articles">
              <div className="extract-pane-header">
                <div className="extract-pane-title-row">
                  <div className="tabs extract-articles-tabs" role="tablist" aria-label="Danh sách bài báo">
                    <button type="button" role="tab" aria-selected="true" className="tab">
                      Bài báo <span className="tab-count">{filteredArticles.length}</span>
                    </button>
                  </div>
                  <div className="extract-pane-title-meta">
                    {articleFilter && <Badge tone="info">Đang lọc 1 bài</Badge>}
                    <span className="caption">
                      {articles.data?.length ?? 0} bài trong batch · {ready.length} sẵn sàng
                    </span>
                    {articleFilter && (
                      <button
                        type="button"
                        className="btn-link extract-clear-filter"
                        onClick={() => {
                          setArticleFilter(undefined);
                          setChecked(new Set());
                          setOffset(0);
                        }}
                      >
                        Bỏ lọc bài
                      </button>
                    )}
                  </div>
                </div>
                <div className="extract-articles-toolbar">
                  <input
                    type="search"
                    className="extract-article-search"
                    placeholder="Tìm theo tiêu đề bài..."
                    value={articleSearch}
                    onChange={(e) => setArticleSearch(e.target.value)}
                    aria-label="Tìm theo tiêu đề bài"
                  />
                  <select
                    className="extract-article-filter-select"
                    value={miningFilter}
                    onChange={(e) => setMiningFilter(e.target.value)}
                    aria-label="Lọc theo trạng thái mining"
                  >
                    <option value="all">Tất cả</option>
                    <option value="not_started">Chưa trích xuất</option>
                    <option value="running">Đang chạy</option>
                    <option value="succeeded">Thành công</option>
                    <option value="failed">Lỗi</option>
                  </select>
                </div>
              </div>

              {articles.isPending ? (
                <Loading />
              ) : articles.isError ? (
                <p className="notice notice-bad" role="alert">{articles.error.message}</p>
              ) : articles.data.length === 0 ? (
                <Empty>Batch này chưa có bài.</Empty>
              ) : filteredArticles.length === 0 ? (
                <Empty>Không có bài báo nào khớp với bộ lọc.</Empty>
              ) : (
                <div className="extract-articles-list">
                  {filteredArticles.map((article) => (
                    <ArticleCard
                      key={article.id}
                      article={article}
                      open={openIds.has(article.id)}
                      filtered={articleFilter === article.id}
                      sourceSentenceIds={sourceSentenceIds}
                      onToggle={() => setOpenIds((old) => toggle(old, article.id, !old.has(article.id)))}
                      onFilter={() => {
                        setArticleFilter(articleFilter === article.id ? undefined : article.id);
                        setChecked(new Set());
                        setOffset(0);
                      }}
                    />
                  ))}
                </div>
              )}
            </div>

            <div className="stack extract-phrases">
              <div className="extract-pane-header">
                <Tabs
                  label="Trạng thái phrase"
                  value={status}
                  onChange={changeStatus}
                  items={[
                    { id: "pending", label: "Chờ duyệt", count: counts.pending },
                    { id: "accepted", label: "Đã chấp nhận", count: counts.accepted },
                    { id: "rejected", label: "Đã từ chối", count: counts.rejected },
                  ]}
                >
                  {status === "pending" && items.length > 0 ? (
                    <div className="extract-bulk-toolbar">
                      <div className="extract-bulk-left">
                        <label className="extract-bulk-select-label">
                          <input
                            type="checkbox"
                            ref={(el) => {
                              if (el) el.indeterminate = checked.size > 0 && !allChecked;
                            }}
                            checked={allChecked}
                            onChange={(event) =>
                              setChecked(event.target.checked ? new Set(items.map((p) => p.id)) : new Set())
                            }
                            aria-label="Chọn cả trang"
                          />
                          <span>Chọn cả trang ({items.length})</span>
                        </label>
                        {checked.size > 0 && (
                          <div className="extract-bulk-counter">
                            <span>Đã chọn <strong>{checked.size}</strong></span>
                            <button
                              type="button"
                              className="btn-link extract-bulk-clear"
                              onClick={() => setChecked(new Set())}
                            >
                              Bỏ chọn
                            </button>
                          </div>
                        )}
                      </div>
                      <div className="extract-bulk-actions">
                        <button
                          type="button"
                          className="btn btn-sm btn-ghost btn-decision-reject"
                          disabled={busy || checked.size === 0}
                          onClick={() => decideMany.mutate("reject")}
                        >
                          <span className="phrase-btn-symbol" aria-hidden="true">✕</span>
                          Từ chối {checked.size ? `(${checked.size})` : ""}
                        </button>
                        <button
                          type="button"
                          className="btn btn-sm btn-primary btn-decision-accept"
                          disabled={busy || checked.size === 0}
                          onClick={() => decideMany.mutate("accept")}
                        >
                          <span className="phrase-btn-symbol" aria-hidden="true">✓</span>
                          Chấp nhận {checked.size ? `(${checked.size})` : ""}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="extract-bulk-toolbar extract-bulk-toolbar--info">
                      <span className="caption">
                        {items.length === 0
                          ? "Danh sách trống"
                          : `Đang hiển thị ${items.length} phrase ${status === "accepted" ? "đã chấp nhận" : status === "rejected" ? "đã từ chối" : "chờ duyệt"}`}
                      </span>
                    </div>
                  )}
                </Tabs>
              </div>

              <div className="extract-phrases-content">
                {phrases.isPending ? (
                  <Loading />
                ) : phrases.isError ? (
                  <p className="notice notice-bad" role="alert">{phrases.error.message}</p>
                ) : items.length === 0 ? (
                  <Empty>
                    {inProgress
                      ? "Đang trích xuất... phrase sẽ xuất hiện khi worker xử lý xong (cần chạy make worker)."
                      : status === "pending"
                        ? "Chưa có phrase nào chờ duyệt. Bấm “Trích xuất” nếu bài chưa được xử lý."
                        : "Chưa có phrase nào ở trạng thái này."}
                  </Empty>
                ) : (
                  <div className="phrase-list-wrap">
                    <ol className="candidate-list phrase-list">
                      {items.map((phrase) => (
                        <li key={phrase.id}>
                          <PhraseCard
                            phrase={phrase}
                            checked={checked.has(phrase.id)}
                            busy={busy}
                            onCheck={(on) => setChecked((old) => toggle(old, phrase.id, on))}
                            onDecide={(decision) => decide.mutate({ id: phrase.id, decision })}
                          />
                        </li>
                      ))}
                    </ol>
                  </div>
                )}
                {total > PAGE_SIZE && (
                  <div className="extract-pagination">
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      disabled={offset === 0}
                      onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                    >
                      ← Trang trước
                    </button>
                    <span className="caption">
                      {offset + 1}–{offset + items.length} / {total} phrase
                    </span>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      disabled={offset + PAGE_SIZE >= total}
                      onClick={() => setOffset(offset + PAGE_SIZE)}
                    >
                      Trang sau →
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
