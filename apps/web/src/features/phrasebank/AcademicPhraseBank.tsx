import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { SlidersHorizontal, X } from "lucide-react";

import { DataState } from "@/components/domain/DataState";
import { PageHeader } from "@/components/domain/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { AcademicPhraseFilter, AcademicPhrase as AcademicPhraseType, DomainOption, FunctionOption, PragmaticFeatureOption, phrasebankSources } from "./source-registry";
import { MeasurementPatternContext } from "@/features/measurement";

export type APBFacetSelection = { code: string; version: string };
export type APBFilterState = {
  function?: APBFacetSelection;
  stance?: APBFacetSelection;
  register?: APBFacetSelection;
  domain?: APBFacetSelection;
};
type FilterProps = {
  sectionCode: string;
  sectionLabel: string;
  filters: APBFilterState;
  intentCode?: string;
  intentLabel?: string;
  onSectionClear: () => void;
  onIntentClear?: () => void;
  onFilterChange: (facet: keyof APBFilterState, value?: APBFacetSelection) => void;
  visible: boolean;
};
type ResultProps = { q: string; sectionCode: string; filters: APBFilterState };
type SelectOption = { code: string; label: string; version: string };
type StringRecord = Record<string, unknown>;

function stringValue(record: StringRecord, key: string): string | undefined {
  const value = record[key];
  return typeof value === "string" ? value : undefined;
}

function optionKey(option: APBFacetSelection) {
  return `${option.code}::${option.version}`;
}

function optionValue(options: SelectOption[], key: string) {
  return options.find((option) => optionKey(option) === key);
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
  ariaLabel,
}: {
  label: string;
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  ariaLabel: string;
}) {
  return (
    <label className="flex min-w-0 flex-col gap-1 text-xs font-medium text-muted-foreground">
      {label}
      <Select value={value || "all"} onValueChange={(next) => onChange(next === "all" ? "" : next)}>
        <SelectTrigger aria-label={ariaLabel} className="w-full text-foreground">
          <SelectValue placeholder={label === "Communicative function" ? "All functions" : `All ${label.toLowerCase()}s`} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">{label === "Communicative function" ? "All functions" : `All ${label.toLowerCase()}s`}</SelectItem>
          {options.map((option) => (
            <SelectItem key={optionKey(option)} value={optionKey(option)}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </label>
  );
}

function functionOptions(options: FunctionOption[]): SelectOption[] {
  return options.map(({ code, label, version, family_label }) => ({
    code,
    label: `${family_label} / ${label}`,
    version,
  }));
}

function featureOptions(options: PragmaticFeatureOption[], facet: "register" | "stance_type"): SelectOption[] {
  return options.filter((option) => option.facet === facet).map(({ code, label, version }) => ({ code, label, version }));
}

function domainOptions(options: DomainOption[]): SelectOption[] {
  return options.map(({ code, label, version }) => ({ code, label, version }));
}

function optionForSelection(options: SelectOption[], selection?: APBFacetSelection) {
  return selection ? options.find((option) => optionKey(option) === `${selection.code}::${selection.version}`) : undefined;
}

function selectionForKey(options: SelectOption[], key: string): APBFacetSelection | undefined {
  const option = optionValue(options, key);
  return option ? { code: option.code, version: option.version } : undefined;
}

function functionsFor(item: AcademicPhraseType) {
  return (item.communicative_functions ?? []).flatMap((record) => {
    const label = stringValue(record, "label");
    return label ? [label] : [];
  });
}

function fieldList(items: StringRecord[] | undefined, field: string) {
  return (items ?? []).flatMap((item) => {
    const value = stringValue(item, field);
    return value ? [value] : [];
  });
}

function ActiveFilter({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-secondary px-2.5 py-1 text-xs font-medium text-secondary-foreground">
      {label}
      <button type="button" onClick={onRemove} aria-label={`Remove ${label} filter`} className="rounded-full hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
        <X aria-hidden="true" className="size-3" />
      </button>
    </span>
  );
}

export function AcademicPhraseBankFilters({
  sectionCode,
  sectionLabel,
  intentCode,
  intentLabel,
  filters,
  onSectionClear,
  onIntentClear,
  onFilterChange,
  visible,
}: FilterProps) {
  const functions = useQuery({
    queryKey: ["academic-phrase-functions"],
    queryFn: phrasebankSources.academicFunctions,
    enabled: visible,
    retry: false,
  });
  const features = useQuery({
    queryKey: ["academic-phrase-pragmatic-features"],
    queryFn: phrasebankSources.academicPragmaticFeatures,
    enabled: visible,
    retry: false,
  });
  const domains = useQuery({
    queryKey: ["academic-phrase-domains"],
    queryFn: phrasebankSources.academicDomains,
    enabled: visible,
    retry: false,
  });
  const functionChoices = functionOptions(functions.data ?? []);
  const stanceChoices = featureOptions(features.data ?? [], "stance_type");
  const registerChoices = featureOptions(features.data ?? [], "register");
  const domainChoices = domainOptions(domains.data ?? []);
  const selectedFunction = optionForSelection(functionChoices, filters.function);
  const selectedStance = optionForSelection(stanceChoices, filters.stance);
  const selectedRegister = optionForSelection(registerChoices, filters.register);
  const selectedDomain = optionForSelection(domainChoices, filters.domain);
  const update = (facet: keyof APBFilterState, choices: SelectOption[], key: string) => {
    onFilterChange(facet, selectionForKey(choices, key));
  };
  const advancedCount = [filters.stance, filters.register, filters.domain].filter(Boolean).length;
  const active = Boolean(sectionCode || intentCode || filters.function || filters.stance || filters.register || filters.domain);
  const clear = () => {
    onFilterChange("function");
    onFilterChange("stance");
    onFilterChange("register");
    onFilterChange("domain");
    onSectionClear();
    onIntentClear?.();
  };
  const advancedFilters = (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {features.isPending ? (
        <DataState state="loading" loadingLabel="Loading stance options" />
      ) : features.isError ? (
        <DataState state="error" errorTitle="Stance filters unavailable" errorDescription={features.error.message} onRetry={() => void features.refetch()} />
      ) : (
        <FilterSelect label="Stance" ariaLabel="APB stance filter" value={filters.stance ? optionKey(filters.stance) : ""} options={stanceChoices} onChange={(key) => update("stance", stanceChoices, key)} />
      )}
      {!features.isError && !features.isPending ? (
        <FilterSelect label="Register" ariaLabel="APB register filter" value={filters.register ? optionKey(filters.register) : ""} options={registerChoices} onChange={(key) => update("register", registerChoices, key)} />
      ) : null}
      {domains.isPending ? (
        <DataState state="loading" loadingLabel="Loading domain options" />
      ) : domains.isError ? (
        <DataState state="error" errorTitle="Domain filters unavailable" errorDescription={domains.error.message} onRetry={() => void domains.refetch()} />
      ) : (
        <FilterSelect label="Domain" ariaLabel="APB domain filter" value={filters.domain ? optionKey(filters.domain) : ""} options={domainChoices} onChange={(key) => update("domain", domainChoices, key)} />
      )}
    </div>
  );

  return (
    <div className="flex flex-col gap-3 border-t border-border pt-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        {functions.isPending ? (
          <DataState state="loading" loadingLabel="Loading communicative function options" />
        ) : functions.isError ? (
          <DataState state="error" errorTitle="Function filters unavailable" errorDescription={functions.error.message} onRetry={() => void functions.refetch()} />
        ) : (
          <div className="w-full min-w-0 sm:max-w-md sm:flex-1">
            <FilterSelect label="Communicative function" ariaLabel="APB function filter" value={filters.function ? optionKey(filters.function) : ""} options={functionChoices} onChange={(key) => update("function", functionChoices, key)} />
          </div>
        )}
        <div className="hidden sm:block">
          <Popover>
            <PopoverTrigger asChild>
              <Button variant="outline" className="gap-2"><SlidersHorizontal aria-hidden="true" className="size-4" />More filters{advancedCount ? " (" + advancedCount + ")" : ""}</Button>
            </PopoverTrigger>
            <PopoverContent align="start" className="w-[min(30rem,calc(100vw-2rem))] p-4">
              <div className="mb-3"><p className="font-medium">More filters</p><p className="text-xs text-muted-foreground">Stance, register, and domain</p></div>
              {advancedFilters}
            </PopoverContent>
          </Popover>
        </div>
        <div className="sm:hidden">
          <Sheet>
            <SheetTrigger asChild><Button variant="outline" className="gap-2"><SlidersHorizontal aria-hidden="true" className="size-4" />More filters{advancedCount ? " (" + advancedCount + ")" : ""}</Button></SheetTrigger>
            <SheetContent side="bottom" className="max-h-[85vh] overflow-y-auto rounded-t-2xl p-4">
              <SheetHeader className="p-0"><SheetTitle>More filters</SheetTitle><SheetDescription>Stance, register, and domain</SheetDescription></SheetHeader>
              {advancedFilters}
              <Button className="w-full" variant="outline" onClick={clear}>Clear filters</Button>
            </SheetContent>
          </Sheet>
        </div>
      </div>
      {active ? (
        <div className="flex flex-wrap items-center gap-2" role="status" aria-label="Active APB filters">
          {sectionCode ? <ActiveFilter label={"Section: " + sectionLabel} onRemove={onSectionClear} /> : null}
          {intentCode ? <ActiveFilter label={"Intent: " + intentLabel} onRemove={() => onIntentClear?.()} /> : null}
          {selectedFunction ? <ActiveFilter label={"Function: " + selectedFunction.label} onRemove={() => onFilterChange("function")} /> : null}
          {selectedStance ? <ActiveFilter label={"Stance: " + selectedStance.label} onRemove={() => onFilterChange("stance")} /> : null}
          {selectedRegister ? <ActiveFilter label={"Register: " + selectedRegister.label} onRemove={() => onFilterChange("register")} /> : null}
          {selectedDomain ? <ActiveFilter label={"Domain: " + selectedDomain.label} onRemove={() => onFilterChange("domain")} /> : null}
          <Button variant="ghost" size="sm" className="ml-auto" onClick={clear}>Clear all</Button>
        </div>
      ) : null}
    </div>
  );
}

export function AcademicPhraseBankPanel({ q, sectionCode, filters }: ResultProps) {
  const filter: AcademicPhraseFilter = {
    q: q || undefined,
    sectionCode: sectionCode || undefined,
    functionCode: filters.function?.code,
    functionVersion: filters.function?.version,
    stanceCode: filters.stance?.code,
    stanceVersion: filters.stance?.version,
    registerCode: filters.register?.code,
    registerVersion: filters.register?.version,
    domainCode: filters.domain?.code,
    limit: 50,
    offset: 0,
  };
  const results = useQuery({
    queryKey: [
      "academic-phrase-search",
      q,
      sectionCode,
      filters.function?.code,
      filters.function?.version,
      filters.stance?.code,
      filters.stance?.version,
      filters.register?.code,
      filters.register?.version,
      filters.domain?.code,
      filters.domain?.version,
      0,
      50,
    ],
    queryFn: () => phrasebankSources.academicPhrases(filter),
    retry: false,
  });

  return (
    <section className="flex flex-col gap-4">
      <h3 className="text-lg font-semibold">Academic Phrase Bank</h3>
        {results.isPending ? (
          <DataState state="loading" loadingLabel="Loading Academic Phrase Bank templates" />
        ) : results.isError ? (
          <DataState state="error" errorTitle="Could not load Academic Phrase Bank" errorDescription={results.error.message} onRetry={() => void results.refetch()} />
        ) : (results.data?.items.length ?? 0) === 0 ? (
          <DataState
            state="empty"
            emptyTitle="No Academic Phrase Bank templates match"
            emptyDescription="Try another phrase or clear one or more APB filters. Results are limited to phrases visible to your account."
          />
        ) : (
          <>
            <p className="text-sm text-muted-foreground" role="status">
              Showing {results.data?.items.length ?? 0} of {results.data?.total ?? 0} matching APB templates.
              {results.data && results.data.total > results.data.items.length ? " Refine filters to narrow the remaining matches." : ""}
            </p>
            <ul className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {results.data?.items.map((item) => <AcademicPhraseCard key={item.id} item={item} />)}
            </ul>
          </>
        )}
    </section>
  );
}
function AcademicPhraseCard({ item }: { item: AcademicPhraseType }) {
  const functions = functionsFor(item);
  const sections = [...new Set([...(item.allowed_sections ?? []), ...(item.usage_profiles ?? []).flatMap((profile) => profile.section_code ? [profile.section_code] : [])])];
  const pragmaticLabels = fieldList(item.pragmatic_tags ?? [], "label").slice(0, 3);
  return (
    <li>
      <Link
        to="/phrasebank/apb/$id"
        params={{ id: item.id }}
        className="flex h-full flex-col gap-3 rounded-[var(--radius-panel)] border border-border p-4 transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
      >
        <div className="flex items-start justify-between gap-3">
          <span className="font-medium">{functions.join(", ") || item.intent_name || "Unmapped function"}</span>
        </div>
        <p className="font-serif text-lg leading-7">{item.canonical_frame ?? "Phrase frame unavailable"}</p>
        <div className="flex flex-wrap gap-1.5">
          {sections.map((section) => <Badge key={section} variant="secondary">{section}</Badge>)}
          {pragmaticLabels.map((tag) => <Badge key={tag} variant="outline">{tag}</Badge>)}
        </div>
      </Link>
    </li>
  );
}

function DetailField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-1 gap-1 border-b border-border py-3 text-sm last:border-0 sm:grid-cols-[minmax(8rem,12rem)_minmax(0,1fr)] sm:gap-4">
      <dt className="font-medium">{label}</dt>
      <dd className="flex min-w-0 flex-col gap-1">{children}</dd>
    </div>
  );
}

export function AcademicPhraseBankDetail({ id }: { id: string }) {
  const phrase = useQuery({
    queryKey: ["academic-phrase-detail", id],
    queryFn: () => phrasebankSources.academicPhrase(id),
    retry: false,
  });
  if (phrase.isPending) return <DataState state="loading" loadingLabel="Loading Academic Phrase Bank detail" />;
  if (phrase.isError || !phrase.data) {
    return <DataState state="error" errorTitle="Academic Phrase Bank detail is unavailable" errorDescription={phrase.error?.message ?? "The phrase could not be found."} onRetry={() => void phrase.refetch()} />;
  }
  return <AcademicPhraseDetail item={phrase.data} />;
}

function AcademicPhraseDetail({ item }: { item: AcademicPhraseType }) {
  const functions = item.communicative_functions ?? [];
  const moves = (item.move_links ?? []) as StringRecord[];
  const steps = (item.step_links ?? []) as StringRecord[];
  const examples = item.examples ?? [];
  const caveats = item.caveats ?? [];
  const pragmatic = item.pragmatic_tags ?? [];
  const slots = Object.entries(item.slots ?? {});
  const usageProfiles = item.usage_profiles ?? [];
  const title = functions.map((entry) => stringValue(entry, "label")).filter(Boolean).join(", ") || item.intent_name || item.intent_code;
  return (
    <div className="flex flex-col gap-6">
      <Link to="/phrasebank" className="text-sm text-primary hover:underline">â† Phrasebank</Link>
      <PageHeader title={<span className="text-3xl">{title}</span>} description={`Academic Phrase Bank Â· version ${item.version_no ?? "unknown"}`} />
      <Card>
        <CardHeader><CardTitle>Phrase frame</CardTitle></CardHeader>
        <CardContent>
          <p className="font-serif text-xl leading-8">{item.canonical_frame ?? "Phrase frame unavailable"}</p>
        </CardContent>
      </Card>
      <MeasurementPatternContext patternId={item.id} />
      <Card>
        <CardHeader><CardTitle>Taxonomy and applicability</CardTitle></CardHeader>
        <CardContent><dl>
          <DetailField label="Communicative function">
            {functions.length ? functions.map((entry, index) => (
              <span key={`${stringValue(entry, "code") ?? "function"}-${index}`}>
                {stringValue(entry, "label") ?? stringValue(entry, "code") ?? "Unresolved function"}
                {stringValue(entry, "family_label") ? ` Â· ${stringValue(entry, "family_label")}` : ""}
                {stringValue(entry, "purpose") ? ` Â· ${stringValue(entry, "purpose")}` : ""}
                {stringValue(entry, "status") === "proposed" ? " Â· Proposed taxonomy mapping" : ""}
              </span>
            )) : "No communicative function is linked."}
          </DetailField>
          <DetailField label="Rhetorical Intent">{item.intent_name} ({item.intent_code})</DetailField>
          <DetailField label="Move links">
            {moves.length ? moves.map((move) => `${stringValue(move, "section_code") ?? "?"} / ${stringValue(move, "label") ?? stringValue(move, "code") ?? "Unknown Move"} (${stringValue(move, "relation") ?? "linked"})`) : "No APB-specific Move link is recorded."}
          </DetailField>
          <DetailField label="Step links">
            {steps.length ? steps.map((step) => `${stringValue(step, "move_code") ?? "?"} / ${stringValue(step, "label") ?? stringValue(step, "code") ?? "Unknown Step"} (${stringValue(step, "relation") ?? "linked"})`) : "No APB-specific Step link is recorded."}
          </DetailField>
          <DetailField label="Usage profiles">
            {usageProfiles.length ? usageProfiles.map((profile, index) => (
              <span key={`${profile.section_code ?? "section"}-${index}`}>
                {[profile.section_label ?? profile.section_code, profile.genre_code, profile.language_code, profile.register_code, profile.discipline_code, profile.audience, profile.preferred_usage].filter(Boolean).join(" Â· ")}
              </span>
            )) : "No detailed usage profile is recorded."}
          </DetailField>
          <DetailField label="VTB Concept/Sense">Deferred; no stable VTB identifier is linked.</DetailField>
        </dl></CardContent>
      </Card>
      {slots.length ? <Card>
        <CardHeader><CardTitle>Typed slots</CardTitle></CardHeader>
        <CardContent><dl>
          {slots.map(([name, slot]) => {
            const details = typeof slot === "string"
              ? { type: slot, label: undefined, instruction: undefined, example: undefined, min_length: undefined, required: true }
              : slot;
            return <DetailField key={name} label={name}>
              {details.label ? <span>{details.label}</span> : null}
              <span>Type: {details.type}</span>
              {details.instruction ? <span>{details.instruction}</span> : null}
              {details.example ? <span>Example: {details.example}</span> : null}
              {details.min_length ? <span>Minimum length: {details.min_length}</span> : null}
              <Badge variant="outline">{details.required === false ? "Optional" : "Required"}</Badge>
            </DetailField>;
          })}
        </dl></CardContent>
      </Card> : null}
      {pragmatic.length ? <Card>
        <CardHeader><CardTitle>Pragmatic profile</CardTitle></CardHeader>
        <CardContent><ul className="flex flex-col gap-2">
          {pragmatic.map((tag) => <li key={`${tag.code}-${tag.version}`}>
            <Badge variant="outline">{tag.facet}</Badge> {tag.label} <span className="text-muted-foreground">v{tag.version}</span>
            {tag.strength_note ? <p>{tag.strength_note}</p> : null}
            {tag.context_note ? <p className="text-sm text-muted-foreground">{tag.context_note}</p> : null}
          </li>)}
        </ul></CardContent>
      </Card> : <Card><CardHeader><CardTitle>Pragmatic profile</CardTitle></CardHeader><CardContent>No pragmatic labels are recorded.</CardContent></Card>}
      {slots.length ? null : <p className="text-sm text-muted-foreground">This template has no typed slots recorded.</p>}
      <Card>
        <CardHeader><CardTitle>Examples</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-4">
          {(["positive", "negative", "revised"] as const).map((kind) => {
            const group = examples.filter((example) => example.kind === kind);
            if (!group.length) return null;
            return <section key={kind} className="flex flex-col gap-2">
              <h3 className="font-medium capitalize">{kind} examples</h3>
              {group.map((example, index) => <article key={`${kind}-${index}`} className="rounded-md border border-border p-3">
                <p className="font-serif leading-7">{example.text}</p>
                {example.explanation ? <p className="mt-1 text-sm text-muted-foreground">{example.explanation}</p> : null}
                <p className="mt-2 text-xs text-muted-foreground">
                  {example.origin_kind}{example.license_code ? ` Â· ${example.license_code}` : ""}{example.source_ref ? ` Â· ${example.source_ref}` : ""}{example.license_allows_display === true ? " Â· display permitted" : example.origin_kind === "licensed" ? " Â· display not confirmed" : ""}
                </p>
              </article>)}
            </section>;
          })}
          {!examples.length ? <p className="text-sm text-muted-foreground">No positive or negative examples are recorded.</p> : null}
        </CardContent>
      </Card>
      {caveats.length ? <Card>
        <CardHeader><CardTitle>Caveats</CardTitle></CardHeader>
        <CardContent><ul className="flex flex-col gap-2">
          {caveats.map((caveat) => <li key={caveat.code} className="rounded-md border border-border p-3">
            <Badge variant={caveat.severity === "critical" ? "destructive" : caveat.severity === "warning" ? "warning" : "outline"}>{caveat.severity}</Badge>
            <span className="ml-2">{caveat.message}</span>
          </li>)}
        </ul></CardContent>
      </Card> : <Card><CardHeader><CardTitle>Caveats</CardTitle></CardHeader><CardContent>No usage caveats are recorded.</CardContent></Card>}
      <Card>
        <CardHeader><CardTitle>Provenance and rights</CardTitle></CardHeader>
        <CardContent><dl>
          <DetailField label="Source type">{item.source_type}</DetailField>
          <DetailField label="License">{item.license_name ?? item.license_code ?? "No license metadata"}</DetailField>
          <DetailField label="Display permission">{item.license_allows_display ? "Permitted" : "Not confirmed"}</DetailField>
          {item.source_reference ? <DetailField label="Source reference">{item.source_reference}</DetailField> : null}
          <DetailField label="Taxonomy status">{item.status}</DetailField>
        </dl></CardContent>
      </Card>
    </div>
  );
}
