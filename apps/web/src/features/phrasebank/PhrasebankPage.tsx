import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";

import { ApiError } from "@/features/slr-import/api/client";
import { Badge, Card, Empty, Loading, PageHeader } from "@/shared/ui";
import { phrasebankSources, SOURCE_REGISTRY, type ManchesterCategory, type PatternDetail, type SourceId } from "./source-registry";

const NOTICE = "Source: University of Manchester Academic Phrasebank. Internal reference only; reuse rights are not verified; do not redistribute.";
function sourceLabel(source: SourceId) {
  return SOURCE_REGISTRY.find((item) => item.id === source)?.label ?? source;
}

function isReferenceDisabled(error: unknown) {
  return error instanceof ApiError && error.status === 404 && error.body?.error?.message === "Reference library is disabled";
}

function groupBy<T, K extends string>(items: T[], key: (item: T) => K): [K, T[]][] {
  const groups = new Map<K, T[]>();
  for (const item of items) groups.set(key(item), [...(groups.get(key(item)) ?? []), item]);
  return [...groups.entries()];
}

function ManchesterNotice() {
  return <aside className="notice notice-warn phrasebank-notice" aria-label="Source notice">{NOTICE}</aside>;
}

function CategoryCards({ categories, kind }: { categories: ManchesterCategory[]; kind: "section" | "function" }) {
  const rows = categories.filter((item) => item.kind === kind);
  return <div className="phrasebank-cards">
    {rows.map((item) => <Link key={item.slug} to="/phrasebank/$slug" params={{ slug: item.slug }} className="phrasebank-category-card">
      <span><Badge tone="warn">{sourceLabel("manchester-reference")}</Badge> {item.title}</span><Badge>{item.entry_count} entries</Badge>
    </Link>)}
  </div>;
}

function useDebounced(value: string, delay = 250) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

function phraseRow(cells: string[][]) {
  return cells.map((alternatives) => alternatives.join(" / ")).join(" ");
}

function PhraseRow({ cells }: { cells: string[][] }) {
  const copy = async () => navigator.clipboard?.writeText(phraseRow(cells));
  return <tr>
    {cells.map((alternatives, index) => <td key={index}>{alternatives.map((text) => <div key={text}>{text}</div>)}</td>)}
    <td><Badge tone="warn">{sourceLabel("manchester-reference")}</Badge> <button type="button" className="btn btn-ghost btn-sm" onClick={() => void copy()} aria-label="Copy phrase row">Copy</button></td>
  </tr>;
}

function EntryList({ entries }: { entries: NonNullable<NonNullable<Awaited<ReturnType<typeof phrasebankSources.category>>>["headings"][number]["entries"]> }) {
  const notes = entries.filter((entry) => entry.kind === "note");
  const phrases = entries.filter((entry) => entry.kind === "phrase" && entry.cells);
  return <div className="phrasebank-entry-list">
    {notes.map((entry) => <p key={entry.id}><Badge tone="warn">{sourceLabel("manchester-reference")}</Badge> {entry.text}</p>)}
    {phrases.length > 0 && <div className="phrasebank-table-wrap"><table className="phrasebank-table"><tbody>
      {phrases.map((entry) => <PhraseRow key={entry.id} cells={entry.cells ?? []} />)}
    </tbody></table></div>}
    {entries.length === 0 && <Empty>No entries in this heading.</Empty>}
  </div>;
}

function PatternGroups({ patterns, query = "" }: { patterns: PatternDetail[]; query?: string }) {
  const filtered = patterns.filter((pattern) => !query || `${pattern.canonical_frame ?? ""} ${pattern.intent_code} ${pattern.allowed_sections.join(" ")}`.toLowerCase().includes(query.toLowerCase()));
  // TODO(owner): Decide whether taxonomy codes map to Manchester categories; do not infer a mapping.
  const groups = new Map<string, PatternDetail[]>();
  for (const pattern of filtered) {
    for (const section of pattern.allowed_sections) {
      const key = `${section} · ${pattern.intent_code}`;
      groups.set(key, [...(groups.get(key) ?? []), pattern]);
    }
  }
  if (!filtered.length) return <Empty>No approved AP-RKB patterns match this search.</Empty>;
  return <div className="stack">
    {[...groups.entries()].map(([group, items]) => <section key={group}>
      <h3>{group}</h3>
      <ul className="phrasebank-pattern-list">
        {items.map((pattern) => <li id={`pattern-${pattern.id}`} key={pattern.id}>
          <Badge tone="info">{sourceLabel("aprkb-patterns")}</Badge>
          <p><a href={`/phrasebank/aprkb-patterns#pattern-${pattern.id}`}>{pattern.canonical_frame}</a></p>
        </li>)}
      </ul>
    </section>)}
  </div>;
}

export function PhrasebankHome() {
  const [source, setSource] = useState<"all" | SourceId>("all");
  const [search, setSearch] = useState("");
  const query = useDebounced(search.trim());
  const manchester = useQuery({ queryKey: ["phrasebank-categories"], queryFn: phrasebankSources.categories, retry: false });
  const patterns = useQuery({ queryKey: ["phrasebank-patterns"], queryFn: phrasebankSources.patterns, enabled: source !== "manchester-reference", retry: false });
  const results = useQuery({ queryKey: ["phrasebank-search", query], queryFn: () => phrasebankSources.search(query), enabled: Boolean(query) && source !== "aprkb-patterns", retry: false });
  const disabled = isReferenceDisabled(manchester.error);
  const patternMatches = useMemo(() => (patterns.data ?? []).filter((pattern) =>
    !query || `${pattern.canonical_frame ?? ""} ${pattern.intent_code} ${pattern.allowed_sections.join(" ")}`.toLowerCase().includes(query.toLowerCase())), [patterns.data, query]);

  return <div className="stack">
    <PageHeader code="Reference library" title="Phrasebank" lead="Browse source-aware phrase collections. Manchester reference material and AP-RKB patterns remain separate collections." />
    <ManchesterNotice />
    <Card title="Search the phrasebank">
      <div className="phrasebank-search-controls">
        <input type="search" aria-label="Search phrasebanks" placeholder="Search phrases and categories" value={search} onChange={(event) => setSearch(event.target.value)} />
        <select aria-label="Source filter" value={source} onChange={(event) => setSource(event.target.value as "all" | SourceId)}>
          <option value="all">All sources</option><option value="manchester-reference">Manchester reference</option><option value="aprkb-patterns">AP-RKB patterns</option>
        </select>
      </div>
    </Card>
    {query ? <>
      <Card title="Search results">
        {source !== "aprkb-patterns" && (results.isPending ? <Loading /> : disabled ? <p className="notice notice-warn" role="status">Manchester reference is disabled. Enable `REFERENCE_LIBRARY_ENABLED` to browse it.</p> : (results.data?.results.length ?? 0) === 0 ? <Empty>No Manchester reference results.</Empty> : <div className="stack">
          {groupBy(results.data?.results ?? [], (item) => item.category_slug).map(([slug, items]) => <section key={slug}>
            <h3>{items?.[0]?.category_title}</h3>
            {groupBy(items ?? [], (item) => String(item.entry.heading_position)).map(([position, group]) => <div key={position}>
              <h4>{group[0]?.heading}</h4>
              {group.map((item) => <p key={item.entry.id}><Badge tone="warn">{sourceLabel("manchester-reference")}</Badge> {item.entry.text ?? item.entry.cells?.map((cell) => cell.join(" / ")).join(" ")} <a href={`/phrasebank/${slug}#heading-${slug}-${position}`}>Open heading</a></p>)}
            </div>)}
          </section>)}
        </div>)}
        {source !== "manchester-reference" && <section><h3>AP-RKB patterns</h3><PatternGroups patterns={patternMatches} query={query} /></section>}
      </Card>
    </> : <>
      {source !== "aprkb-patterns" && <Card title="Sections">
        {disabled ? <p className="notice notice-warn" role="status">Manchester reference is disabled. Enable `REFERENCE_LIBRARY_ENABLED` to browse these categories.</p> : manchester.isPending ? <Loading /> : <CategoryCards categories={manchester.data?.categories ?? []} kind="section" />}
      </Card>}
      {source !== "aprkb-patterns" && <Card title="General functions">
        {disabled ? <Empty>Manchester general functions are unavailable while the reference API is disabled.</Empty> : manchester.isPending ? <Loading /> : <CategoryCards categories={manchester.data?.categories ?? []} kind="function" />}
      </Card>}
      {source !== "manchester-reference" && <Card title={<Link to="/phrasebank/$slug" params={{ slug: "aprkb-patterns" }}>AP-RKB patterns</Link>} aside={<><Badge tone="info">{sourceLabel("aprkb-patterns")}</Badge> <Badge>{patterns.data?.length ?? 0} approved</Badge></>}>
        {patterns.isPending ? <Loading /> : <PatternGroups patterns={patternMatches} />}
      </Card>}
    </>}
  </div>;
}

export function PhrasebankCategory({ slug }: { slug: string }) {
  const manchester = useQuery({ queryKey: ["phrasebank-category", slug], queryFn: () => phrasebankSources.category(slug), enabled: slug !== "aprkb-patterns", retry: false });
  const patterns = useQuery({ queryKey: ["phrasebank-patterns"], queryFn: phrasebankSources.patterns, enabled: slug === "aprkb-patterns", retry: false });
  const disabled = isReferenceDisabled(manchester.error);
  if (slug === "aprkb-patterns") return <div className="stack">
    <ManchesterNotice /><p><Link to="/phrasebank">← Phrasebank home</Link></p>
    <PageHeader code={sourceLabel("aprkb-patterns")} title="Approved AP-RKB patterns" lead="Self-authored patterns are shown from the approved client view of the existing pattern API." />
    {patterns.isPending ? <Loading /> : <PatternGroups patterns={patterns.data ?? []} />}
  </div>;
  if (disabled) return <div className="stack"><ManchesterNotice /><p><Link to="/phrasebank">← Phrasebank home</Link></p><p className="notice notice-warn" role="status">Manchester reference is disabled. Enable `REFERENCE_LIBRARY_ENABLED` to browse this category.</p></div>;
  if (manchester.isPending) return <div className="stack"><ManchesterNotice /><Loading /></div>;
  const category = manchester.data;
  if (manchester.isError) return <div className="stack"><ManchesterNotice /><Empty>{manchester.error instanceof ApiError && manchester.error.status === 404 ? "Category not found or reference data has not been imported." : "The reference category could not be loaded."}</Empty></div>;
  if (!category) return <div className="stack"><ManchesterNotice /><Empty>Category not found.</Empty></div>;
  const intro = category.headings[0];
  const sections = category.headings.slice(1);
  return <div className="stack">
    <ManchesterNotice />
    <p><Link to="/phrasebank">← Phrasebank home</Link></p>
    <PageHeader code={sourceLabel("manchester-reference")} title={category.category.title} lead={category.category.kind === "section" ? "Paper structure" : "General function"} />
    <section id={`heading-${category.category.slug}-${intro?.heading_position ?? 0}`} className="phrasebank-intro"><EntryList entries={intro?.entries ?? []} /></section>
    <nav className="phrasebank-index" aria-label="In-page headings"><strong>On this page</strong><div>{sections.map((item) => <a key={item.heading_position} href={`#heading-${category.category.slug}-${item.heading_position}`}>{item.heading}</a>)}</div></nav>
    {sections.map((item) => <section className="phrasebank-section" id={`heading-${category.category.slug}-${item.heading_position}`} key={item.heading_position}>
      <h2>{item.heading}</h2><Badge>{sourceLabel("manchester-reference")}</Badge><EntryList entries={item.entries} />
    </section>)}
  </div>;
}
