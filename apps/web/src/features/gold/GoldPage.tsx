import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { ApiError, unwrap } from "@/features/slr-import/api/client";
import { Badge, Card, Empty, Loading, PageHeader, Stat } from "@/shared/ui";
import { goldClient } from "./api";

type GoldItem = {
  id: string;
  sample_batch: string;
  split: string;
  section: string;
  status: string;
  ai_labels: Record<string, unknown> | null;
  final_labels: Record<string, unknown> | null;
};
type GoldDetail = GoldItem & {
  text: string;
  previous_text: string | null;
  next_text: string | null;
  section_heading: string | null;
};
type GoldStats = {
  total: number;
  by_status: Record<string, number>;
  by_split: Record<string, number>;
  field_edits: Record<string, number>;
};

export function GoldPage() {
  const client = goldClient();
  const queryClient = useQueryClient();
  const [status, setStatus] = useState("draft");
  const [split, setSplit] = useState("");
  const [section, setSection] = useState("");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<string>();
  const [labelsJson, setLabelsJson] = useState("");
  const [message, setMessage] = useState("");
  const items = useQuery({
    queryKey: ["gold-items", status, split, section, offset],
    refetchInterval: status === "pending_ai" ? 2500 : false,
    queryFn: async (): Promise<GoldItem[]> => {
      const data = unwrap(await client.GET("/v1/admin/gold/items", {
          params: { query: { status: status || undefined, split: split || undefined, section: section || undefined, offset, limit: 100 } },
      }));
      return (data ?? []) as unknown as GoldItem[];
    },
  });
  const stats = useQuery({
    queryKey: ["gold-stats"],
    queryFn: async (): Promise<GoldStats> => unwrap(await client.GET("/v1/admin/gold/stats")) as unknown as GoldStats,
  });
  const detail = useQuery({
    queryKey: ["gold-item", selected],
    enabled: Boolean(selected),
    queryFn: async (): Promise<GoldDetail> => unwrap(await client.GET("/v1/admin/gold/items/{item_id}", {
      params: { path: { item_id: selected! } },
    })) as unknown as GoldDetail,
  });

  useEffect(() => {
    setLabelsJson(detail.data?.ai_labels ? JSON.stringify(detail.data.ai_labels, null, 2) : "");
  }, [detail.data]);

  const review = useMutation({
    mutationFn: async ({ decision, useAiDraft }: { decision: "approve" | "reject"; useAiDraft?: boolean }) => {
      let final_labels: Record<string, unknown> | undefined;
      if (decision === "approve" && !useAiDraft && labelsJson.trim()) {
        const parsed: unknown = JSON.parse(labelsJson);
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("Nhãn phải là JSON object.");
        final_labels = parsed as Record<string, unknown>;
      }
      return unwrap(await client.POST("/v1/admin/gold/items/{item_id}/review", {
        params: { path: { item_id: selected! } },
        body: { decision, final_labels } as never,
      }));
    },
    onSuccess: () => {
      setMessage("Đã lưu quyết định duyệt.");
      void queryClient.invalidateQueries({ queryKey: ["gold-items"] });
      void queryClient.invalidateQueries({ queryKey: ["gold-stats"] });
      setSelected(undefined);
    },
    onError: (error) => setMessage(error instanceof ApiError ? error.message : error.message || "Không lưu được quyết định."),
  });
  const labelBatch = useMutation({
    mutationFn: async (sampleBatch: string) => unwrap(await client.POST(
      "/v1/admin/gold/samples/{sample_batch}/label",
      { params: { path: { sample_batch: sampleBatch } } },
    )),
    onSuccess: () => setMessage("Đã đưa job gán nhãn vào hàng đợi. Cần bật provider và quyền xử lý AI bên ngoài."),
    onError: (error) => setMessage(error instanceof ApiError ? error.message : error.message || "Không tạo được job gán nhãn."),
  });

  const current = detail.data;
  return (
    <div className="stack">
      <PageHeader
        code="GOLD · ONE HUMAN REVIEW"
        title="Gold review"
        lead="AI labels are drafts. Review the source sentence, then accept, edit, or reject each draft. Only approved human-reviewed labels enter the development gold set."
      />
      <div className="stat-row">
        <Stat label="Gold items" value={stats.data?.total ?? 0} note={`${stats.data?.by_status.approved ?? 0} approved`} />
        <Stat label="Awaiting review" value={stats.data?.by_status.draft ?? 0} note="AI drafts" />
        <Stat label="Test split" value={stats.data?.by_split.test ?? 0} note="Held aside from tuning" />
        <Stat label="Reviewed edits" value={Object.values(stats.data?.field_edits ?? {}).reduce((a, b) => a + b, 0)} note="Changed label fields" />
      </div>

      <div className="gold-layout">
        <Card title="Items" aside={<div className="filter-row">
          <select aria-label="Status" value={status} onChange={(event) => { setStatus(event.target.value); setOffset(0); }}>
            <option value="draft">AI draft</option><option value="pending_ai">Pending AI</option><option value="approved">Approved</option><option value="rejected">Rejected</option><option value="label_failed">Label failed</option>
          </select>
          <select aria-label="Split" value={split} onChange={(event) => { setSplit(event.target.value); setOffset(0); }}>
            <option value="">All splits</option><option value="dev">Dev</option><option value="test">Test</option>
          </select>
          <input aria-label="Section" placeholder="Section" value={section} onChange={(event) => { setSection(event.target.value); setOffset(0); }} />
        </div>}>
          {items.isPending ? <Loading /> : items.isError ? <p role="alert">{items.error.message}</p> : items.data.length === 0 ? <Empty>No gold items match these filters.</Empty> : (
            <ul className="entry-list">
              {items.data.map((item) => <li key={item.id}>
                <button className="gold-item-button" type="button" aria-pressed={selected === item.id} onClick={() => { setSelected(item.id); setMessage(""); }}>
                  <span><strong>{item.section}</strong> · {item.split}</span><Badge>{item.status}</Badge>
                  <code>{item.id.slice(0, 8)}</code>
                </button>
              </li>)}
            </ul>
          )}
          {!items.isPending && !items.isError && items.data.length > 0 && <div className="gold-actions">
            <button type="button" className="btn btn-ghost btn-sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 100))}>Previous</button>
            <span className="caption">Items {offset + 1}–{offset + items.data.length}</span>
            <button type="button" className="btn btn-ghost btn-sm" disabled={items.data.length < 100} onClick={() => setOffset(offset + 100)}>Next</button>
          </div>}
        </Card>

        <Card title={current?.section_heading || "Review item"}>
          {!selected ? <Empty>Select an item to inspect its source and labels.</Empty> : detail.isPending ? <Loading /> : detail.isError ? <p role="alert">{detail.error.message}</p> : current ? (
            <div className="gold-review">
              {current.previous_text && <p className="gold-context">{current.previous_text}</p>}
              <blockquote>{current.text}</blockquote>
              {current.next_text && <p className="gold-context">{current.next_text}</p>}
              <label className="field">
                <span className="field-label">AI draft labels · edit JSON before approval</span>
                <textarea rows={16} value={labelsJson} onChange={(event) => setLabelsJson(event.target.value)} spellCheck={false} />
              </label>
              {message && <p role="status">{message}</p>}
              {current.status === "pending_ai" && <button type="button" className="btn btn-ghost" disabled={labelBatch.isPending} onClick={() => labelBatch.mutate(current.sample_batch)}>Queue AI labeling for this batch</button>}
              <div className="gold-actions">
                <button type="button" className="btn btn-primary" disabled={review.isPending || current.status !== "draft"} onClick={() => review.mutate({ decision: "approve" })}>Approve / save edits</button>
                <button type="button" className="btn btn-ghost" disabled={review.isPending || current.status !== "draft"} onClick={() => review.mutate({ decision: "approve", useAiDraft: true })}>Approve AI labels</button>
                <button type="button" className="btn btn-ghost" disabled={review.isPending || current.status !== "draft"} onClick={() => review.mutate({ decision: "reject" })}>Reject</button>
              </div>
            </div>
          ) : null}
        </Card>
      </div>
    </div>
  );
}
