import type { ReactNode } from "react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"

type DataStateProps = {
  state: "ready" | "loading" | "empty" | "error"
  /** Label for the ready value, e.g. "Reviewed frames". */
  label?: string
  /** Ready value. 0 prints "0"; null/undefined prints "—". */
  value?: number | null
  loadingLabel?: string
  emptyTitle?: string
  emptyDescription?: string
  emptyAction?: ReactNode
  errorTitle?: string
  errorDescription?: string
  retryLabel?: string
  onRetry?: () => void
}

function DataState({
  state,
  label,
  value,
  loadingLabel = "Loading",
  emptyTitle = "Nothing here yet",
  emptyDescription,
  emptyAction,
  errorTitle = "Could not load this",
  errorDescription,
  retryLabel = "Try again",
  onRetry,
}: DataStateProps) {
  if (state === "loading") {
    return (
      <div className="flex flex-col gap-3" aria-busy="true" aria-label={loadingLabel}>
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-4 w-1/2" />
      </div>
    )
  }

  if (state === "empty") {
    return (
      <Empty>
        <EmptyHeader>
          <EmptyTitle>{emptyTitle}</EmptyTitle>
          {emptyDescription ? <EmptyDescription>{emptyDescription}</EmptyDescription> : null}
        </EmptyHeader>
        {emptyAction ? <EmptyContent>{emptyAction}</EmptyContent> : null}
      </Empty>
    )
  }

  if (state === "error") {
    return (
      <Alert variant="destructive" role="alert">
        <AlertTitle>{errorTitle}</AlertTitle>
        <AlertDescription className="flex flex-wrap items-center gap-3">
          {errorDescription}
          {onRetry ? <Button variant="secondary" onClick={onRetry}>{retryLabel}</Button> : null}
        </AlertDescription>
      </Alert>
    )
  }

  return (
    <p className="text-sm text-muted-foreground">
      {label ? `${label}: ` : null}
      <strong className="font-medium tabular-nums text-foreground">{value ?? "—"}</strong>
    </p>
  )
}

export { DataState }
