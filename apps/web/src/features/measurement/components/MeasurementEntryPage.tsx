import { getRouteApi, Link } from "@tanstack/react-router";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataState } from "@/components/domain/DataState";
import { PageHeader } from "@/components/domain/PageHeader";
import { useAuth } from "@/features/auth/AuthProvider";
import { KIND_LABELS, useMeasurement, useProposedLinks, useReviewLink } from "../api/client";

const route = getRouteApi("/shell/guarded/measurements/$code");

const RELATION_LABELS: Record<string, [outgoing: string, incoming: string]> = {
  uses_method: ["Measured with", "Used to compute"],
  part_of: ["Part of protocol", "Includes"],
  variant_of: ["Variant of", "Has variant"],
  related_to: ["Related to", "Related to"],
};

export function MeasurementEntryPage() {
  const { code } = route.useParams();
  const search = route.useSearch();
  const entry = useMeasurement(code);
  const back = (
    <Button asChild variant="outline">
      <Link to="/measurements" search={search}>
        Back to catalog
      </Link>
    </Button>
  );

  if (entry.isPending) return <DataState state="loading" loadingLabel="Loading entry" />;
  if (entry.isError || !entry.data)
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title="Measurement entry" actions={back} />
        <DataState
          state="error"
          errorTitle="Entry is unavailable"
          errorDescription={entry.error?.message ?? "The entry could not be found."}
          onRetry={() => void entry.refetch()}
        />
      </div>
    );

  const item = entry.data;
  const facts = [
    ["Formula", item.formula],
    ["Scale", item.scale],
    ["Value range", item.value_range],
  ].filter((fact): fact is [string, string] => Boolean(fact[1]));

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={<span className="font-serif text-3xl">{item.name}</span>}
        description={`${KIND_LABELS[item.kind]} · catalog ${item.catalog_version}`}
        actions={back}
      />

      <Card>
        <CardHeader>
          <CardTitle>Definition</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <p className="font-serif text-lg leading-7">{item.definition}</p>
          {facts.length ? (
            <dl className="grid gap-4 sm:grid-cols-3">
              {facts.map(([label, value]) => (
                <div key={label} className="flex flex-col gap-1">
                  <dt className="text-sm text-muted-foreground">{label}</dt>
                  <dd className="font-mono text-sm">{value}</dd>
                </div>
              ))}
            </dl>
          ) : null}
          {item.aliases.length ? (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm text-muted-foreground">Also called</span>
              {item.aliases.map((alias) => (
                <Badge key={alias} variant="secondary">
                  {alias}
                </Badge>
              ))}
            </div>
          ) : null}
        </CardContent>
      </Card>

      {item.usage_note || item.example ? (
        <Card>
          <CardHeader>
            <CardTitle>Reporting it</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {item.usage_note ? <p>{item.usage_note}</p> : null}
            {item.example ? (
              <p>
                <span className="text-muted-foreground">Example wording: </span>
                <span className="font-serif">{item.example}</span>
              </p>
            ) : null}
            <p className="text-sm text-muted-foreground">
              Catalog text is self-authored for this project, not copied from a source.
            </p>
          </CardContent>
        </Card>
      ) : null}

      {item.related.length ? (
        <Card>
          <CardHeader>
            <CardTitle>Related entries</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="flex flex-col divide-y">
              {item.related.map((related) => {
                const [outgoing, incoming] = RELATION_LABELS[related.relation] ?? [related.relation, related.relation];
                return (
                  <li key={`${related.direction}-${related.relation}-${related.code}`} className="flex items-center justify-between gap-3 py-2">
                    <span className="text-sm text-muted-foreground">
                      {related.direction === "outgoing" ? outgoing : incoming}
                    </span>
                    <Link
                      to="/measurements/$code"
                      params={{ code: related.code }}
                      search={search}
                      className="text-primary hover:underline"
                    >
                      {related.name}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Phrase patterns that can use it</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {item.slot_links.length ? (
            <ul className="flex flex-col divide-y">
              {item.slot_links.map((link) => (
                <li key={link.id} className="flex flex-wrap items-center justify-between gap-3 py-2">
                  <span className="font-serif">{link.canonical_frame ?? "Pattern"}</span>
                  <span className="flex items-center gap-3">
                    <Badge variant="outline">{link.slot_name ? `{${link.slot_name}}` : "Whole pattern"}</Badge>
                    <Link
                      to="/phrasebank/pattern/$id"
                      params={{ id: link.pattern_id }}
                      className="text-sm text-primary hover:underline"
                    >
                      Open pattern
                    </Link>
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">No reviewed pattern links yet.</p>
          )}
          <p className="text-sm text-muted-foreground">
            Slot links are suggestions for a slot; whole-pattern links mark a pattern that describes this measure.
            The writer still chooses and phrases the value.
          </p>
        </CardContent>
      </Card>

      <ProposedLinks code={item.code} />
    </div>
  );
}

/** Curator-only review of proposed links for this entry (e.g. from measurement-propose-links). */
function ProposedLinks({ code }: { code: string }) {
  const { client } = useAuth();
  const isCurator = client?.role === "curator" || client?.role === "admin";
  const proposed = useProposedLinks(isCurator);
  const review = useReviewLink();
  const items = (proposed.data ?? []).filter((link) => link.entry_code === code);
  if (!isCurator || !items.length) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Proposed links to review</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <ul className="flex flex-col divide-y">
          {items.map((link) => (
            <li key={link.id} className="flex flex-wrap items-center justify-between gap-3 py-2">
              <span className="flex flex-col gap-1">
                <span className="font-serif">{link.canonical_frame ?? "Pattern"}</span>
                <span className="text-xs text-muted-foreground">
                  {link.slot_name ? `Slot {${link.slot_name}}` : "Whole pattern"} ·{" "}
                  {link.origin === "term_match" ? "matched catalog term" : "proposed manually"}
                </span>
              </span>
              <span className="flex items-center gap-2">
                <Button
                  size="sm"
                  disabled={review.isPending}
                  onClick={() => review.mutate({ id: link.id, decision: "approved" })}
                >
                  Approve
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={review.isPending}
                  onClick={() => review.mutate({ id: link.id, decision: "rejected" })}
                >
                  Reject
                </Button>
              </span>
            </li>
          ))}
        </ul>
        {review.isError ? <p className="text-sm text-destructive">{review.error.message}</p> : null}
        <p className="text-sm text-muted-foreground">
          A term match is only a candidate. Approve it only if the pattern really describes or reports this measure.
        </p>
      </CardContent>
    </Card>
  );
}
