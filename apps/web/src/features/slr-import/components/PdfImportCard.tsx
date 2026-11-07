import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useAuth } from "@/features/auth/AuthProvider";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { components } from "@/shared/api/schema";

type Preview = components["schemas"]["PdfPreview"];
type Result = { article_id: string; job_id: string; status: string };
type Match = { matched_article_id?: string | null; matched_title?: string | null; reason?: string | null };

async function pdfRequest<T>(path: string, apiKey: string, body?: FormData): Promise<T> {
  const response = await fetch(`${import.meta.env.VITE_API_BASE_URL ?? ""}/v1/admin/${path}`, {
    method: body ? "POST" : "GET", headers: { "X-API-Key": apiKey }, body,
  });
  const data = await response.json() as T & { error?: { message?: string; details?: Match & { message?: string; code?: string } } };
  if (!response.ok) {
    const details = data.error?.details;
    if (details?.code === "duplicate_article") {
      throw new Error(`Duplicate (${details.reason}): ${details.matched_title ?? "Existing article"} · ${details.matched_article_id}. Reuse the existing article; inspect Jobs if ingestion failed.`);
    }
    throw new Error(details?.message ?? data.error?.message ?? `PDF request failed (HTTP ${response.status}).`);
  }
  return data;
}

export function PdfImportCard() {
  const auth = useAuth();
  const apiKey = sessionStorage.getItem("aprkb-api-key") || auth.apiKey || "";
  const epoch = useRef(0);
  const [file, setFile] = useState<File>();
  const [license, setLicense] = useState("");
  const [preview, setPreview] = useState<Preview>();
  const [title, setTitle] = useState("");
  const [doi, setDoi] = useState("");
  const [authors, setAuthors] = useState("");
  const [year, setYear] = useState("");
  const [journal, setJournal] = useState("");
  const [genre, setGenre] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [reviewed, setReviewed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Result>();
  const job = useQuery({
    queryKey: ["pdf-import-job", result?.job_id, apiKey],
    enabled: !!result,
    queryFn: () => pdfRequest<{ status: string; error: string | null }>(`jobs/${result!.job_id}`, apiKey),
    refetchInterval: (query) => ["succeeded", "failed"].includes(query.state.data?.status ?? "") ? false : 2000,
  });

  function resetPreview() {
    epoch.current += 1; setPreview(undefined); setReviewed(false); setError(""); setResult(undefined);
  }

  async function inspect() {
    if (!file || !license) return;
    const requestEpoch = ++epoch.current;
    setBusy(true); setError(""); setResult(undefined); setPreview(undefined); setReviewed(false);
    const form = new FormData(); form.set("file", file); form.set("license_code", license);
    try {
      const data = await pdfRequest<Preview>("corpus/pdf/preview", apiKey, form);
      if (requestEpoch !== epoch.current) return;
      setPreview(data); setTitle(data.suggested_title ?? ""); setAuthors(data.suggested_authors.join("; "));
      setDoi(""); setYear(""); setJournal(""); setGenre(""); setSourceUrl("");
    } catch (reason) {
      if (requestEpoch === epoch.current) setError(reason instanceof Error ? reason.message : "PDF preview failed.");
    } finally { if (requestEpoch === epoch.current) setBusy(false); }
  }

  async function importPdf(event: React.FormEvent) {
    event.preventDefault();
    if (!file || !preview || !reviewed || preview.duplicate || busy) return;
    const requestEpoch = ++epoch.current;
    setBusy(true); setError("");
    const form = new FormData(); form.set("file", file); form.set("license_code", license);
    form.set("metadata_reviewed", "true");
    form.set("metadata_json", JSON.stringify({
      title, doi: doi.trim() || null, authors: authors.split(";").map((item) => item.trim()).filter(Boolean),
      publication_year: year ? Number(year) : null, journal_id: journal || null,
      genre_id: genre || null, source_url: sourceUrl || null,
    }));
    try {
      const data = await pdfRequest<Result>("corpus/articles", apiKey, form);
      if (requestEpoch === epoch.current) setResult(data);
    } catch (reason) {
      if (requestEpoch === epoch.current) setError(reason instanceof Error ? reason.message : "PDF import failed.");
    } finally { if (requestEpoch === epoch.current) setBusy(false); }
  }

  function edit(setter: (value: string) => void, value: string) { setter(value); setReviewed(false); }
  const selectClass = "h-10 w-full rounded-md border bg-background px-3 text-sm";
  return <Card className="w-full max-w-[1152px] self-center">
    <CardHeader><CardTitle>Import a PDF</CardTitle><CardDescription>Preview a text PDF, verify its metadata, then import. The file stays on this server. Scanned or encrypted PDFs need OCR or an unlocked copy first.</CardDescription></CardHeader>
    <CardContent className="space-y-5">
      <fieldset disabled={busy} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2"><Label htmlFor="pdf-file">PDF file</Label><Input id="pdf-file" type="file" accept=".pdf,application/pdf" onChange={(event) => { resetPreview(); setFile(event.target.files?.[0]); }} /></div>
          <div className="space-y-2"><Label htmlFor="pdf-license">PDF license</Label><select id="pdf-license" className={selectClass} value={license} onChange={(event) => { resetPreview(); setLicense(event.target.value); }}><option value="">Select the verified license</option><option value="CC0">CC0</option><option value="CC-BY">CC-BY</option><option value="CC-BY-SA">CC-BY-SA</option></select></div>
        </div>
        <Button type="button" onClick={() => void inspect()} disabled={!file || !license || busy}>{busy ? "Processing PDF…" : "Preview PDF and check duplicates"}</Button>
      </fieldset>
      {error && <p role="alert" className="break-words text-sm text-destructive">{error}</p>}
      {preview && <div className="space-y-4">
        <p className="text-sm">{preview.page_count} pages. File bytes and extracted full text were checked for duplicates. DOI is checked again when you import.</p>
        {preview.warnings.map((warning) => <p className="text-sm text-muted-foreground" key={warning}>{warning}</p>)}
        {preview.duplicate && <p role="alert" className="break-words">Duplicate ({preview.duplicate.reason}): {preview.duplicate.matched_title ?? "Existing article"} · {preview.duplicate.matched_article_id}. Reuse this article; check <Link to="/jobs" className="underline">Jobs</Link> if ingestion failed.</p>}
        {preview.suspected_duplicates.length > 0 && <div className="text-sm"><p>Similar titles to review — these are hints, not confirmed duplicates:</p><ul className="list-disc pl-5">{preview.suspected_duplicates.map((item) => <li key={item.matched_article_id} className="break-words">{item.matched_title} · {item.matched_article_id}</li>)}</ul></div>}
        {!preview.duplicate && <form onSubmit={(event) => void importPdf(event)}>
          <fieldset disabled={busy || !!result} className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2 sm:col-span-2"><Label htmlFor="pdf-title">PDF title</Label><Input id="pdf-title" value={title} required maxLength={1000} onChange={(event) => edit(setTitle, event.target.value)} /></div>
            <div className="space-y-2"><Label htmlFor="pdf-doi">Paper DOI (optional)</Label><Input id="pdf-doi" value={doi} list="pdf-doi-candidates" maxLength={255} onChange={(event) => edit(setDoi, event.target.value)} /><datalist id="pdf-doi-candidates">{preview.doi_candidates.map((value) => <option key={value} value={value} />)}</datalist><p className="text-xs text-muted-foreground">First-page candidates: {preview.doi_candidates.join("; ") || "none"}. Verify the paper DOI, not a cited work.</p></div>
            <div className="space-y-2"><Label htmlFor="pdf-authors">Authors (separate with semicolons)</Label><Input id="pdf-authors" value={authors} onChange={(event) => edit(setAuthors, event.target.value)} /></div>
            <div className="space-y-2"><Label htmlFor="pdf-year">Publication year (optional)</Label><Input id="pdf-year" type="number" min={1000} max={3000} value={year} onChange={(event) => edit(setYear, event.target.value)} /></div>
            <div className="space-y-2"><Label htmlFor="pdf-source">Source URL (optional)</Label><Input id="pdf-source" type="url" maxLength={2048} value={sourceUrl} onChange={(event) => edit(setSourceUrl, event.target.value)} /></div>
            <div className="space-y-2"><Label htmlFor="pdf-journal">Journal (optional)</Label><select id="pdf-journal" className={selectClass} value={journal} onChange={(event) => edit(setJournal, event.target.value)}><option value="">Not specified</option>{preview.journals.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div>
            <div className="space-y-2"><Label htmlFor="pdf-genre">Article genre (optional)</Label><select id="pdf-genre" className={selectClass} value={genre} onChange={(event) => edit(setGenre, event.target.value)}><option value="">Not specified</option>{preview.genres.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div>
            <label className="flex items-start gap-3 text-sm sm:col-span-2"><input type="checkbox" checked={reviewed} onChange={(event) => setReviewed(event.target.checked)} className="mt-1" />I reviewed these metadata and confirm the selected license permits processing.</label>
            <Button type="submit" disabled={!reviewed || !title.trim() || busy} className="sm:col-span-2">Import reviewed PDF</Button>
          </fieldset>
        </form>}
      </div>}
      {result && <div role="status" className="space-y-2 text-sm"><p>PDF import: {job.data?.status ?? result.status}. {job.data?.status === "succeeded" ? "Ready for extraction." : ""}</p>{job.data?.error && <p role="alert">{job.data.error}</p>}{job.error && <p role="alert">{job.error.message}</p>}<div className="flex gap-4"><Link to="/jobs" search={{ job: result.job_id }} className="underline">Inspect PDF job</Link><Link to="/extract" className="underline">Open extraction</Link></div></div>}
    </CardContent>
  </Card>;
}
