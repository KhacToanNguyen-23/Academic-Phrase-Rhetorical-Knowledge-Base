import { Badge } from "@/components/ui/badge"

type EvidenceKind = "required" | "observed" | "suggested"

const labels: Record<EvidenceKind, string> = {
  required: "Required by journal",
  observed: "Observed in corpus",
  suggested: "Model suggestion",
}

function EvidenceLabel({ kind }: { kind: EvidenceKind }) {
  return <Badge variant="secondary" title="Evidence class">{labels[kind]}</Badge>
}

export { EvidenceLabel }
export type { EvidenceKind }
