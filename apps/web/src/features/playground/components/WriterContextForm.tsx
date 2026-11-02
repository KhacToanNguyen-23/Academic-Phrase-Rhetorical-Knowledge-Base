import { Card, Field } from "@/shared/ui";
import type { Journal, Option, Taxonomy } from "../live/api";

export type WriterContext = {
  section: string;
  intent: string;
  genre: string;
  claimType: string;
  evidenceLevel: string;
  query: string;
  journalId: string;
};

export const blankContext: WriterContext = {
  section: "", intent: "", genre: "", claimType: "", evidenceLevel: "", query: "", journalId: "",
};

export function WriterContextForm({
  context, taxonomy, options, journals, searching, onChange, onSearch,
}: {
  context: WriterContext;
  taxonomy: Taxonomy;
  options: Option[];
  journals: Journal[];
  searching: boolean;
  onChange: (next: WriterContext) => void;
  onSearch: () => void;
}) {
  // FR-07.1: combine section, intent, genre, claim/evidence, journal and query in one recommendation context.
  const sections = taxonomy.sections.filter(
    (item) => !context.genre || item.compatible_genres.includes(context.genre),
  );
  const section = sections.find((item) => item.code === context.section);
  const intentSections = section ? [section] : sections;
  const intents = intentSections.flatMap((item) =>
    item.moves.flatMap((move) => move.steps.flatMap((step) => step.intents)),
  );

  return <Card title="1. Writing context">
    <form onSubmit={(event) => { event.preventDefault(); onSearch(); }}>
      <div className="slot-grid">
        <Field label="Article genre">
          <select value={context.genre} onChange={(event) => onChange({ ...context, genre: event.target.value, section: "", intent: "" })}>
            <option value="">Any genre</option>
            {taxonomy.article_genres.map((item) => <option key={item.code} value={item.code}>{item.name}</option>)}
          </select>
        </Field>
        <Field label="Manuscript section">
          <select value={context.section} onChange={(event) => onChange({ ...context, section: event.target.value, intent: "" })}>
            <option value="">Any section</option>
            {sections.map((item) => <option key={item.code} value={item.code}>{item.name}</option>)}
          </select>
        </Field>
        <Field label="Rhetorical intent">
          <select value={context.intent} onChange={(event) => onChange({ ...context, intent: event.target.value })}>
            <option value="">Any intent</option>
            {intents.map((item) => <option key={item.code} value={item.code}>{item.name}</option>)}
          </select>
        </Field>
        <Field label="Claim type">
          <select value={context.claimType} onChange={(event) => onChange({ ...context, claimType: event.target.value })}>
            <option value="">Any claim type</option>
            {options.filter((item) => item.group === "claim_type").map((item) => <option key={item.code} value={item.code}>{item.label}</option>)}
          </select>
        </Field>
        <Field label="Evidence level">
          <select value={context.evidenceLevel} onChange={(event) => onChange({ ...context, evidenceLevel: event.target.value })}>
            <option value="">Any evidence level</option>
            {options.filter((item) => item.group === "evidence_level").map((item) => <option key={item.code} value={item.code}>{item.label}</option>)}
          </select>
        </Field>
        <Field label="Target journal (optional)">
          <select value={context.journalId} onChange={(event) => onChange({ ...context, journalId: event.target.value })}>
            <option value="">No journal selected</option>
            {journals.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
        </Field>
        <Field label="Search keywords (optional)">
          <input maxLength={500} value={context.query} onChange={(event) => onChange({ ...context, query: event.target.value })} />
        </Field>
      </div>
      <button className="btn btn-primary" type="submit" disabled={searching}>Find patterns</button>
    </form>
  </Card>;
}
