import { Badge, type badgeVariants } from "@/components/ui/badge"
import type { VariantProps } from "class-variance-authority"

type BadgeVariant = VariantProps<typeof badgeVariants>["variant"]

const statusVariants: Record<string, BadgeVariant> = {
  approved: "success",
  active: "success",
  succeeded: "success",
  done: "success",
  pending: "warning",
  in_review: "warning",
  revision: "warning",
  queued: "warning",
  running: "secondary",
  draft: "secondary",
  rejected: "destructive",
  retired: "destructive",
  suspended: "destructive",
  failed: "destructive",
}

function sentenceCase(value: string) {
  return value.replace(/[-_]/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function StatusBadge({ status }: { status: string }) {
  return <Badge variant={statusVariants[status] ?? "secondary"}>{sentenceCase(status)}</Badge>
}

export { StatusBadge }
