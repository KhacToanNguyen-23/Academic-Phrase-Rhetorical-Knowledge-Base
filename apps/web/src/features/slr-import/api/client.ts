import { createBackendClient } from "@/shared/api/contract-client";

export function slrImportClient() {
  const client = createBackendClient(import.meta.env.VITE_API_BASE_URL ?? "");
  client.use({
    onRequest({ request }) {
      const key = sessionStorage.getItem("aprkb-api-key");
      if (key) request.headers.set("X-API-Key", key);
      return request;
    },
  });
  return client;
}

type ErrorBody = { error?: { message?: string; details?: { errors?: { loc: (string | number)[]; msg: string }[] } } };

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly body: ErrorBody | undefined,
  ) {
    super(
      body?.error?.message ??
        (status >= 500 && !body
          ? `Backend không phản hồi (HTTP ${status}). Kiểm tra API đã chạy ở cổng 8000 chưa.`
          : `Yêu cầu thất bại (HTTP ${status}).`),
    );
  }
}

/** Check the HTTP status, not `error`: openapi-fetch sets `error` to "" when the error body is empty. */
export function unwrap<T>(res: { data?: T; error?: unknown; response: Response }): T {
  if (!res.response.ok) {
    const body = res.error && typeof res.error === "object" ? (res.error as ErrorBody) : undefined;
    throw new ApiError(res.response.status, body);
  }
  return res.data as T;
}
