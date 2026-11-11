import { getRouteApi, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DataState } from "@/components/domain/DataState";
import { PageHeader } from "@/components/domain/PageHeader";
import { ApiError } from "@/features/slr-import/api/client";
import { KIND_LABELS, useMeasurements, type MeasurementKind } from "../api/client";

const route = getRouteApi("/shell/guarded/measurements");
const KINDS: MeasurementKind[] = ["metric", "method", "protocol"];

export function MeasurementPage() {
  const search = route.useSearch();
  const navigate = useNavigate({ from: "/measurements" });
  const [query, setQuery] = useState(search.q ?? "");
  const list = useMeasurements({ kind: search.kind, q: search.q });

  useEffect(() => {
    const handle = window.setTimeout(() => {
      const next = query.trim() || undefined;
      if (next !== search.q) void navigate({ search: (prev) => ({ ...prev, q: next }), replace: true });
    }, 250);
    return () => window.clearTimeout(handle);
  }, [query, search.q, navigate]);

  const disabled = list.error instanceof ApiError && list.error.status === 404;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Metrics & measurement"
        description={
          "How research results are measured: metrics, measurement methods and data-collection " +
          "protocols. The Phrasebank covers how to write about them."
        }
      />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs
          value={search.kind ?? "all"}
          onValueChange={(value) =>
            void navigate({
              search: (prev) => ({ ...prev, kind: value === "all" ? undefined : (value as MeasurementKind) }),
            })
          }
        >
          <TabsList aria-label="Entry kind">
            <TabsTrigger value="all">All</TabsTrigger>
            {KINDS.map((kind) => (
              <TabsTrigger key={kind} value={kind}>
                {KIND_LABELS[kind]}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <Input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search name, alias or definition"
          aria-label="Search the measurement catalog"
          className="w-full sm:w-72"
          maxLength={200}
        />
      </div>

      {list.isPending ? (
        <DataState state="loading" loadingLabel="Loading the measurement catalog" />
      ) : disabled ? (
        <DataState
          state="empty"
          emptyTitle="Measurement catalog is switched off"
          emptyDescription="Set MEASUREMENT_ENABLED=true on the backend and import the catalog to use this page."
        />
      ) : list.isError ? (
        <DataState
          state="error"
          errorTitle="Could not load the catalog"
          errorDescription={list.error.message}
          onRetry={() => void list.refetch()}
        />
      ) : list.data.items.length === 0 ? (
        <DataState
          state="empty"
          emptyTitle={list.data.catalog_version ? "No entries match" : "The catalog is not imported yet"}
          emptyDescription={
            list.data.catalog_version
              ? "Try another search or kind."
              : "Run `make migrate` and `make seed` (or the deploy initializer `python -m aprkb.seeds.load`) to import it."
          }
        />
      ) : (
        <>
          <p className="text-sm text-muted-foreground">
            {list.data.total} {list.data.total === 1 ? "entry" : "entries"}
            {list.data.catalog_version ? ` · catalog ${list.data.catalog_version}` : ""}
          </p>
          <ul className="grid gap-3 md:grid-cols-2">
            {list.data.items.map((item) => (
              <li key={item.code}>
                <Link
                  to="/measurements/$code"
                  params={{ code: item.code }}
                  search={search}
                  className="block h-full rounded-lg no-underline hover:no-underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <Card className="h-full transition-colors hover:bg-muted/50">
                    <CardContent className="flex flex-col gap-2">
                      <div className="flex items-start justify-between gap-3">
                        <span className="font-serif text-lg">{item.name}</span>
                        <Badge variant="outline">{KIND_LABELS[item.kind]}</Badge>
                      </div>
                      <p className="text-sm leading-6 text-muted-foreground">{item.definition}</p>
                      {item.aliases.length ? (
                        <p className="text-xs text-muted-foreground">Also: {item.aliases.join(", ")}</p>
                      ) : null}
                    </CardContent>
                  </Card>
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
