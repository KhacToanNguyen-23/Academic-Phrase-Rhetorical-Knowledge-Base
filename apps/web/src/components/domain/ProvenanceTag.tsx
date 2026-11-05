import { Badge } from "@/components/ui/badge"

type Provenance = "authored" | "adapted" | "corpus-inferred"

const labels: Record<Provenance, string> = {
  authored: "Authored",
  adapted: "Adapted with permission",
  "corpus-inferred": "Corpus-inferred",
}

function ProvenanceTag({ value }: { value: Provenance }) {
  return <Badge variant="secondary">{labels[value]}</Badge>
}

function LicenceStatus({ status }: { status: "cleared" | "unknown" | "restricted" }) {
  if (status === "unknown") {
    return <Badge variant="warning">Locked: licence unknown</Badge>
  }

  return (
    <Badge variant={status === "cleared" ? "success" : "destructive"}>
      {status === "cleared" ? "Licence cleared" : "Licence restricted"}
    </Badge>
  )
}

export { LicenceStatus, ProvenanceTag }
export type { Provenance }
