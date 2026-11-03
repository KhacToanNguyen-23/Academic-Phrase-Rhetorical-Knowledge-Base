import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import { useEffect, useState } from "react";

import { ApiError } from "@/features/slr-import/api/client";
import { Card, Empty, Loading, PageHeader } from "@/shared/ui";
import { PHRASEBANK_SOURCES, phrasebankSources, type ManchesterCategory, type ManchesterSearchResult, type PatternDetail, type SourceId, type TaxonomyTree } from "./source-registry";

const SOURCE_CREDIT = "Source: University of Manchester Academic Phrasebank.";

function isReferenceDisabled(error: unknown) {
  return error instanceof ApiError && error.status === 404 && error.body?.error?.message === "Reference library is disabled";
}

function groupBy<T, K extends string>(items: T[], key: (item: T) => K): [K, T[]][] {
  const groups = new Map<K, T[]>();
  for (const item of items) groups.set(key(item), [...(groups.get(key(item)) ?? []), item]);
  return [...groups.entries()];
}

function SourceCredit() {
  return <p className="phrasebank-source-credit">{SOURCE_CREDIT}</p>;
}

function CategoryCards({ categories, kind }: { categories: ManchesterCategory[]; kind: "section" | "function" }) {
  const rows = categories.filter((item) => item.kind === kind);
  return <div className="phrasebank-cards">
    {rows.map((item) => <Link key={item.slug} to="/phrasebank/$slug" params={{ slug: item.slug }} className="phrasebank-category-card">
      <span className="phrasebank-card-title">{item.title}</span><span className="phrasebank-count" title={`${item.entry_count} ${item.entry_count === 1 ? "item" : "items"}`}>{item.entry_count}</span>
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

function HighlightedText({ text, query }: { text: string; query: string }) {
  const terms = [...new Set(query.trim().split(/\s+/).filter(Boolean))];
  if (!terms.length) return text;
  const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const termSet = new Set(terms.map((term) => term.toLocaleLowerCase()));
  const matcher = new RegExp(`(${terms.map(escapeRegExp).join("|")})`, "gi");
  return <>{text.split(matcher).map((part, index) => termSet.has(part.toLocaleLowerCase())
    ? <mark className="phrasebank-match" key={index}>{part}</mark>
    : part)}</>;
}

type SearchEntry = NonNullable<Awaited<ReturnType<typeof phrasebankSources.search>>>["results"][number]["entry"];

function SearchResultEntry({ entry, query, slug, headingPosition }: {
  entry: SearchEntry;
  query: string;
  slug: string;
  headingPosition: string;
}) {
  const navigate = useNavigate();
  const targetId = `heading-${slug}-${headingPosition}`;
  const openHeading = <Link to="/phrasebank/$slug" params={{ slug }} hash={targetId} onClick={(event) => {
    event.preventDefault();
    void navigate({ to: "/phrasebank/$slug", params: { slug }, hash: targetId }).then(() => scrollAfterNavigation(targetId));
  }}>Open heading</Link>;
  if (entry.kind === "phrase" && entry.cells?.length) {
    return <div className="phrasebank-search-phrase">
      <div className="phrasebank-table-wrap phrasebank-search-table-wrap"><table className="phrasebank-table phrasebank-search-table"><caption>Phrase pattern row</caption><tbody><tr>
        {entry.cells.map((alternatives, cellIndex) => <td key={cellIndex}>{alternatives.map((text, alternativeIndex) =>
          <div key={alternativeIndex}><HighlightedText text={text} query={query} /></div>)}</td>)}
      </tr></tbody></table></div>
      {openHeading}
    </div>;
  }
  return null;
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

function taxonomyIntents(taxonomy?: TaxonomyTree) {
  return (taxonomy?.sections ?? []).flatMap((section) => section.moves.flatMap((move) => move.steps.flatMap((step) => step.intents)));
}

function SourceFilters({ taxonomy, sectionCode, intentCode, onSectionChange, onIntentChange }: {
  taxonomy?: TaxonomyTree;
  sectionCode: string;
  intentCode: string;
  onSectionChange: (value: string) => void;
  onIntentChange: (value: string) => void;
}) {
  return <div className="phrasebank-taxonomy-filters">
    <label>Section<select aria-label="Section filter" value={sectionCode} onChange={(event) => onSectionChange(event.target.value)}>
      <option value="">All sections</option>{taxonomy?.sections.map((section) => <option key={section.code} value={section.code}>{section.name}</option>)}
    </select></label>
    <label>Intent<select aria-label="Intent filter" value={intentCode} onChange={(event) => onIntentChange(event.target.value)}>
      <option value="">All intents</option>{taxonomyIntents(taxonomy).map((intent) => <option key={intent.code} value={intent.code}>{intent.name}</option>)}
    </select></label>
  </div>;
}

function taxonomyUnmappedCount(categories: ManchesterCategory[], intentCode: string, results?: ManchesterSearchResult[]) {
  if (results) return results.filter((result) => intentCode ? !result.intent_code : !result.section_code).length;
  const field = intentCode ? "unmapped_intent_entry_count" : "unmapped_section_entry_count";
  return categories.reduce((total, category) => total + category[field], 0);
}

function EntryList({ entries }: { entries: NonNullable<NonNullable<Awaited<ReturnType<typeof phrasebankSources.category>>>["headings"][number]["entries"]> }) {
  const blocks: { id: string; entries: typeof entries }[] = [];
  for (const entry of entries) {
    if (entry.kind === "phrase") {
      const previous = blocks.at(-1);
      if (previous?.id === String(entry.block_index)) previous.entries.push(entry);
      else blocks.push({ id: String(entry.block_index), entries: [entry] });
    }
  }
  return <div className="phrasebank-entry-list">
    {blocks.map((block) => <div className="phrasebank-table-wrap" key={`table-${block.id}`}><table className="phrasebank-table"><caption>Phrase pattern row with alternatives</caption><tbody>
        {block.entries.map((entry) => <PhraseRow key={entry.id} cells={entry.cells ?? []} />)}
      </tbody></table></div>)}
  </div>;
}

function PatternGroups({ patterns, query = "" }: { patterns: PatternDetail[]; query?: string }) {
  const filtered = patterns.filter((pattern) => !query || `${pattern.canonical_frame ?? ""} ${pattern.intent_code} ${pattern.allowed_sections.join(" ")}`.toLowerCase().includes(query.toLowerCase()));
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
          <p><Link to="/phrasebank/pattern/$id" params={{ id: pattern.id }}>{pattern.canonical_frame}</Link> <Link to="/writer" className="btn btn-ghost btn-sm">Use in Writer</Link></p>
        </li>)}
      </ul>
    </section>)}
  </div>;
}

export function PhrasebankHome() {
  const [source, setSource] = useState<"all" | SourceId>("all");
  const [search, setSearch] = useState("");
  const [sectionCode, setSectionCode] = useState("");
  const [intentCode, setIntentCode] = useState("");
  const query = useDebounced(search.trim());
  const taxonomy = useQuery({ queryKey: ["phrasebank-taxonomy"], queryFn: phrasebankSources.taxonomy, retry: false });
  const manchester = useQuery({ queryKey: ["phrasebank-categories"], queryFn: PHRASEBANK_SOURCES["manchester-reference"].listGroups, retry: false });
  const patterns = useQuery({ queryKey: ["phrasebank-patterns"], queryFn: PHRASEBANK_SOURCES["aprkb-patterns"].listGroups, enabled: source !== "manchester-reference", retry: false });
  const results = useQuery({ queryKey: ["phrasebank-search", query], queryFn: () => PHRASEBANK_SOURCES["manchester-reference"].search(query), enabled: Boolean(query) && source !== "aprkb-patterns", retry: false });
  const disabled = isReferenceDisabled(manchester.error);
  const filters = { sectionCode: sectionCode || undefined, intentCode: intentCode || undefined };
  const patternSearch = useQuery({
    queryKey: ["phrasebank-pattern-search", query, sectionCode, intentCode],
    queryFn: () => PHRASEBANK_SOURCES["aprkb-patterns"].search(query, filters, patterns.data ?? []),
    enabled: source !== "manchester-reference" && patterns.data !== undefined,
    retry: false,
  });
  const patternMatches = query ? patternSearch.data ?? [] : (patterns.data ?? []).filter((pattern) =>
    (!sectionCode || PHRASEBANK_SOURCES["aprkb-patterns"].filterBySection(pattern, sectionCode, taxonomy.data as TaxonomyTree))
    && (!intentCode || PHRASEBANK_SOURCES["aprkb-patterns"].filterByIntent(pattern, intentCode)));
  const referenceSource = PHRASEBANK_SOURCES["manchester-reference"];
  const visibleCategories = (manchester.data ?? []).filter((category) =>
    (!sectionCode || Boolean(taxonomy.data && referenceSource.filterBySection(category, sectionCode, taxonomy.data)))
    && (!intentCode || referenceSource.filterByIntent(category, intentCode)));
  const visibleResults = (results.data ?? []).filter((item) =>
    item.entry.kind === "phrase" && (!sectionCode || Boolean(taxonomy.data && referenceSource.filterBySection(item, sectionCode, taxonomy.data)))
    && (!intentCode || referenceSource.filterByIntent(item, intentCode)));
  const hasFilters = Boolean(sectionCode || intentCode);
  const unmapped = query
    ? results.data ? taxonomyUnmappedCount([], intentCode, results.data.filter((item) => item.entry.kind === "phrase")) : 0
    : taxonomyUnmappedCount(manchester.data ?? [], intentCode);

  return <div className="stack phrasebank-home">
    <PageHeader title="Phrasebank" />
    <Card title="Search the phrasebank">
      <div className="phrasebank-search-controls">
        <input type="search" aria-label="Search phrasebanks" placeholder="Search phrases and categories" value={search} onChange={(event) => setSearch(event.target.value)} />
        <select aria-label="Source filter" value={source} onChange={(event) => setSource(event.target.value as "all" | SourceId)}>
          <option value="all">All sources</option><option value="manchester-reference">Manchester reference</option><option value="aprkb-patterns">AP-RKB patterns</option>
        </select>
        <SourceFilters taxonomy={taxonomy.data} sectionCode={sectionCode} intentCode={intentCode} onSectionChange={setSectionCode} onIntentChange={setIntentCode} />
      </div>
    </Card>
    {hasFilters && source !== "aprkb-patterns" && manchester.data && (!query || results.data) && <p className="phrasebank-filter-note" role="status">
      {unmapped} {query ? "matching items" : "items"} have no mapping for this filter and are hidden.
    </p>}
    {query ? <>
      <Card title="Search results">
        {source !== "aprkb-patterns" && (results.isPending ? <Loading /> : disabled ? <p role="status">Manchester reference is disabled. Enable `REFERENCE_LIBRARY_ENABLED` to browse it.</p> : visibleResults.length === 0 ? <Empty>No Manchester reference results.</Empty> : <section className="stack"><h3>Manchester reference</h3>
          {groupBy(visibleResults, (item) => item.category_slug).map(([slug, items]) => <section key={slug}>
            <h4>{items?.[0]?.category_title}</h4>
            {groupBy(items ?? [], (item) => String(item.entry.heading_position)).map(([position, group]) => <div key={position}>
              <h5>{group[0]?.heading}</h5>
              {group.map((item) => <SearchResultEntry key={item.entry.id} entry={item.entry} query={query} slug={slug} headingPosition={position} />)}
            </div>)}
          </section>)}
        </section>)}
        {source !== "manchester-reference" && <section><h3>AP-RKB patterns</h3><PatternGroups patterns={patternMatches} query={query} /></section>}
      </Card>
    </> : <>
      {source !== "aprkb-patterns" && <Card title="Sections">
        {disabled ? <p role="status">Manchester reference is disabled. Enable `REFERENCE_LIBRARY_ENABLED` to browse these categories.</p> : manchester.isPending ? <Loading /> : <CategoryCards categories={visibleCategories} kind="section" />}
      </Card>}
      {source !== "aprkb-patterns" && <Card title="General functions">
        {disabled ? <Empty>Manchester general functions are unavailable while the reference API is disabled.</Empty> : manchester.isPending ? <Loading /> : <CategoryCards categories={visibleCategories} kind="function" />}
      </Card>}
      {source !== "manchester-reference" && <Card title={<Link to="/phrasebank/$slug" params={{ slug: "aprkb-patterns" }}>AP-RKB patterns</Link>}>
        {patterns.isPending ? <Loading /> : <PatternGroups patterns={patternMatches} />}
      </Card>}
    </>}
    <SourceCredit />
  </div>;
}

export function PhrasebankCategory({ slug }: { slug: string }) {
  const navigate = useNavigate();
  const locationHref = useRouterState({ select: (state) => state.location.href });
  const manchester = useQuery({ queryKey: ["phrasebank-category", slug], queryFn: () => PHRASEBANK_SOURCES["manchester-reference"].getGroup(slug), enabled: slug !== "aprkb-patterns", retry: false });
  const patterns = useQuery({ queryKey: ["phrasebank-patterns"], queryFn: () => PHRASEBANK_SOURCES["aprkb-patterns"].getGroup("aprkb-patterns"), enabled: slug === "aprkb-patterns", retry: false });
  const disabled = isReferenceDisabled(manchester.error);
  useEffect(() => {
    const hash = new URL(locationHref, window.location.origin).hash;
    if (!hash || (slug === "aprkb-patterns" && patterns.isPending)) return;
    const targetId = decodeURIComponent(hash.slice(1));
    window.setTimeout(() => scrollToHeading(targetId), 250);
  }, [locationHref, slug, manchester.data, patterns.data, patterns.isPending]);
  if (slug === "aprkb-patterns") return <div className="stack">
    <p><Link to="/phrasebank">← Phrasebank home</Link></p>
    <PageHeader title="Approved AP-RKB patterns" />
    {patterns.isPending ? <Loading /> : <PatternGroups patterns={patterns.data ?? []} />}
    <SourceCredit />
  </div>;
  if (disabled) return <div className="stack"><p><Link to="/phrasebank">← Phrasebank home</Link></p><p role="status">Manchester reference is disabled. Enable `REFERENCE_LIBRARY_ENABLED` to browse this category.</p><SourceCredit /></div>;
  if (manchester.isPending) return <div className="stack"><Loading /><SourceCredit /></div>;
  const category = manchester.data;
  if (manchester.isError) return <div className="stack"><Empty>{manchester.error instanceof ApiError && manchester.error.status === 404 ? "Category not found or reference data has not been imported." : "The reference category could not be loaded."}</Empty><SourceCredit /></div>;
  if (!category) return <div className="stack"><Empty>Category not found.</Empty><SourceCredit /></div>;
  const intro = category.headings[0];
  const sections = category.headings.slice(1);
  return <div className="stack">
    <p><Link to="/phrasebank">← Phrasebank home</Link></p>
    <PageHeader title={category.category.title} />
    {intro?.entries.some((entry) => entry.kind === "phrase") && <section id={`heading-${category.category.slug}-${intro.heading_position}`} className="phrasebank-intro"><EntryList entries={intro.entries} /></section>}
    <nav className="phrasebank-index" aria-label="In-page headings"><strong>On this page</strong><div>{sections.map((item) => {
      const targetId = `heading-${category.category.slug}-${item.heading_position}`;
      return <Link key={item.heading_position} to="/phrasebank/$slug" params={{ slug: category.category.slug }} hash={targetId} onClick={(event) => { event.preventDefault(); void navigate({ to: "/phrasebank/$slug", params: { slug: category.category.slug }, hash: targetId }).then(() => scrollAfterNavigation(targetId)); }}>{item.heading}</Link>;
    })}</div></nav>
    {sections.map((item) => <section className="phrasebank-section" id={`heading-${category.category.slug}-${item.heading_position}`} key={item.heading_position}>
      <h2>{item.heading}</h2><EntryList entries={item.entries} />
    </section>)}
    <SourceCredit />
  </div>;
}

export function PhrasebankPatternDetail({ id }: { id: string }) {
  const pattern = useQuery({
    queryKey: ["phrasebank-pattern", id],
    queryFn: () => phrasebankSources.pattern(id),
    retry: false,
  });
  if (pattern.isPending) return <Loading />;
  if (pattern.isError || !pattern.data) return <Empty>Pattern detail is unavailable.</Empty>;
  const item = pattern.data;
  const list = (values: string[]) => values.length ? values.join(", ") : "—";
  return <div className="stack">
    <p><Link to="/phrasebank/$slug" params={{ slug: "aprkb-patterns" }}>← AP-RKB patterns</Link></p>
    <PageHeader title={item.intent_name || item.intent_code} />
    <Card title="Frame"><p>{item.canonical_frame}</p></Card>
    <Card title="Slots">
      {Object.entries(item.slots ?? {}).length ? <dl>{Object.entries(item.slots ?? {}).map(([name, slot]) => {
        const metadata = typeof slot === "string" ? { type: slot, label: null, instruction: null, example: null, required: true } : slot;
        return <div key={name}><dt>{name}</dt><dd>Type: {metadata.type}; Label: {metadata.label ?? "—"}; Instruction: {metadata.instruction ?? "—"}; Example: {metadata.example ?? "—"}; Required: {metadata.required ? "Yes" : "No"}</dd></div>;
      })}</dl> : <p>—</p>}
    </Card>
    <Card title="Variants">{item.variants.length ? <ul>{item.variants.map((variant, index) => <li key={`${index}-${variant.text}`}>{variant.text} {variant.register && <small>({variant.register})</small>}</li>)}</ul> : <p>—</p>}</Card>
    <Card title="Usage"><dl>
      <dt>Minimum evidence</dt><dd>{item.evidence_min ?? "—"}</dd>
      <dt>Forbidden contexts</dt><dd>{list(item.forbidden_contexts)}</dd>
      <dt>Allowed sections</dt><dd>{list(item.allowed_sections)}</dd>
      <dt>Allowed genres</dt><dd>{list(item.allowed_genres)}</dd>
    </dl></Card>
    <Card title="Evidence"><dl>
      <dt>Strength</dt><dd>{item.epistemic_strength ?? "Not labelled"}</dd>
      <dt>Claim type</dt><dd>{item.claim_type ?? "Not labelled"}</dd>
    </dl></Card>
    <Card title="Provenance"><dl>
      <dt>Source type</dt><dd>{item.source_type}</dd>
      <dt>License</dt><dd>{item.license_name ?? "—"}{item.license_code ? ` (${item.license_code})` : ""}</dd>
      <dt>Allows display</dt><dd>{item.license_allows_display ? "Yes" : "No"}</dd>
      <dt>Internal use</dt><dd>{item.license_flag ? "Yes" : "No"}</dd>
      <dt>Article reference</dt><dd>{item.source_reference ?? "—"}</dd>
      <dt>Article ID</dt><dd>{item.article_id ?? "—"}</dd>
      <dt>Source sentences</dt><dd>{item.source_sentence_count}</dd>
    </dl></Card>
    <p>Version {item.version_no} · <Link to="/writer">Use in Writer</Link></p>
  </div>;
}
