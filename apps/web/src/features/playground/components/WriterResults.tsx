import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { Recommendation } from "../live/api";
import { Notice } from "./WriterStatus";

const fallbackLabels: Record<string, string> = {
  journal_genre: "Journal and genre",
  similar_journal_genre: "Similar journal",
  subfield_genre: "Subfield",
  field_genre: "Field",
  generic_genre: "General",
};

const scoreLabels: Record<string, string> = {
  discipline: "Discipline",
  journal_genre: "Journal / genre",
  evidence: "Evidence alignment",
  linguistic: "Keyword match",
  provenance: "Provenance",
};

export function WriterResults({
  recommendation,
  picked,
  searchedWith,
  onSelect,
}: {
  recommendation: Recommendation;
  picked: string;
  searchedWith: string[];
  onSelect: (versionId: string) => void;
}) {
  const scoreKeys = recommendation.items[0] ? Object.keys(recommendation.items[0].breakdown) : [];
  const hidden = recommendation.excluded.GATE_EVIDENCE ?? 0;

  // CR-01 / FR-07.3/.4: show eligible samples immediately in a filterable table.
  return (
    <Card>
      <CardHeader>
        <CardTitle>Recommended patterns</CardTitle>
        <CardDescription>
          Select an evidence level to hide patterns that exceed it. No evidence check is applied until one is selected.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <p className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          {searchedWith.length ? "Searched with" : "No filters: every eligible pattern is listed."}
          {searchedWith.map((item) => (
            <Badge key={item} variant="secondary">
              {item}
            </Badge>
          ))}
        </p>
        {recommendation.fallback_reason && <Notice>{recommendation.fallback_reason}</Notice>}
        {(recommendation.warnings ?? []).map((warning) => (
          <Notice key={warning}>{warning}</Notice>
        ))}
        {hidden > 0 && <Notice>{hidden} samples hidden because they exceed the selected evidence level.</Notice>}
        {recommendation.items.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No patterns meet these criteria. Try changing the context or the evidence level.
          </p>
        )}
        {recommendation.items.length > 0 && (
          <RadioGroup value={picked} onValueChange={onSelect} aria-label="Recommended patterns">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10">
                    <span className="sr-only">Select</span>
                  </TableHead>
                  <TableHead>Sentence frame</TableHead>
                  <TableHead className="text-right">Score</TableHead>
                  <TableHead>Fallback</TableHead>
                  {scoreKeys.map((key) => (
                    <TableHead key={key} className="text-right">
                      {scoreLabels[key] ?? key.replaceAll("_", " ")}
                    </TableHead>
                  ))}
                  <TableHead>Source and licence</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {recommendation.items.map((item) => (
                  <TableRow
                    key={item.pattern_version_id}
                    data-state={picked === item.pattern_version_id ? "selected" : undefined}
                  >
                    <TableCell>
                      <RadioGroupItem
                        id={`candidate-${item.pattern_version_id}`}
                        value={item.pattern_version_id}
                        aria-label={`Select ${item.canonical_frame}`}
                      />
                    </TableCell>
                    <TableCell className="max-w-md whitespace-normal">
                      <label htmlFor={`candidate-${item.pattern_version_id}`} className="cursor-pointer font-medium">
                        {item.canonical_frame}
                      </label>
                      {item.explanations.map((explanation) => (
                        <span key={explanation} className="mt-1 block text-sm text-muted-foreground">
                          {explanation}
                        </span>
                      ))}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{item.score.toFixed(2)}</TableCell>
                    <TableCell>{fallbackLabels[item.fallback_tier] ?? "General"}</TableCell>
                    {scoreKeys.map((key) => {
                      const value = item.breakdown[key];
                      return (
                        <TableCell key={key} className="text-right tabular-nums">
                          {value === null ? "—" : value.toFixed(2)}
                        </TableCell>
                      );
                    })}
                    <TableCell className="whitespace-normal">
                      <span>
                        {item.source_type === "authored" ? "Self-authored" : "Corpus"} · v{item.version_no}
                      </span>
                      {(item.license_name || item.license_code) && (
                        <span className="block text-sm text-muted-foreground">
                          {item.license_name ?? item.license_code}
                          {item.license_name && item.license_code ? ` (${item.license_code})` : ""}
                          {item.license_flag ? " · Copyrighted source, internal use only" : ""}
                        </span>
                      )}
                      {item.source_reference && (
                        <span className="block text-sm text-muted-foreground">{item.source_reference}</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </RadioGroup>
        )}
      </CardContent>
    </Card>
  );
}
