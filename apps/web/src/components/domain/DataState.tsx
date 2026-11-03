import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"

type DataStateProps = {
  state: "ready" | "loading" | "empty" | "error"
  value?: number | null
  onRetry?: () => void
}

function DataState({ state, value, onRetry }: DataStateProps) {
  if (state === "loading") {
    return (
      <div className="flex flex-col gap-3" aria-busy="true" aria-label="Loading evidence">
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
          <EmptyTitle>No reviewed frames yet</EmptyTitle>
          <EmptyDescription>Review a candidate to build the evidence set for this view.</EmptyDescription>
        </EmptyHeader>
        <EmptyContent>
          <Button variant="secondary">Review a candidate</Button>
        </EmptyContent>
      </Empty>
    )
  }

  if (state === "error") {
    return (
      <Alert variant="destructive" role="alert">
        <AlertTitle>Evidence could not be loaded</AlertTitle>
        <AlertDescription className="flex flex-wrap items-center gap-3">
          Check the connection and try the request again.
          {onRetry ? <Button variant="secondary" onClick={onRetry}>Try again</Button> : null}
        </AlertDescription>
      </Alert>
    )
  }

  return (
    <p className="text-sm text-muted-foreground">
      Reviewed frames: <strong className="font-medium text-foreground">{value ?? "—"}</strong>
    </p>
  )
}

export { DataState }
