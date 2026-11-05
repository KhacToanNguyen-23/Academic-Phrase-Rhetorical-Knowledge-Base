import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader, SelectField } from "@/components/domain";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { jobsApi, type Job, type JobStatus } from "@/shared/api/jobs";

type Props = { apiKey: string; actorId: string; role: string; initialJob?: string };
const STAGES: Record<string, string> = {
  starting: "Starting", checking_input: "Checking input", listing_articles: "Listing articles",
  checking_duplicates: "Checking duplicates and rights", fetching_content: "Downloading content",
  saving_import_page: "Saving import page", checking_rights: "Checking mining rights",
  reading_content: "Reading content", parsing_document: "Parsing document",
  saving_sentences: "Saving sections and sentences", loading_sentences: "Loading sentences",
  extracting_phrases: "Extracting phrases", saving_candidates: "Saving candidates",
  labeling_gold: "Labeling gold batch", waiting_for_retry: "Waiting for manual retry", completed: "Completed",
};
const stageName = (value: string | null | undefined) => value ? STAGES[value] ?? value : "Not recorded";
const time = (value: string | null | undefined) => value ? new Date(value).toLocaleString() : "—";
function Pager({ offset, count, onChange }: { offset: number; count: number; onChange: (offset: number) => void }) {
  return <div className="flex items-center gap-3"><Button variant="outline" disabled={!offset} onClick={() => onChange(Math.max(0, offset - 50))}>Previous</Button><span>Page {offset / 50 + 1}</span><Button variant="outline" disabled={count < 50} onClick={() => onChange(offset + 50)}>Next</Button></div>;
}
export function JobsPage(props: Props) {
  if (!["curator", "admin"].includes(props.role)) return <p role="alert">Curator or admin access is required to operate jobs.</p>;
  return <OperatorJobs {...props} />;
}
function OperatorJobs({ apiKey, actorId, initialJob }: Props) {
  const prefix = ["jobs", actorId];
  const cache = useQueryClient();
  const [status, setStatus] = useState<JobStatus | "">("");
  const [jobType, setJobType] = useState("");
  const [offset, setOffset] = useState(0);
  const [alertOffset, setAlertOffset] = useState(0);
  const [selected, setSelected] = useState(initialJob ?? "");
  const jobs = useQuery({ queryKey: [...prefix, "list", status, jobType, offset], queryFn: () => jobsApi.list(apiKey, status || undefined, jobType || undefined, offset), retry: false, refetchInterval: 5000 });
  const alerts = useQuery({ queryKey: [...prefix, "alerts", alertOffset], queryFn: () => jobsApi.alerts(apiKey, alertOffset), retry: false, refetchInterval: 5000 });
  const ack = useMutation({ mutationFn: ({ id, at }: { id: string; at: string }) => jobsApi.acknowledge(apiKey, id, at), retry: false, onSettled: () => cache.invalidateQueries({ queryKey: prefix }) });
  return <div className="space-y-6">
    <PageHeader title="Jobs" description="Track background processing, investigate failures and retry after correcting the cause. Refreshes every 5 seconds." />
    <Card><CardHeader><CardTitle>Repeated failure alerts</CardTitle></CardHeader><CardContent className="space-y-4">
      <p className="text-sm text-muted-foreground">Acknowledging records that someone has seen the alert. It resolves only after the job succeeds; another failure reopens acknowledgement.</p>
      {alerts.isPending && <p role="status">Loading alerts…</p>}
      {alerts.error && <p role="alert">{alerts.error.message}</p>}
      {alerts.data?.length === 0 && <p>No active alerts on this page.</p>}
      {alerts.data?.map((alert) => <div key={alert.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-500/40 bg-amber-500/5 p-4">
        <div className="space-y-1"><p className="font-medium">{alert.failure_count} failed or interrupted attempts <Badge variant="outline">{alert.acknowledged_at ? "Acknowledged" : "Needs attention"}</Badge></p><p className="text-sm">{alert.last_error_code ?? "Unknown error"} · {time(alert.last_failed_at)}</p><p className="font-mono text-xs text-muted-foreground">{alert.job_id}</p></div>
        <div className="flex gap-2"><Button variant="outline" onClick={() => setSelected(alert.job_id)}>Inspect job</Button><Button variant="outline" disabled={!!alert.acknowledged_at || ack.isPending || !!alerts.error} onClick={() => ack.mutate({ id: alert.id, at: alert.last_failed_at })}>Acknowledge</Button></div>
      </div>)}
      {ack.error && <p role="alert">{ack.error.message}</p>}
      <Pager offset={alertOffset} count={alerts.data?.length ?? 0} onChange={setAlertOffset} />
    </CardContent></Card>
    <Card><CardHeader><CardTitle>Processing jobs</CardTitle></CardHeader><CardContent className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <SelectField id="jobs-status" anyLabel="All statuses" label="Job status" value={status} options={["queued", "processing", "succeeded", "failed"].map((value) => ({ value, label: value }))} onChange={(value) => { setStatus(value as JobStatus | ""); setOffset(0); }} />
        <SelectField id="jobs-type" anyLabel="All types" label="Job type" value={jobType} options={["import_articles", "ingest_article", "mine_article", "label_gold"].map((value) => ({ value, label: value.replaceAll("_", " ") }))} onChange={(value) => { setJobType(value); setOffset(0); }} />
        <Button variant="outline" onClick={() => void cache.invalidateQueries({ queryKey: prefix })}>Refresh</Button>
      </div>
      {jobs.isPending && <p role="status">Loading jobs…</p>}{jobs.error && <p role="alert">{jobs.error.message}</p>}
      <Table><TableHeader><TableRow><TableHead>Job</TableHead><TableHead>Status</TableHead><TableHead>Current step</TableHead><TableHead>Attempts</TableHead><TableHead>Next retry</TableHead><TableHead>Action</TableHead></TableRow></TableHeader><TableBody>
        {jobs.data?.map((job) => <TableRow key={job.id}><TableCell><p>{job.type.replaceAll("_", " ")}</p><p className="font-mono text-xs text-muted-foreground">{job.id}</p></TableCell><TableCell><Badge variant="outline">{job.status}</Badge></TableCell><TableCell>{stageName(job.progress_stage)}</TableCell><TableCell>{job.attempts}/{job.max_attempts}</TableCell><TableCell>{time(job.next_attempt_at)}</TableCell><TableCell><Button variant="outline" onClick={() => setSelected(job.id)}>View job</Button></TableCell></TableRow>)}
      </TableBody></Table>
      {jobs.data?.length === 0 && <p>No matching jobs on this page.</p>}
      <Pager offset={offset} count={jobs.data?.length ?? 0} onChange={setOffset} />
    </CardContent></Card>
    {selected && <JobDetail key={selected} apiKey={apiKey} actorId={actorId} id={selected} />}
  </div>;
}
function JobDetail({ apiKey, actorId, id }: { apiKey: string; actorId: string; id: string }) {
  const cache = useQueryClient();
  const [reason, setReason] = useState("");
  const [offset, setOffset] = useState(0);
  const [message, setMessage] = useState("");
  const prefix = ["jobs", actorId];
  const job = useQuery({ queryKey: [...prefix, "detail", id], queryFn: () => jobsApi.job(apiKey, id), retry: false, refetchInterval: 3000 });
  const history = useQuery({ queryKey: [...prefix, "history", id, offset], queryFn: () => jobsApi.history(apiKey, id, offset), retry: false, refetchInterval: 3000 });
  const retry = useMutation({ mutationFn: (current: Job) => jobsApi.retry(apiKey, current, reason.trim()), retry: false, onSuccess: () => { setMessage("One additional attempt queued. Existing history is preserved."); setReason(""); }, onSettled: () => cache.invalidateQueries({ queryKey: prefix }) });
  const current = job.data;
  const allowed = current && current.status === "failed" && ["import_articles", "ingest_article", "mine_article"].includes(current.type) && current.manual_retries < current.manual_retry_limit;
  return <Card><CardHeader><CardTitle>Job details</CardTitle></CardHeader><CardContent className="space-y-5">
    <p className="break-all font-mono text-xs">{id}</p>
    {job.isPending && <p role="status">Loading job…</p>}{job.error && <p role="alert">{job.error.message}</p>}
    {current && <>
      <div aria-label="Current job progress" className="space-y-2 rounded-lg border p-4"><p><Badge variant="outline">{current.status}</Badge> · {stageName(current.progress_stage)}</p>
        {current.progress_completed != null && current.progress_total != null && <p>{current.progress_completed}/{current.progress_total} items in this step</p>}
        <p className="text-sm text-muted-foreground">Counts describe this step of this job. Import pages and child jobs finish separately.</p>
        <p className="text-sm">Attempts: {current.attempts}/{current.max_attempts} · Last heartbeat: {time(current.locked_at)} · Next retry: {time(current.next_attempt_at)}</p>
        {current.error && <p className="text-sm text-destructive">Last failure: {current.error_code} — {current.error}</p>}
      </div>
      <div className="space-y-3"><p className="text-sm">Manual retries: {current.manual_retries}/{current.manual_retry_limit}. Each manual retry grants one attempt and rechecks source rights. Correct the cause first.</p>
        <Label htmlFor="job-retry-reason">Reason for manual retry</Label><Textarea id="job-retry-reason" value={reason} maxLength={1000} onChange={(event) => setReason(event.target.value)} placeholder="Describe the corrected cause; do not include source text or credentials." />
        <Button disabled={!allowed || reason.trim().length < 10 || retry.isPending || !!job.error || job.isFetching} onClick={() => retry.mutate(current)}>Retry once</Button>
        {!allowed && <p className="text-sm text-muted-foreground">Retry is available only for failed import, ingestion or mining jobs within the manual retry limit.</p>}
        {retry.error && <p role="alert">{retry.error.message}</p>}{message && <p role="status">{message}</p>}
      </div>
    </>}
    <div className="space-y-3"><h3 className="font-medium">Attempt history</h3><p className="text-sm text-muted-foreground">Older jobs may have no recorded history. Interrupted attempts are closed when the queue recovers them.</p>
      {history.error && <p role="alert">{history.error.message}</p>}
      <Table><TableHeader><TableRow><TableHead>Attempt</TableHead><TableHead>Started / ended</TableHead><TableHead>Outcome</TableHead><TableHead>Last step</TableHead><TableHead>Failure</TableHead></TableRow></TableHeader><TableBody>
        {history.data?.map((attempt) => <TableRow key={attempt.id}><TableCell>{attempt.attempt_no}</TableCell><TableCell>{time(attempt.started_at)}<br />{time(attempt.ended_at)}</TableCell><TableCell>{attempt.outcome}</TableCell><TableCell>{stageName(attempt.stage)}{attempt.total != null && <span> ({attempt.completed}/{attempt.total})</span>}</TableCell><TableCell>{attempt.error_code ?? "—"}{attempt.error && <p className="text-xs">{attempt.error}</p>}</TableCell></TableRow>)}
      </TableBody></Table>{history.data?.length === 0 && <p>No attempt history recorded.</p>}
      <Pager offset={offset} count={history.data?.length ?? 0} onChange={setOffset} />
    </div>
  </CardContent></Card>;
}
