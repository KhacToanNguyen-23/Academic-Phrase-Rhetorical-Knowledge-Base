import { SelectField } from "@/components/domain";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
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
  section: "",
  intent: "",
  genre: "",
  claimType: "",
  evidenceLevel: "",
  query: "",
  journalId: "",
};

export function WriterContextForm({
  context,
  taxonomy,
  options,
  journals,
  supportingContext,
  searching,
  primary,
  onChange,
  onSupportingContextChange,
  onSearch,
}: {
  context: WriterContext;
  taxonomy: Taxonomy;
  options: Option[];
  journals: Journal[];
  supportingContext: string;
  searching: boolean;
  primary: boolean;
  onChange: (next: WriterContext) => void;
  onSupportingContextChange: (value: string) => void;
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
  const byGroup = (group: string) =>
    options.filter((item) => item.group === group).map((item) => ({ value: item.code, label: item.label }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Writing context</CardTitle>
        <CardDescription>
          Every field is optional. Selected fields narrow the patterns; an empty context lists every eligible one.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            onSearch();
          }}
        >
          <FieldGroup>
            <div className="grid grid-cols-3 gap-4">
              <SelectField
                id="writer-genre"
                label="Article genre"
                value={context.genre}
                anyLabel="Any genre"
                options={taxonomy.article_genres.map((item) => ({ value: item.code, label: item.name }))}
                onChange={(genre) => onChange({ ...context, genre, section: "", intent: "" })}
              />
              <SelectField
                id="writer-section"
                label="Manuscript section"
                value={context.section}
                anyLabel="Any section"
                options={sections.map((item) => ({ value: item.code, label: item.name }))}
                onChange={(next) => onChange({ ...context, section: next, intent: "" })}
              />
              <SelectField
                id="writer-intent"
                label="Rhetorical intent"
                value={context.intent}
                anyLabel="Any intent"
                options={intents.map((item) => ({ value: item.code, label: item.name }))}
                onChange={(intent) => onChange({ ...context, intent })}
              />
              <SelectField
                id="writer-claim"
                label="Claim type"
                value={context.claimType}
                anyLabel="Any claim type"
                options={byGroup("claim_type")}
                onChange={(claimType) => onChange({ ...context, claimType })}
              />
              <SelectField
                id="writer-evidence"
                label="Evidence level"
                value={context.evidenceLevel}
                anyLabel="Any evidence level"
                options={byGroup("evidence_level")}
                onChange={(evidenceLevel) => onChange({ ...context, evidenceLevel })}
              />
              <SelectField
                id="writer-journal"
                label="Target journal"
                value={context.journalId}
                anyLabel="No journal selected"
                options={journals.map((item) => ({ value: item.id, label: item.name }))}
                onChange={(journalId) => onChange({ ...context, journalId })}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Field>
                <FieldLabel htmlFor="writer-query">Search keywords</FieldLabel>
                <Input
                  id="writer-query"
                  maxLength={500}
                  value={context.query}
                  onChange={(event) => onChange({ ...context, query: event.target.value })}
                />
                <FieldDescription>Keywords narrow the search. They do not count as evidence.</FieldDescription>
              </Field>
              <Field>
                <FieldLabel htmlFor="writer-supporting">Supporting context</FieldLabel>
                <Textarea
                  id="writer-supporting"
                  rows={2}
                  maxLength={2000}
                  value={supportingContext}
                  onChange={(event) => onSupportingContextChange(event.target.value)}
                />
                <FieldDescription>
                  Facts, numbers, DOIs or citations entered here may support the V03 check.
                </FieldDescription>
              </Field>
            </div>
            <div>
              <Button type="submit" variant={primary ? "default" : "secondary"} disabled={searching}>
                {searching ? "Searching…" : "Find patterns"}
              </Button>
            </div>
          </FieldGroup>
        </form>
      </CardContent>
    </Card>
  );
}
