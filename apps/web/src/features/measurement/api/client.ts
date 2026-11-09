import { useQuery } from "@tanstack/react-query";

import { createBackendClient } from "@/shared/api/contract-client";
import type { components } from "@/shared/api/schema";
import { ApiError, unwrap } from "@/features/slr-import/api/client";

export type MeasurementKind = components["schemas"]["MeasurementSummary"]["kind"];
export type MeasurementList = components["schemas"]["MeasurementListResponse"];
export type MeasurementDetail = components["schemas"]["MeasurementDetail"];
export type SlotSuggestions = components["schemas"]["SlotSuggestionsResponse"];

export const KIND_LABELS: Record<MeasurementKind, string> = {
  metric: "Metric",
  method: "Measurement method",
  protocol: "Protocol",
};

function measurementClient() {
  const client = createBackendClient(import.meta.env.VITE_API_BASE_URL ?? "");
  client.use({
    onRequest({ request }) {
      const key =
        sessionStorage.getItem("aprkb-staff-session") ?? sessionStorage.getItem("aprkb-api-key");
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
