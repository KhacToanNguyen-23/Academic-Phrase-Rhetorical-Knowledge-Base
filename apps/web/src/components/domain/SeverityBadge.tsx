import { Badge } from "@/components/ui/badge"

type Severity = "pass" | "warn" | "block"

const labels: Record<Severity, string> = {
  pass: "Pass",
  warn: "Warn",
  block: "Block",
}

function SeverityBadge({ value }: { value: Severity }) {
  const variant = value === "pass" ? "success" : value === "warn" ? "warning" : "destructive"
  return <Badge variant={variant}>{labels[value]}</Badge>
}

export { SeverityBadge }
export type { Severity }
