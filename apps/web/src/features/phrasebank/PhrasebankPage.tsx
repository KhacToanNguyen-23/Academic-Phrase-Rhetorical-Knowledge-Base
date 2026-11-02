import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
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

function scrollToHeading(id: string) {
  const target = document.getElementById(id);
  target?.scrollIntoView({ block: "start", behavior: "instant" });
}

function scrollAfterNavigation(id: string) {
  let attempts = 0;
  const tryScroll = () => {
    const target = document.getElementById(id);
    if (target) target.scrollIntoView({ block: "start", behavior: "instant" });
    else if (attempts++ < 40) window.setTimeout(tryScroll, 50);
  };
  window.setTimeout(tryScroll, 0);
}

function PhraseRow({ cells }: { cells: string[][] }) {
  const copy = async () => navigator.clipboard?.writeText(phraseRow(cells));
  return <tr>
    {cells.map((alternatives, index) => <td key={`cell-${index}`}>{alternatives.map((text, alternativeIndex) => <div key={`alternative-${alternativeIndex}`}>{text}</div>)}</td>)}
    <td><button type="button" className="btn btn-ghost btn-sm" onClick={() => void copy()} aria-label="Copy phrase row">Copy</button></td>
  </tr>;
}

function EntryList({ entries }: { entries: NonNullable<NonNullable<Awaited<ReturnType<typeof phrasebankSources.category>>>["headings"][number]["entries"]> }) {
  const blocks: ({ kind: "note"; id: string; text: string | null } | { kind: "table"; id: string; entries: typeof entries })[] = [];
  for (const entry of entries) {
    if (entry.kind === "note") blocks.push({ kind: "note", id: entry.id, text: entry.text });
    else {
      const previous = blocks.at(-1);
      if (previous?.kind === "table" && previous.id === String(entry.block_index)) previous.entries.push(entry);
      else blocks.push({ kind: "table", id: String(entry.block_index), entries: [entry] });
    }
  }
  return <div className="phrasebank-entry-list">
    {blocks.map((block) => block.kind === "note"
      ? <p key={block.id}>{block.text}</p>
      : <div className="phrasebank-table-wrap" key={`table-${block.id}`}><table className="phrasebank-table"><tbody>
        {block.entries.map((entry) => <PhraseRow key={entry.id} cells={entry.cells ?? []} />)}
      </tbody></table></div>)}
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
          <p><Link to="/phrasebank/$slug" params={{ slug: "aprkb-patterns" }} hash={`pattern-${pattern.id}`}>{pattern.canonical_frame}</Link> <Link to="/writer" className="btn btn-ghost btn-sm">Use in Writer</Link></p>
        </li>)}
      </ul>
    </section>)}
  </div>;
}

export function PhrasebankHome() {
  const navigate = useNavigate();
  const [source, setSource] = useState<"all" | SourceId>("all");
  const [search, setSearch] = useState("");
  const query = useDebounced(search.trim());
  const manchester = useQuery({ queryKey: ["phrasebank-categories"], queryFn: phrasebankSources.categories, retry: false });
  const patterns = useQuery({ queryKey: ["phrasebank-patterns"], queryFn: phrasebankSources.patterns, enabled: source !== "manchester-reference", retry: false });
  const results = useQuery({ queryKey: ["phrasebank-search", query], queryFn: () => phrasebankSources.search(query), enabled: Boolean(query) && source !== "aprkb-patterns", retry: false });
  const disabled = isReferenceDisabled(manchester.error);
  const patternMatches = useMemo(() => (patterns.data ?? []).filter((pattern) =>
    !query || `${pattern.canonical_frame ?? ""} ${pattern.intent_code} ${pattern.allowed_sections.join(" ")}`.toLowerCase().includes(query.toLowerCase())), [patterns.data, query]);

  return <div className="stack phrasebank-home">
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
            <h3>{items?.[0]?.category_title} <Badge tone="warn">{sourceLabel("manchester-reference")}</Badge></h3>
            {groupBy(items ?? [], (item) => String(item.entry.heading_position)).map(([position, group]) => <div key={position}>
              <h4>{group[0]?.heading}</h4>
              {group.map((item) => {
                const targetId = `heading-${slug}-${position}`;
                return <p key={item.entry.id}>{item.entry.text ?? item.entry.cells?.map((cell) => cell.join(" / ")).join(" ")} <Link to="/phrasebank/$slug" params={{ slug }} hash={targetId} onClick={(event) => { event.preventDefault(); void navigate({ to: "/phrasebank/$slug", params: { slug }, hash: targetId }).then(() => scrollAfterNavigation(targetId)); }}>Open heading</Link></p>;
              })}
            </div>)}
          </section>)}
        </div>)}
        {source !== "manchester-reference" && <section><h3>AP-RKB patterns <Badge tone="info">{sourceLabel("aprkb-patterns")}</Badge></h3><PatternGroups patterns={patternMatches} query={query} /></section>}
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
  const navigate = useNavigate();
  const locationHref = useRouterState({ select: (state) => state.location.href });
  const manchester = useQuery({ queryKey: ["phrasebank-category", slug], queryFn: () => phrasebankSources.category(slug), enabled: slug !== "aprkb-patterns", retry: false });
  const patterns = useQuery({ queryKey: ["phrasebank-patterns"], queryFn: phrasebankSources.patterns, enabled: slug === "aprkb-patterns", retry: false });
  const disabled = isReferenceDisabled(manchester.error);
  useEffect(() => {
    const hash = new URL(locationHref, window.location.origin).hash;
    if (!hash || (slug === "aprkb-patterns" && patterns.isPending)) return;
    const targetId = decodeURIComponent(hash.slice(1));
    window.setTimeout(() => scrollToHeading(targetId), 250);
  }, [locationHref, slug, manchester.data, patterns.data, patterns.isPending]);
  if (slug === "aprkb-patterns") return <div className="stack">
    <ManchesterNotice /><p><Link to="/phrasebank">← Phrasebank home</Link></p>
    <PageHeader title={<span className="phrasebank-category-title">Approved AP-RKB patterns <Badge tone="info">{sourceLabel("aprkb-patterns")}</Badge></span>} lead="Self-authored patterns are shown from the approved client view of the existing pattern API." />
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
    <PageHeader title={<span className="phrasebank-category-title">{category.category.title} <Badge tone="warn">{sourceLabel("manchester-reference")}</Badge></span>} lead={category.category.kind === "section" ? "Paper structure" : "General function"} />
    <section id={`heading-${category.category.slug}-${intro?.heading_position ?? 0}`} className="phrasebank-intro"><EntryList entries={intro?.entries ?? []} /></section>
    <nav className="phrasebank-index" aria-label="In-page headings"><strong>On this page</strong><div>{sections.map((item) => {
      const targetId = `heading-${category.category.slug}-${item.heading_position}`;
      return <Link key={item.heading_position} to="/phrasebank/$slug" params={{ slug: category.category.slug }} hash={targetId} onClick={(event) => { event.preventDefault(); void navigate({ to: "/phrasebank/$slug", params: { slug: category.category.slug }, hash: targetId }).then(() => scrollAfterNavigation(targetId)); }}>{item.heading}</Link>;
    })}</div></nav>
    {sections.map((item) => <section className="phrasebank-section" id={`heading-${category.category.slug}-${item.heading_position}`} key={item.heading_position}>
      <h2>{item.heading}</h2><EntryList entries={item.entries} />
    </section>)}
  </div>;
}
