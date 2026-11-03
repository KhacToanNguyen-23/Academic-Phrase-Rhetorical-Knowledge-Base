import { getRouteApi, Link, useNavigate } from "@tanstack/react-router"
import { useEffect, useMemo, useState, type ReactNode } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Field, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Pagination, PaginationContent, PaginationItem, PaginationNext, PaginationPrevious } from "@/components/ui/pagination"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { DataState } from "@/components/domain/DataState"
import { PageHeader } from "@/components/domain/PageHeader"
import { useAuth } from "@/features/auth/AuthProvider"
import { useFamilies, useLemmas, useLetters } from "../api/client"
import { VocabularyImportCard } from "./VocabularyImportCard"

const route = getRouteApi("/shell/guarded/vocabulary")
const alphabet = [..."abcdefghijklmnopqrstuvwxyz", "#"]

function statusVariant(status: string | null): "success" | "warning" | "secondary" | "default" {
  if (status === "y") return "success"
  if (status === "r") return "warning"
  if (status === "x") return "secondary"
  return "default"
}

function QueryState({ pending, error, empty, onRetry, emptyTitle, emptyDescription, emptyAction }: { pending: boolean; error: Error | null; empty: boolean; onRetry: () => void; emptyTitle: string; emptyDescription: string; emptyAction?: ReactNode }) {
  if (pending) return <div className="flex flex-col gap-3" aria-busy="true" aria-label="Loading vocabulary"><Skeleton className="h-8 w-1/3" /><Skeleton className="h-12 w-full" /><Skeleton className="h-12 w-full" /></div>
  if (error) return <DataState state="error" errorTitle="Could not load vocabulary" errorDescription={error.message} onRetry={onRetry} />
  if (empty) return <DataState state="empty" emptyTitle={emptyTitle} emptyDescription={emptyDescription} emptyAction={emptyAction} />
  return null
}

export function VocabularyPage() {
  const { client: authClient } = useAuth()
  const search = route.useSearch()
  const navigate = useNavigate({ from: "/vocabulary" })
  const [query, setQuery] = useState(search.q ?? "")
  const [debouncedQuery, setDebouncedQuery] = useState(search.q ?? "")
  const [showImport, setShowImport] = useState(false)
  const view = search.view ?? "lemmas"
  const coreOnly = search.coreOnly ?? false
  const sort = search.sort ?? "alpha"
  const offset = search.offset ?? 0
  const limit = 50
  const isCurator = authClient?.role === "curator" || authClient?.role === "admin"
  const letters = useLetters(coreOnly)
  const lemmas = useLemmas({ q: debouncedQuery || undefined, letter: search.letter, core_only: coreOnly, sort, limit, offset })
  const families = useFamilies({ q: debouncedQuery || undefined, limit, offset })

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedQuery(query.trim())
      void navigate({ search: (previous) => ({ ...previous, q: query.trim() || undefined, letter: query.trim() ? undefined : previous.letter, offset: 0 }) })
    }, 250)
    return () => window.clearTimeout(timer)
  }, [navigate, query])
  useEffect(() => { if (search.q !== undefined && search.q !== query) setQuery(search.q) }, [search.q, query])

  const counts = useMemo(() => new Map((letters.data ?? []).map((item) => [item.letter, item.count])), [letters.data])
  const totalLettersCount = useMemo(() => (letters.data ?? []).reduce((sum, item) => sum + item.count, 0), [letters.data])
  const total = view === "families" ? (families.data?.total ?? 0) : (lemmas.data?.total ?? 0)
  const first = total === 0 ? 0 : offset + 1
  const last = Math.min(offset + limit, total)
  const hasActiveFilters = Boolean(search.q || search.letter || coreOnly || sort !== "alpha")
  const updateSearch = (patch: Partial<typeof search>) => void navigate({ search: (previous) => ({ ...previous, ...patch }) })
  const clearFilters = () => { setQuery(""); setDebouncedQuery(""); updateSearch({ q: undefined, letter: undefined, coreOnly: undefined, sort: undefined, offset: 0 }) }

  return <div className="flex flex-col gap-6">
    <PageHeader title="Academic vocabulary" description="Browse and inspect the academic lexicon by lemma, rank, and word family." actions={isCurator ? <Button variant={showImport ? "outline" : "default"} onClick={() => setShowImport((open) => !open)}>{showImport ? "Close import" : "Import vocabulary"}</Button> : undefined} />
    {showImport && isCurator ? <VocabularyImportCard onClose={() => setShowImport(false)} /> : null}
    <Tabs value={view} onValueChange={(nextView) => updateSearch({ view: nextView as "lemmas" | "families", offset: 0, letter: nextView === "families" ? undefined : search.letter, coreOnly: nextView === "families" ? undefined : search.coreOnly, sort: nextView === "families" ? undefined : search.sort })} className="flex flex-col gap-4">
      <TabsList aria-label="Vocabulary view"><TabsTrigger value="lemmas">Lemmas{lemmas.data ? ` (${lemmas.data.total.toLocaleString()})` : ""}</TabsTrigger><TabsTrigger value="families">Word families{families.data ? ` (${families.data.total.toLocaleString()})` : ""}</TabsTrigger></TabsList>
      <Card><CardContent className="flex flex-col gap-4 pt-4">
        <div className="flex items-end gap-4"><Field className="max-w-xl"><FieldLabel htmlFor="vocabulary-search">Search vocabulary</FieldLabel><Input id="vocabulary-search" type="search" placeholder={view === "families" ? "Search word families by headword" : "Search lemmas by prefix"} value={query} onChange={(event) => setQuery(event.target.value)} /></Field>{query ? <Button variant="ghost" onClick={() => setQuery("")}>Clear</Button> : null}</div>
        <TabsContent value="lemmas" className="flex flex-col gap-4">
          <div className="flex items-end gap-6"><Field orientation="horizontal" className="w-auto"><Checkbox id="vocabulary-core" checked={coreOnly} onCheckedChange={(checked) => updateSearch({ coreOnly: checked === true ? true : undefined, offset: 0 })} /><FieldLabel htmlFor="vocabulary-core">Core only</FieldLabel></Field><Field className="w-44"><FieldLabel>Sort order</FieldLabel><Select value={sort} onValueChange={(value) => updateSearch({ sort: value as "alpha" | "rank", offset: 0 })}><SelectTrigger aria-label="Sort order"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="alpha">A–Z</SelectItem><SelectItem value="rank">Academic rank</SelectItem></SelectContent></Select></Field>{hasActiveFilters ? <Button variant="outline" onClick={clearFilters}>Reset filters</Button> : null}</div>
          <ToggleGroup type="single" value={search.letter ?? "all"} onValueChange={(value) => { if (!value) return; setQuery(""); setDebouncedQuery(""); updateSearch({ letter: value === "all" ? undefined : value, q: undefined, offset: 0 }) }} aria-label="Filter vocabulary by initial letter" className="flex flex-wrap gap-1"><ToggleGroupItem value="all" aria-label="All letters" className="h-10 min-w-12 flex-col gap-0"><span>All</span><small className="tabular-nums text-muted-foreground">{totalLettersCount}</small></ToggleGroupItem>{alphabet.map((letter) => { const count = counts.get(letter) ?? 0; return <ToggleGroupItem key={letter} value={letter} disabled={!letters.isPending && count === 0} aria-label={`${letter.toUpperCase()} ${count} lemmas`} className="h-10 min-w-10 flex-col gap-0"><span>{letter.toUpperCase()}</span><small className="tabular-nums text-muted-foreground">{count}</small></ToggleGroupItem> })}</ToggleGroup>
        </TabsContent>
      </CardContent></Card>
      <TabsContent value="lemmas" className="mt-0"><Card><CardHeader><CardTitle>Academic lemmas</CardTitle></CardHeader><CardContent className="flex flex-col gap-4"><QueryState pending={lemmas.isPending} error={lemmas.isError ? lemmas.error : null} empty={!lemmas.isPending && !lemmas.isError && lemmas.data.items.length === 0} onRetry={() => void lemmas.refetch()} emptyTitle={hasActiveFilters ? "No lemmas match these filters" : "No academic lemmas loaded"} emptyDescription={hasActiveFilters ? "Try another search, letter, or sort order." : "The lexicon has not been imported yet."} emptyAction={hasActiveFilters ? <Button variant="outline" onClick={clearFilters}>Reset filters</Button> : isCurator ? <Button variant="outline" onClick={() => setShowImport(true)}>Open import tool</Button> : undefined} />{!lemmas.isPending && !lemmas.isError && lemmas.data.items.length > 0 ? <Table><TableHeader><TableRow><TableHead>Lemma</TableHead><TableHead>Part of speech</TableHead><TableHead numeric>Rank</TableHead><TableHead numeric>Band</TableHead><TableHead>Status</TableHead><TableHead>Action</TableHead></TableRow></TableHeader><TableBody>{lemmas.data.items.map((item) => <TableRow key={item.id}><TableCell><Link className="font-medium text-primary hover:underline" to="/vocabulary/$lemmaId" params={{ lemmaId: item.id }} search={search}>{item.word}</Link></TableCell><TableCell><Badge variant="outline">{item.pos_label}</Badge></TableCell><TableCell numeric>{item.rank !== null ? `#${item.rank}` : "—"}</TableCell><TableCell numeric>{item.band !== null ? `Band ${item.band}` : "—"}</TableCell><TableCell><Badge variant={statusVariant(item.status)}>{item.status_label || "Unknown"}</Badge></TableCell><TableCell><Button asChild variant="outline" size="sm"><Link to="/vocabulary/$lemmaId" params={{ lemmaId: item.id }} search={search}>Details</Link></Button></TableCell></TableRow>)}</TableBody></Table> : null}{total > 0 ? <Pagination><PaginationContent><PaginationItem><PaginationPrevious text="Previous" aria-disabled={offset === 0} className={offset === 0 ? "pointer-events-none opacity-50" : undefined} onClick={(event) => { event.preventDefault(); if (offset > 0) updateSearch({ offset: Math.max(0, offset - limit) }) }} href="#" /></PaginationItem><PaginationItem><span className="px-3 text-sm text-muted-foreground">{first.toLocaleString()}–{last.toLocaleString()} of {total.toLocaleString()}</span></PaginationItem><PaginationItem><PaginationNext text="Next" aria-disabled={last >= total} className={last >= total ? "pointer-events-none opacity-50" : undefined} onClick={(event) => { event.preventDefault(); if (last < total) updateSearch({ offset: offset + limit }) }} href="#" /></PaginationItem></PaginationContent></Pagination> : null}</CardContent></Card></TabsContent>
      <TabsContent value="families" className="mt-0"><Card><CardHeader><CardTitle>Academic word families</CardTitle></CardHeader><CardContent className="flex flex-col gap-4"><QueryState pending={families.isPending} error={families.isError ? families.error : null} empty={!families.isPending && !families.isError && families.data.items.length === 0} onRetry={() => void families.refetch()} emptyTitle={query ? "No word families match this search" : "No word families recorded"} emptyDescription="Try a different search or import a vocabulary spreadsheet." emptyAction={query ? <Button variant="outline" onClick={() => setQuery("")}>Clear search</Button> : undefined} />{!families.isPending && !families.isError && families.data.items.length > 0 ? <div className="flex flex-col gap-3">{families.data.items.map((family) => <details key={family.id} className="rounded-[var(--radius)] border border-border"><summary className="flex cursor-pointer items-center justify-between gap-4 px-4 py-3 hover:bg-muted/50"><span className="flex items-center gap-3"><strong>{family.headword}</strong><Badge variant="outline">{family.members.length} members</Badge></span><span className="text-sm text-muted-foreground">Rank {family.rank} · {family.family_freq.toLocaleString()} frequency</span></summary><div className="border-t border-border p-2"><Table><TableHeader><TableRow><TableHead>Word form</TableHead><TableHead>Part of speech</TableHead><TableHead numeric>Frequency</TableHead><TableHead>Category</TableHead><TableHead>Domains</TableHead><TableHead>Action</TableHead></TableRow></TableHeader><TableBody>{family.members.map((member) => <TableRow key={`${family.id}-${member.lemma_id}`}><TableCell><Link className="font-medium text-primary hover:underline" to="/vocabulary/$lemmaId" params={{ lemmaId: member.lemma_id }} search={search}>{member.word}</Link></TableCell><TableCell><Badge variant="outline">{member.pos_label}</Badge></TableCell><TableCell numeric>{member.freq.toLocaleString()}</TableCell><TableCell><Badge>{member.category_label}</Badge></TableCell><TableCell>{member.domains.join(", ") || "—"}</TableCell><TableCell><Button asChild variant="outline" size="sm"><Link to="/vocabulary/$lemmaId" params={{ lemmaId: member.lemma_id }} search={search}>Inspect</Link></Button></TableCell></TableRow>)}</TableBody></Table></div></details>)}</div> : null}{total > 0 ? <p className="text-sm text-muted-foreground">Showing {first.toLocaleString()}–{last.toLocaleString()} of {total.toLocaleString()} families.</p> : null}</CardContent></Card></TabsContent>
    </Tabs>
  </div>
}
