import { getRouteApi, Link } from "@tanstack/react-router";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DataState } from "@/components/domain/DataState";
import { PageHeader } from "@/components/domain/PageHeader";
import { useLemma } from "../api/client";

const route = getRouteApi("/shell/guarded/vocabulary/$lemmaId");

export function VocabularyLemmaPage() {
  const { lemmaId } = route.useParams();
  const search = route.useSearch();
  const lemma = useLemma(lemmaId);

  if (lemma.isPending)
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title="Vocabulary lemma" description="Loading the selected lemma." />
        <div className="flex flex-col gap-3" aria-busy="true" aria-label="Loading lemma">
          <Skeleton className="h-8 w-1/3" />
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-52 w-full" />
        </div>
      </div>
    );
  if (lemma.isError)
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title="Vocabulary lemma" description="The selected lemma could not be loaded." />
        <DataState
          state="error"
          errorTitle="Could not load this lemma"
          errorDescription={lemma.error.message}
          onRetry={() => void lemma.refetch()}
        />
      </div>
    );
  if (!lemma.data)
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title="Vocabulary lemma" description="The selected lemma is not available." />
        <DataState
          state="empty"
          emptyTitle="Vocabulary lemma not found"
          emptyDescription="The requested lemma is not available in the current lexicon."
          emptyAction={
            <Button asChild variant="outline">
              <Link to="/vocabulary" search={search}>
                Back to vocabulary
              </Link>
            </Button>
          }
        />
      </div>
    );

  const item = lemma.data;
  const maxRatio = Math.max(1.2, ...item.domain_stats.map((stat) => stat.relative_ratio));
  const hasFamilies = item.families.length > 0;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={
          <span className="flex items-baseline gap-3">
            <span className="font-serif text-3xl">{item.word}</span>
            <span className="text-base text-muted-foreground">({item.pos_label})</span>
          </span>
        }
        description={
          `Academic lemma ${item.rank !== null ? `#${item.rank}` : "without a rank"} ` +
          `· Band ${item.band ?? "—"} · ` +
          item.status_label
        }
        actions={
          <Button asChild variant="outline">
            <Link to="/vocabulary" search={search}>
              Back to vocabulary
            </Link>
          </Button>
        }
      />

      <div className="grid grid-cols-4 gap-3">
        {[
          ["Rank", item.rank !== null ? `#${item.rank}` : "—", "AVL frequency rank"],
          ["Band", item.band !== null ? `Band ${item.band}` : "—", "Core academic band"],
          ["COCA-Acad", item.coca_acad !== null ? item.coca_acad.toLocaleString() : "—", "Academic occurrences"],
          ["COCA-All", item.coca_all !== null ? item.coca_all.toLocaleString() : "—", "Total corpus occurrences"],
          ["Ratio", item.ratio !== null ? `${item.ratio.toFixed(2)}x` : "—", "Academic vs general"],
          ["Dispersion", item.disp !== null ? item.disp.toFixed(2) : "—", "Cross-disciplinary spread"],
          ["Range", item.range !== null ? `${item.range}/9` : "—", "Disciplines represented"],
        ].map(([label, value, note]) => (
          <Card key={label}>
            <CardContent className="flex flex-col gap-1 pt-4">
              <span className="text-xs text-muted-foreground">{label}</span>
              <strong className="text-xl tabular-nums">{value}</strong>
              <span className="text-xs text-muted-foreground">{note}</span>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="font-serif text-xl">Example use</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="font-serif text-lg leading-7">
            The study uses {item.word} as a precise term for the reported analysis.
          </p>
          <p className="mt-3 text-sm text-muted-foreground">
            This illustrative sentence is written for the interface and is not copied from a source corpus.
          </p>
        </CardContent>
      </Card>

      {item.domain_stats.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Disciplinary distribution</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <p className="text-sm text-muted-foreground">
              Relative ratio compares frequency in each discipline against a uniform academic expectation. Values above
              1.0 indicate stronger specialization.
            </p>
            <div className="flex flex-col gap-3" role="list" aria-label="Relative ratio by academic domain">
              {item.domain_stats.map((stat) => (
                <div key={stat.domain} className="grid grid-cols-[12rem_1fr_5rem] items-center gap-3" role="listitem">
                  <span className="text-sm">{stat.domain_label}</span>
                  <div className="h-3 rounded-sm bg-muted">
                    <span
                      className="block h-3 rounded-sm bg-primary"
                      style={{ width: `${Math.min(100, (stat.relative_ratio / maxRatio) * 100)}%` }}
                      title={`${stat.relative_ratio.toFixed(2)}x`}
                    />
                  </div>
                  <span className="text-right text-sm tabular-nums">{stat.relative_ratio.toFixed(2)}x</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="pt-4">
            <DataState
              state="empty"
              emptyTitle="No disciplinary distribution"
              emptyDescription="This lemma has no domain-level frequency data yet."
            />
          </CardContent>
        </Card>
      )}

      {hasFamilies ? (
        <Card>
          <CardHeader>
            <CardTitle>Morphological word family</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-5">
            {item.families.map((family) => (
              <section key={family.id} className="flex flex-col gap-3">
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <h2 className="font-serif text-xl">{family.headword}</h2>
                    <Badge variant="outline">{family.members.length} members</Badge>
                  </div>
                  <span className="text-sm text-muted-foreground">
                    Rank {family.rank} · {family.family_freq.toLocaleString()} total frequency
                  </span>
                </div>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Word form</TableHead>
                      <TableHead>Part of speech</TableHead>
                      <TableHead numeric>Frequency</TableHead>
                      <TableHead>Category</TableHead>
                      <TableHead>Domains</TableHead>
                      <TableHead>Action</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {family.members.map((member) => {
                      const current = member.lemma_id === item.id;
                      return (
                        <TableRow key={`${family.id}-${member.lemma_id}`} data-state={current ? "selected" : undefined}>
                          <TableCell>
                            {current ? (
                              <span className="font-medium">
                                {member.word} <Badge variant="outline">Selected</Badge>
                              </span>
                            ) : (
                              <Link
                                className="font-medium text-primary hover:underline"
                                to="/vocabulary/$lemmaId"
                                params={{ lemmaId: member.lemma_id }}
                                search={search}
                              >
                                {member.word}
                              </Link>
                            )}
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline">{member.pos_label}</Badge>
                          </TableCell>
                          <TableCell numeric>{member.freq.toLocaleString()}</TableCell>
                          <TableCell>
                            <Badge>{member.category_label}</Badge>
                          </TableCell>
                          <TableCell>{member.domains.join(", ") || "—"}</TableCell>
                          <TableCell>
                            {current ? (
                              <span className="text-sm text-muted-foreground">Current</span>
                            ) : (
                              <Button asChild variant="outline" size="sm">
                                <Link to="/vocabulary/$lemmaId" params={{ lemmaId: member.lemma_id }} search={search}>
                                  Inspect
                                </Link>
                              </Button>
                            )}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </section>
            ))}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
