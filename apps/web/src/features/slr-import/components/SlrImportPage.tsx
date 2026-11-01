import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Badge, Card, Empty, Field, Loading, PageHeader, Stat, StatusBadge } from "@/shared/ui";
import { ApiError, slrImportClient, unwrap } from "../api/client";

const kinds = ["FULLTEXT_MARKDOWN", "FETCHER_FULLTEXT_MARKDOWN", "SOURCE_PDF"] as const;
type Kind = typeof kinds[number];
type Profile = { id: string; name: string; filters: Record<string, unknown>; artifact_kinds: string[]; batch_limit: number; is_active: boolean };
type JobResult = {
  listed?: number;
  imported?: number;
  skipped_license?: number;
  skipped_duplicate?: number;
  skipped_format?: number;
  skipped_invalid_content?: number;
  continuation_job_id?: string | null;
};
const taxonFields: Record<string, string> = { domain: "domainId", field: "fieldId", subfield: "subfieldId", topic: "topicId" };
type TaxonomyPage = { items: { id: string; label: string }[]; nextCursor: string | null };

function taxonomyQuery(api: ReturnType<typeof slrImportClient>, level: string, parentId?: string, enabled = true) {
  return {
    queryKey: ["slr-taxonomy", level, parentId],
    enabled,
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }: { pageParam: string | undefined }): Promise<TaxonomyPage> => {
      const data = unwrap(
        await api.GET("/v1/admin/corpus/sources/slr/taxonomy", {
          params: { query: { level, parentId, cursor: pageParam, limit: 100 } },
        }),
      );
      if (!data) throw new Error("SLR taxonomy returned an empty response.");
      return data as unknown as TaxonomyPage;
    },
    getNextPageParam: (lastPage: TaxonomyPage | undefined) => lastPage?.nextCursor ?? undefined,
  };
}

export function SlrImportPage() {
  const api = slrImportClient();
  const qc = useQueryClient();

  const [key, setKey] = useState(sessionStorage.getItem("aprkb-api-key") ?? "");
  const [hasSavedKey, setHasSavedKey] = useState(Boolean(sessionStorage.getItem("aprkb-api-key")));
  const [selected, setSelected] = useState<string>();
  const [name, setName] = useState("");
  const [filters, setFilters] = useState<Record<string, string | boolean>>({ hasFullText: true });
  const [artifactKinds, setArtifactKinds] = useState<Kind[]>([...kinds]);
  const [batchLimit, setBatchLimit] = useState(25);
  const [jobId, setJobId] = useState<string>();
  const [startError, setStartError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [saveMessage, setSaveMessage] = useState("");

  const profiles = useQuery({
    queryKey: ["slr-import-profiles"],
    queryFn: async () => {
      const data = unwrap(await api.GET("/v1/admin/corpus/import-profiles"));
      return (data ?? []) as Profile[];
    },
  });

  const profile = profiles.data?.find((p) => p.id === selected);

  const taxonomyLevels = ["domain", "field", "subfield", "topic"] as const;
  const taxonomyQueries = [
    useInfiniteQuery(taxonomyQuery(api, "domain")),
    useInfiniteQuery(taxonomyQuery(api, "field", String(filters.domainId ?? "") || undefined, Boolean(filters.domainId))),
    useInfiniteQuery(taxonomyQuery(api, "subfield", String(filters.fieldId ?? "") || undefined, Boolean(filters.fieldId))),
    useInfiniteQuery(taxonomyQuery(api, "topic", String(filters.subfieldId ?? "") || undefined, Boolean(filters.subfieldId))),
  ];

  const handleSaveKey = () => {
    sessionStorage.setItem("aprkb-api-key", key);
    setHasSavedKey(Boolean(key));
    void qc.invalidateQueries();
  };

  const handleClearKey = () => {
    sessionStorage.removeItem("aprkb-api-key");
    setKey("");
    setHasSavedKey(false);
    void qc.invalidateQueries();
  };

  const handleSelectProfile = (p: Profile) => {
    setSelected(p.id);
    setName(p.name);
    setFilters((p.filters as Record<string, string | boolean>) ?? { hasFullText: true });
    setArtifactKinds((p.artifact_kinds as Kind[]) ?? [...kinds]);
    setBatchLimit(p.batch_limit ?? 25);
    setFieldErrors({});
    setSaveMessage("");
  };

  const handleCreateNew = () => {
    setSelected(undefined);
    setName("");
    setFilters({ hasFullText: true });
    setArtifactKinds([...kinds]);
    setBatchLimit(25);
    setFieldErrors({});
    setSaveMessage("");
  };

  const save = useMutation({
    mutationFn: async () => {
      const filterBody: Record<string, unknown> = Object.fromEntries(
        Object.entries(filters).filter(([, v]) => v !== ""),
      );
      for (const yearKey of ["yearFrom", "yearTo"]) {
        if (typeof filterBody[yearKey] === "string") filterBody[yearKey] = Number(filterBody[yearKey]);
      }
      filterBody.hasFullText = filters.hasFullText !== false;
      const body = {
        name,
        source: "slr" as const,
        is_active: true,
        filters: filterBody,
        artifact_kinds: artifactKinds,
        batch_limit: batchLimit,
      };
      const res = selected
        ? await api.PATCH("/v1/admin/corpus/import-profiles/{profile_id}", {
            params: { path: { profile_id: selected } },
            body: { name, filters: filterBody, artifact_kinds: artifactKinds, batch_limit: batchLimit } as never,
          })
        : await api.POST("/v1/admin/corpus/import-profiles", { body: body as never });
      return unwrap(res);
    },
    onSuccess: (created) => {
      setFieldErrors({});
      setSaveMessage("Lưu profile thành công.");
      if (!selected && created?.id) setSelected(created.id);
      void qc.invalidateQueries({ queryKey: ["slr-import-profiles"] });
    },
    onError: (error) => {
      const details = error instanceof ApiError ? error.body?.error?.details?.errors : undefined;
      const mapped: Record<string, string> = {};
      for (const item of details ?? []) mapped[String(item.loc.at(-1) ?? "form")] = item.msg;
      setFieldErrors(mapped);
      setSaveMessage(details ? "Vui lòng kiểm tra các trường được đánh dấu." : error.message);
    },
  });

  const start = useMutation({
    mutationFn: async () => {
      return unwrap(await api.POST("/v1/admin/corpus/imports", { body: { profile_id: selected } }))?.job_id;
    },
    onSuccess: (id) => {
      setStartError("");
      if (id) setJobId(id);
    },
    onError: (error) => {
      setStartError(error.message || "Không thể tạo job import. Vui lòng thử lại.");
    },
  });

  const job = useQuery({
    queryKey: ["slr-job", jobId],
    enabled: !!jobId,
    refetchInterval: (q) => (["done", "failed", "succeeded"].includes(q.state.data?.status ?? "") ? false : 2500),
    queryFn: async () => {
      const data = unwrap(await api.GET("/v1/admin/jobs/{job_id}", { params: { path: { job_id: jobId! } } }));
      return data as { status: string; error?: string; result?: JobResult };
    },
  });

  const setFilter = (fieldName: string, value: string | boolean) =>
    setFilters((old) => {
      const next = { ...old, [fieldName]: value };
      if (fieldName === "domainId") {
        delete next.fieldId;
        delete next.subfieldId;
        delete next.topicId;
      }
      if (fieldName === "fieldId") {
        delete next.subfieldId;
        delete next.topicId;
      }
      if (fieldName === "subfieldId") delete next.topicId;
      return next;
    });

  const moveKind = (index: number, by: number) =>
    setArtifactKinds((old) => {
      const next = [...old];
      const to = index + by;
      if (to < 0 || to >= next.length) return old;
      [next[index], next[to]] = [next[to], next[index]];
      return next;
    });

  const pdfFirst = artifactKinds[0] === "SOURCE_PDF" && artifactKinds.some((k) => k.includes("MARKDOWN"));
  const result = job.data?.result;

  return (
    <div className="stack">
      <PageHeader
        code="CORPUS · SLR IMPORT"
        title="Import từ SLR"
        lead="Cấu hình bộ lọc bài báo từ SLR Repository và giám sát tiến trình nhập dữ liệu vào kho."
      />

      {/* AP-RKB API Authentication Card */}
      <Card
        title="Xác thực AP-RKB API"
        aside={hasSavedKey ? <Badge tone="ok">Đã lưu trong phiên</Badge> : <Badge tone="warn">Chưa có API key</Badge>}
      >
        <div className="slr-apikey-bar">
          <div className="field" style={{ flex: 1, minWidth: "260px", margin: 0 }}>
            <input
              type="password"
              placeholder="Nhập X-API-Key để truy cập /v1/admin/corpus/*"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              autoComplete="off"
            />
          </div>
          <button type="button" className="btn btn-primary" onClick={handleSaveKey}>
            Lưu key phiên này
          </button>
          {hasSavedKey && (
            <button type="button" className="btn btn-ghost" onClick={handleClearKey}>
              Xóa key
            </button>
          )}
        </div>
        <p className="caption">
          Key được lưu tạm trong <code>sessionStorage</code> và gửi qua header <code>X-API-Key</code> trong các yêu cầu quản trị.
        </p>
      </Card>

      <div className="slr-layout">
        {/* Column 1: Profiles List */}
        <aside className="slr-sidebar">
          <Card
            title="Import Profiles"
            aside={
              <button type="button" className="btn btn-ghost btn-sm" onClick={handleCreateNew}>
                + Mới
              </button>
            }
          >
            {profiles.isPending ? (
              <Loading />
            ) : profiles.isError ? (
              <div className="notice notice-bad" role="alert">
                Không tải được danh sách profile: {profiles.error.message}
              </div>
            ) : profiles.data.length === 0 ? (
              <Empty>Chưa có profile nào. Bấm nút phía trên để tạo mới.</Empty>
            ) : (
              <ul className="entry-list">
                {profiles.data?.map((p) => {
                  const isSelected = p.id === selected;
                  return (
                    <li key={p.id}>
                      <button
                        type="button"
                        className="entry"
                        aria-current={isSelected}
                        onClick={() => handleSelectProfile(p)}
                      >
                        <span className="entry-head">
                          <strong>{p.name}</strong>
                          <Badge tone={p.is_active ? "ok" : "neutral"}>
                            {p.is_active ? "Active" : "Inactive"}
                          </Badge>
                        </span>
                        <span className="entry-meta">
                          Batch: {p.batch_limit} bài · {p.artifact_kinds?.length ?? 0} định dạng
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
            <button
              type="button"
              className="btn btn-ghost"
              style={{ width: "100%", marginTop: 12 }}
              onClick={handleCreateNew}
            >
              + Tạo profile mới
            </button>
          </Card>
        </aside>

        {/* Column 2: Profile Editor Form */}
        <form
          className="stack"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
        >
          <Card
            title={selected ? `Sửa profile: ${name || "Chưa đặt tên"}` : "Tạo profile mới"}
            aside={selected && <Badge tone="info">ID: {selected.slice(0, 8)}</Badge>}
          >
            <Field label="Tên profile" hint="Tên định danh phân biệt mục đích lấy bài báo" error={fieldErrors.name}>
              <input
                required
                placeholder="VD: Deep Learning in Healthcare 2020-2025"
                value={name}
                aria-invalid={!!fieldErrors.name}
                onChange={(e) => setName(e.target.value)}
              />
            </Field>

            {/* Taxonomy Hierarchy */}
            <div className="form-section-title">Phân loại SLR (Taxonomy)</div>
            <p className="caption" style={{ marginTop: -4, marginBottom: 12 }}>
              Chọn phân cấp từ Domain đến Topic. Các cấp con tự động lọc theo cấp cha đã chọn.
            </p>

            {taxonomyQueries.some((query) => query.isError) && (
              <div className="notice notice-warn">Không tải được danh mục SLR. Hãy kiểm tra API key và thử lại.</div>
            )}

            <div className="taxonomy-grid">
              {taxonomyLevels.map((level, index) => {
                const keyName = taxonFields[level];
                const query = taxonomyQueries[index];
                const items = query.data?.pages.flatMap((page) => page.items) ?? [];
                const parentKey = index > 0 ? taxonFields[taxonomyLevels[index - 1]] : null;
                const isDisabled = index > 0 && !filters[parentKey!];
                const levelLabels: Record<string, string> = {
                  domain: "Domain (Lĩnh vực)",
                  field: "Field (Ngành)",
                  subfield: "Subfield (Chuyên ngành)",
                  topic: "Topic (Chủ đề)",
                };

                return (
                  <div key={level} className="taxonomy-level-box">
                    <Field label={levelLabels[level] ?? level}>
                      <select
                        disabled={isDisabled}
                        value={String(filters[keyName] ?? "")}
                        onChange={(e) => setFilter(keyName, e.target.value)}
                      >
                        <option value="">-- Tất cả {level} --</option>
                        {items.map((item) => (
                          <option key={item.id} value={item.id}>
                            {item.label}
                          </option>
                        ))}
                      </select>
                    </Field>
                    {query.hasNextPage && (
                      <button
                        type="button"
                        className="btn btn-link small"
                        style={{ alignSelf: "flex-start", marginTop: 2 }}
                        disabled={query.isFetchingNextPage}
                        onClick={() => void query.fetchNextPage()}
                      >
                        {query.isFetchingNextPage ? "Đang tải thêm..." : `+ Tải thêm ${level}`}
                      </button>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Filter Criteria */}
            <div className="form-section-title">Tiêu chí lọc bài báo</div>

            <div className="grid-2">
              <Field label="Năm xuất bản từ" error={fieldErrors.yearFrom}>
                <input
                  type="number"
                  placeholder="2020"
                  aria-invalid={!!fieldErrors.yearFrom}
                  value={String(filters.yearFrom ?? "")}
                  onChange={(e) => setFilter("yearFrom", e.target.value)}
                />
              </Field>
              <Field label="Năm xuất bản đến" error={fieldErrors.yearTo}>
                <input
                  type="number"
                  placeholder="2026"
                  aria-invalid={!!fieldErrors.yearTo}
                  value={String(filters.yearTo ?? "")}
                  onChange={(e) => setFilter("yearTo", e.target.value)}
                />
              </Field>
            </div>

            <div className="grid-2">
              <Field label="Ngôn ngữ" hint="Mã ISO (VD: en, vi)" error={fieldErrors.language}>
                <input
                  placeholder="en"
                  aria-invalid={!!fieldErrors.language}
                  value={String(filters.language ?? "")}
                  onChange={(e) => setFilter("language", e.target.value)}
                />
              </Field>
              <Field label="Loại bài báo" hint="VD: journal-article" error={fieldErrors.publicationType}>
                <input
                  placeholder="journal-article"
                  aria-invalid={!!fieldErrors.publicationType}
                  value={String(filters.publicationType ?? "")}
                  onChange={(e) => setFilter("publicationType", e.target.value)}
                />
              </Field>
            </div>

            <div className="grid-2">
              <Field label="Tên tạp chí" error={fieldErrors.journal}>
                <input
                  placeholder="VD: Nature Machine Intelligence"
                  aria-invalid={!!fieldErrors.journal}
                  value={String(filters.journal ?? "")}
                  onChange={(e) => setFilter("journal", e.target.value)}
                />
              </Field>
              <Field label="Mã ISSN" error={fieldErrors.journalIssn}>
                <input
                  placeholder="VD: 2522-5839"
                  aria-invalid={!!fieldErrors.journalIssn}
                  value={String(filters.journalIssn ?? "")}
                  onChange={(e) => setFilter("journalIssn", e.target.value)}
                />
              </Field>
            </div>

            <Field label="Từ khóa tìm kiếm (q)" hint="Tìm kiếm theo chuỗi trong tiêu đề hoặc metadata" error={fieldErrors.q}>
              <input
                type="search"
                placeholder="VD: rhetorical moves academic phraseology"
                aria-invalid={!!fieldErrors.q}
                value={String(filters.q ?? "")}
                onChange={(e) => setFilter("q", e.target.value)}
              />
            </Field>

            <div className="grid-2" style={{ alignItems: "flex-start", marginTop: 8 }}>
              <Field label="Số bài mỗi lượt (Batch limit)" hint="Giới hạn số bài trong một lần import (1 - 100)">
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={batchLimit}
                  onChange={(e) => setBatchLimit(Number(e.target.value))}
                />
              </Field>
              <div className="field">
                <span className="field-label">Điều kiện toàn văn</span>
                <label className="choice" style={{ margin: 0 }}>
                  <input
                    type="checkbox"
                    checked={filters.hasFullText !== false}
                    onChange={(e) => setFilter("hasFullText", e.target.checked)}
                  />
                  <span>
                    <strong>Chỉ bài có full text</strong>
                    <span className="field-hint">Bỏ qua các bài chỉ có abstract hoặc metadata</span>
                  </span>
                </label>
              </div>
            </div>

            {/* Artifact Kinds Priority */}
            <div className="form-section-title">Thứ tự ưu tiên định dạng file (Artifact Kinds)</div>
            <p className="caption" style={{ marginTop: -4, marginBottom: 12 }}>
              Hệ thống thử tải theo thứ tự từ trên xuống dưới. Định dạng đứng đầu được ưu tiên nhất.
            </p>

            <div className="artifact-kinds-list">
              {artifactKinds.map((kind, index) => (
                <div key={kind} className="artifact-kind-item">
                  <label className="artifact-kind-label">
                    <input
                      type="checkbox"
                      checked={true}
                      onChange={() => setArtifactKinds((old) => old.filter((k) => k !== kind))}
                    />
                    <Badge tone="info">#{index + 1}</Badge>
                    <span>{kind.replaceAll("_", " ")}</span>
                  </label>
                  <div className="artifact-kind-actions">
                    <button
                      type="button"
                      className="btn btn-ghost btn-icon"
                      aria-label={`Đưa ${kind} lên`}
                      disabled={index === 0}
                      onClick={() => moveKind(index, -1)}
                      title="Tăng độ ưu tiên"
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      className="btn btn-ghost btn-icon"
                      aria-label={`Đưa ${kind} xuống`}
                      disabled={index === artifactKinds.length - 1}
                      onClick={() => moveKind(index, 1)}
                      title="Giảm độ ưu tiên"
                    >
                      ↓
                    </button>
                  </div>
                </div>
              ))}

              {kinds
                .filter((k) => !artifactKinds.includes(k))
                .map((kind) => (
                  <div key={kind} className="artifact-kind-item" style={{ opacity: 0.65 }}>
                    <label className="artifact-kind-label">
                      <input
                        type="checkbox"
                        checked={false}
                        onChange={() => setArtifactKinds((old) => [...old, kind])}
                      />
                      <Badge tone="neutral">Đã tắt</Badge>
                      <span>{kind.replaceAll("_", " ")}</span>
                    </label>
                  </div>
                ))}
            </div>

            {pdfFirst && (
              <div className="notice notice-warn">
                ⚠️ <strong>Lưu ý:</strong> PDF chưa được parse (parser đang là stub). Bài báo sẽ được lưu nhưng chưa thể mining được nội dung cho đến khi có parser. Nên ưu tiên Markdown trước.
              </div>
            )}

            {saveMessage && (
              <div className={`notice ${save.isError ? "notice-bad" : "notice-ok"}`} role="alert">
                {saveMessage}
              </div>
            )}

            <div className="card-actions" style={{ marginTop: 20 }}>
              <button type="submit" className="btn btn-primary" disabled={save.isPending}>
                {save.isPending ? "Đang lưu..." : selected ? "Cập nhật profile" : "Lưu profile mới"}
              </button>
              {selected && (
                <button type="button" className="btn btn-ghost" onClick={handleCreateNew}>
                  Hủy chọn / Tạo mới
                </button>
              )}
            </div>
          </Card>
        </form>

        {/* Column 3: Execution & Job Progress Monitoring */}
        <aside className="slr-monitor">
          <Card
            title="Tiến độ Import"
            aside={job.data?.status && <StatusBadge status={job.data.status} />}
          >
            {!selected ? (
              <div className="notice notice-warn" style={{ marginTop: 0 }}>
                Vui lòng chọn một profile từ danh sách hoặc tạo mới để bắt đầu lấy bài báo.
              </div>
            ) : (
              <>
                <div className="profile-summary-box">
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                    <strong>{profile?.name || name}</strong>
                    <StatusBadge status={profile?.is_active ? "active" : "draft"} />
                  </div>
                  <div className="small muted">
                    Giới hạn: {batchLimit} bài/lượt · {artifactKinds.length} định dạng
                  </div>
                </div>

                <button
                  type="button"
                  className="btn btn-primary"
                  style={{ width: "100%", minHeight: 44 }}
                  disabled={!selected || !profile?.is_active || start.isPending}
                  onClick={() => start.mutate()}
                >
                  {start.isPending ? "Đang tạo job..." : "Lấy bài báo"} <span className="arrow">→</span>
                </button>

                {!profile?.is_active && (
                  <p className="caption" style={{ color: "var(--color-warning)" }}>
                    Profile này đang ở trạng thái không kích hoạt (inactive).
                  </p>
                )}

                {startError && (
                  <div className="notice notice-bad" role="alert">
                    {startError}
                  </div>
                )}
              </>
            )}

            {jobId && (
              <div style={{ marginTop: 20, paddingTop: 16, borderTop: "1px solid var(--color-border)" }}>
                <div className="job-monitor-head">
                  <span className="small muted">
                    Job ID: <code>{jobId.slice(0, 8)}...</code>
                  </span>
                  <StatusBadge status={job.data?.status ?? "queued"} />
                </div>

                {job.data?.error && (
                  <div className="notice notice-bad" role="alert">
                    {job.data.error}
                  </div>
                )}

                <div className="job-metrics-grid">
                  <Stat label="Tìm thấy" value={result?.listed ?? 0} />
                  <Stat label="Đã nhập" value={result?.imported ?? 0} tone="ok" />
                </div>

                <div style={{ marginTop: 12 }}>
                  <span className="field-label" style={{ display: "block", marginBottom: 6 }}>
                    Thống kê bỏ qua:
                  </span>
                  <table className="table">
                    <tbody>
                      <tr>
                        <td className="small">Bản quyền (License)</td>
                        <td className="num">{result?.skipped_license ?? 0}</td>
                      </tr>
                      <tr>
                        <td className="small">Trùng lặp (Duplicate)</td>
                        <td className="num">{result?.skipped_duplicate ?? 0}</td>
                      </tr>
                      <tr>
                        <td className="small">Sai định dạng (Format)</td>
                        <td className="num">{result?.skipped_format ?? 0}</td>
                      </tr>
                      <tr>
                        <td className="small">Lỗi nội dung (Invalid)</td>
                        <td className="num">{result?.skipped_invalid_content ?? 0}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                {result?.listed !== undefined &&
                  result.listed > 0 &&
                  result.skipped_license !== undefined &&
                  result.skipped_license / result.listed > 0.5 && (
                    <div className="notice notice-warn">
                      ⚠️ <strong>Cảnh báo bản quyền:</strong> Hơn 50% số bài bị bỏ qua do thiếu license cho phép mining. Xem chi tiết tại <code>policies/licenses.yaml</code>.
                    </div>
                  )}

                {result?.continuation_job_id && (
                  <button
                    type="button"
                    className="btn btn-ghost"
                    style={{ width: "100%", marginTop: 14 }}
                    onClick={() => setJobId(result.continuation_job_id!)}
                  >
                    Theo dõi job tiếp theo <span className="arrow">→</span>
                  </button>
                )}
              </div>
            )}
          </Card>
        </aside>
      </div>
    </div>
  );
}
