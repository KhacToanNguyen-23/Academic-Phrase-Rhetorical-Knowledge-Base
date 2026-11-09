import { createBackendClient } from "./contract-client";
import type { components } from "./schema";

export type Job = components["schemas"]["JobRead"];
export type JobStatus = "queued" | "processing" | "succeeded" | "failed";
const client = createBackendClient("");
const headers = (key: string) => ({ "X-API-Key": key });
function unpack<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data !== undefined) return result.data;
  const error = result.error as { error?: { message?: string } } | undefined;
  throw new Error(error?.error?.message ?? `Request failed (${result.response.status})`);
}
export const jobsApi = {
  list: async (key: string, status: JobStatus | undefined, jobType: string | undefined, offset: number) =>
    unpack(await client.GET("/v1/admin/jobs", { headers: headers(key), params: { query: { status, job_type: jobType, offset, limit: 50 } } })),
  job: async (key: string, id: string) => unpack(await client.GET("/v1/admin/jobs/{job_id}", { headers: headers(key), params: { path: { job_id: id } } })),
  history: async (key: string, id: string, offset: number) => unpack(await client.GET("/v1/admin/jobs/{job_id}/attempts", { headers: headers(key), params: { path: { job_id: id }, query: { limit: 50, offset } } })),
  retry: async (key: string, job: Job, rationale: string) => unpack(await client.POST("/v1/admin/jobs/{job_id}/retry", { headers: headers(key), params: { path: { job_id: job.id } }, body: { expected_attempts: job.attempts, rationale } })),
  alerts: async (key: string, offset: number) => unpack(await client.GET("/v1/admin/job-alerts", { headers: headers(key), params: { query: { active_only: true, limit: 50, offset } } })),
  acknowledge: async (key: string, id: string, expectedLastFailedAt: string) => unpack(await client.POST("/v1/admin/job-alerts/{alert_id}/acknowledge", { headers: headers(key), params: { path: { alert_id: id } }, body: { expected_last_failed_at: expectedLastFailedAt } })),
};
