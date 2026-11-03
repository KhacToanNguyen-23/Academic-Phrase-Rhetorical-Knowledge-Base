import { useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { StatusBadge } from "@/components/domain/StatusBadge";
import { cn } from "@/lib/utils";
import { HighlightedSentence, MaskedFrame } from "./MaskedFrame";
import type { Phrase } from "./types";

type Props = {
  phrase: Phrase;
  checked: boolean;
  busy: boolean;
  onCheck: (checked: boolean) => void;
  onDecide: (decision: "accept" | "reject") => void;
};

export function PhraseCard({ phrase, checked, busy, onCheck, onDecide }: Props) {
  const pending = phrase.status === "pending";
  const [expanded, setExpanded] = useState(false);
  const totalSources = phrase.sources.length;
  const visibleSources = expanded ? phrase.sources : phrase.sources.slice(0, 2);
  const hiddenCount = Math.max(0, totalSources - 2);
  const checkboxId = `phrase-${phrase.id}`;

  return (
    <Card
      className={cn("min-w-0", checked && "border-foreground", phrase.blocked && "border-destructive/50")}
      data-status={phrase.status}
    >
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-3">
          {pending ? (
            <div className="pt-1">
              <Checkbox
                id={checkboxId}
                checked={checked}
                onCheckedChange={(value) => onCheck(value === true)}
                aria-label={`Select phrase ${phrase.canonical_frame}`}
              />
            </div>
          ) : null}
          <h3 className="min-w-0 text-lg font-medium">
            <MaskedFrame frame={phrase.canonical_frame} />
          </h3>
        </div>
        <div className="flex shrink-0 flex-wrap justify-end gap-2">
          {totalSources > 2 && !expanded ? <Badge variant="secondary">{totalSources} sources</Badge> : null}
          {phrase.epistemic_strength ? <Badge variant="outline">{phrase.epistemic_strength}</Badge> : null}
          {phrase.blocked ? <Badge variant="destructive">Blocked</Badge> : null}
          {!pending ? <StatusBadge status={phrase.status} /> : null}
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {totalSources === 0 ? (
          <Alert variant="destructive">
            <AlertDescription>
              The source sentence is unavailable because the source or mining permission is missing.
            </AlertDescription>
          </Alert>
        ) : (
          <div className="flex flex-col gap-3">
            {visibleSources.map((source) => (
              <div key={source.sentence_id} className="rounded-[var(--radius)] border border-border bg-muted/30 p-3">
                <p className="leading-6">
                  <HighlightedSentence text={source.text} spans={source.slot_spans} />
                </p>
                <div className="mt-3 flex min-w-0 items-center justify-between gap-3 text-xs text-muted-foreground">
                  <span className="flex min-w-0 flex-wrap gap-2">
                    {source.section ? <Badge variant="outline">{source.section}</Badge> : null}
                    {source.journal ? <Badge variant="outline">{source.journal}</Badge> : null}
                  </span>
                  <span className="truncate" title={source.article_title ?? undefined}>
                    {source.article_title ?? "Article title unavailable"}
                  </span>
                </div>
              </div>
            ))}
            {totalSources > 2 ? (
              <Button variant="ghost" size="sm" className="self-start" onClick={() => setExpanded((value) => !value)}>
                {expanded ? "Show fewer sources" : `Show ${hiddenCount} more sources`}
              </Button>
            ) : null}
          </div>
        )}
      </CardContent>
      {pending ? (
        <CardFooter className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-muted-foreground">
            {phrase.blocked
              ? "Mining permission and valid slots are required before acceptance."
              : "Review the source evidence before accepting this phrase."}
          </p>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" disabled={busy} onClick={() => onDecide("reject")}>
              Reject
            </Button>
            <Button
              variant="outline"
              disabled={busy || phrase.blocked}
              title={phrase.blocked ? "Source permission or slot validation is missing" : undefined}
              onClick={() => onDecide("accept")}
            >
              Accept
            </Button>
          </div>
        </CardFooter>
      ) : null}
    </Card>
  );
}
