import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { createBackendClient } from "@/shared/api/contract-client";
import type { components } from "@/shared/api/schema";
import { ApiError, unwrap } from "@/features/slr-import/api/client";

export type MeasurementKind = components["schemas"]["MeasurementSummary"]["kind"];
export type MeasurementList = components["schemas"]["MeasurementListResponse"];
export type MeasurementDetail = components["schemas"]["MeasurementDetail"];
export type SlotSuggestions = components["schemas"]["SlotSuggestionsResponse"];
export type PatternMeasurements = components["schemas"]["PatternMeasurementsResponse"];
export type SlotLink = components["schemas"]["SlotLinkRead"];

export const KIND_LABELS: Record<MeasurementKind, string> = {
  metric: "Metric",
  method: "Measurement method",
  protocol: "Protocol",
};

function measurementClient() {
  const client = createBackendClient(import.meta.env.VITE_API_BASE_URL ?? "");
  client.use({
    onRequest({ request }) {
      // Same session key the AuthProvider stores after sign-in.
      const key = sessionStorage.getItem("aprkb-web-session");
      if (key) request.headers.set("X-API-Key", key);
      return request;
    },
  });
  return client;
}

export function useMeasurements(params: { kind?: MeasurementKind; q?: string }) {
  return useQuery({
    queryKey: ["measurements", params],
    retry: false,
    queryFn: async (): Promise<MeasurementList> =>
      unwrap(
        await measurementClient().GET("/v1/measurements", {
          params: { query: { kind: params.kind, q: params.q || undefined, limit: 200 } },
        }),
      ) as MeasurementList,
  });
}

export function useMeasurement(code: string) {
  return useQuery({
    queryKey: ["measurement", code],
    enabled: Boolean(code),
    retry: false,
    queryFn: async (): Promise<MeasurementDetail> =>
      unwrap(
        await measurementClient().GET("/v1/measurements/{code}", { params: { path: { code } } }),
      ) as MeasurementDetail,
  });
}

/** Approved catalog suggestions for one pattern slot; null when the catalog is switched off. */
export function useSlotSuggestions(patternId: string, slot: string) {
  return useQuery({
    queryKey: ["measurement-slot-suggestions", patternId, slot],
    retry: false,
    queryFn: async (): Promise<SlotSuggestions | null> => {
      try {
        return unwrap(
          await measurementClient().GET("/v1/measurements/slot-suggestions", {
            params: { query: { pattern_id: patternId, slot } },
          }),
        ) as SlotSuggestions;
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) return null;
        throw error;
      }
    },
  });
}

/** Approved measures linked to a pattern; null when the catalog is switched off. */
export function usePatternMeasurements(patternId: string) {
  return useQuery({
    queryKey: ["measurement-pattern", patternId],
    retry: false,
    queryFn: async (): Promise<PatternMeasurements | null> => {
      try {
        return unwrap(
          await measurementClient().GET("/v1/measurements/pattern-measurements", {
            params: { query: { pattern_id: patternId } },
          }),
        ) as PatternMeasurements;
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) return null;
        throw error;
      }
    },
  });
}

/** Proposed links awaiting curator review (curator role only). */
export function useProposedLinks(enabled: boolean) {
  return useQuery({
    queryKey: ["measurement-links", "proposed"],
    enabled,
    retry: false,
    queryFn: async (): Promise<SlotLink[]> =>
      (
        unwrap(
          await measurementClient().GET("/v1/admin/measurements/slot-links", {
            params: { query: { status: "proposed" } },
          }),
        ) as { items: SlotLink[] }
      ).items,
  });
}

export function useReviewLink() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, decision }: { id: string; decision: "approved" | "rejected" }) =>
      unwrap(
        await measurementClient().POST("/v1/admin/measurements/slot-links/{link_id}/review", {
          params: { path: { link_id: id } },
          body: { decision },
        }),
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["measurement-links"] });
      void queryClient.invalidateQueries({ queryKey: ["measurement"] });
      void queryClient.invalidateQueries({ queryKey: ["measurement-pattern"] });
      void queryClient.invalidateQueries({ queryKey: ["measurement-slot-suggestions"] });
    },
  });
}
