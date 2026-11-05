import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { EvidenceLabel } from "@/components/domain/EvidenceLabel"
import { LicenceStatus, ProvenanceTag, type Provenance } from "@/components/domain/ProvenanceTag"

type DictionaryEntryProps = {
  headword: string
  partOfSpeech: string
  family: string
  rank?: number | null
  example: string
  provenance: Provenance
  licence: "cleared" | "unknown" | "restricted"
}

function DictionaryEntry({
  headword,
  partOfSpeech,
  family,
  rank,
  example,
  provenance,
  licence,
}: DictionaryEntryProps) {
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <CardTitle className="font-serif text-xl">{headword}</CardTitle>
          <span className="num text-sm text-muted-foreground">Rank {rank ?? "—"}</span>
        </div>
        <CardDescription>{partOfSpeech} · {family}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <p className="font-serif leading-7 text-foreground">{example}</p>
        <div className="flex flex-wrap items-center gap-2">
          <ProvenanceTag value={provenance} />
          <LicenceStatus status={licence} />
          <EvidenceLabel kind="observed" />
        </div>
      </CardContent>
    </Card>
  )
}

export { DictionaryEntry }
