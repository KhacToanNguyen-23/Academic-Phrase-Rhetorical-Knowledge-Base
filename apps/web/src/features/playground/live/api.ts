import { createBackendClient } from "@/shared/api/contract-client";
import type { components } from "@/shared/api/schema";

export type Taxonomy = components["schemas"]["TaxonomyTree"];
export type Option = components["schemas"]["ReferenceOption"];
export type Journal = components["schemas"]["JournalRead"];
export type Recommendation = components["schemas"]["RecommendationResponse"];
export type RecommendationRequest = components["schemas"]["RecommendationRequest"];
export type Version = components["schemas"]["RenderableVersionRead"];
export type SlotDefinition = components["schemas"]["SlotDefinition"];
export type Render = components["schemas"]["RenderResponse"];
export type Validation = components["schemas"]["ValidationResponse"];
export type Feedback = components["schemas"]["FeedbackCreate"];

const client = createBackendClient("");

function required<T>(data: T | undefined, status: number): T {
  if (data !== undefined) return data;
  const reason = status === 401 ? "Authentication failed" :
    status === 403 ? "This client is not authorized for the requested action" :
    status === 404 ? "The requested data is no longer available" :
    status === 422 ? "Some submitted fields are invalid" :
    status === 503 ? "Policy or reference data is unavailable" :
    "The backend did not respond. Check the API and database, then try again";
  throw new Error(`${reason} (HTTP ${status})`);
}

const headers = (key: string) => key ? { "X-API-Key": key } : {};

export class SlotValidationApiError extends Error {
  constructor(readonly fieldErrors: Record<string, string>) {
    super("Check the highlighted slot fields.");
  }
}

// FR-09.1 contracts for the Writer path: taxonomy/options → recommendation → version/render → validate → feedback.
export const liveApi = {
  taxonomy: async (key: string) => {
    const { data, response } = await client.GET("/v1/taxonomy", { headers: headers(key) });
    return required(data, response.status);
  },
  options: async (key: string) => {
    const { data, response } = await client.GET("/v1/taxonomy/reference-options", { headers: headers(key) });
    return required(data, response.status);
  },
  journals: async (key: string) => {
    const { data, response } = await client.GET("/v1/journals", { headers: headers(key) });
    return required(data, response.status);
  },
  recommend: async (key: string, body: RecommendationRequest) => {
    const { data, response } = await client.POST("/v1/recommendations", {
      headers: headers(key), body,
    });
    return required(data, response.status);
  },
  version: async (key: string, versionId: string) => {
    const { data, response } = await client.GET("/v1/patterns/versions/{version_id}", {
      headers: headers(key), params: { path: { version_id: versionId } },
    });
    return required(data, response.status);
  },
  render: async (key: string, recommendationId: string, versionId: string, slots: Record<string, string>) => {
    const { data, response } = await client.POST("/v1/render", {
      headers: headers(key),
      body: { recommendation_id: recommendationId, pattern_version_id: versionId, slots },
    });
    if (data === undefined && response.status === 422) {
      const body: unknown = await response.clone().json().catch(() => undefined);
      if (body && typeof body === "object" && "error" in body) {
        const error = body.error;
        if (error && typeof error === "object" && "details" in error) {
          const details = error.details;
          if (details && typeof details === "object" && "field_errors" in details) {
            const fields = details.field_errors;
            if (fields && typeof fields === "object") {
              throw new SlotValidationApiError(fields as Record<string, string>);
            }
          }
        }
      }
    }
    return required(data, response.status);
  },
  validate: async (key: string, text: string, claimType: string, evidenceLevel: string) => {
    const { data, response } = await client.POST("/v1/validate", {
      headers: headers(key),
      body: { text, claim_type: claimType, evidence_level: evidenceLevel },
    });
    return required(data, response.status);
  },
  feedback: async (key: string, body: Feedback) => {
    const { data, response } = await client.POST("/v1/feedback", {
      headers: headers(key), body,
    });
    return required(data, response.status);
  },
};
