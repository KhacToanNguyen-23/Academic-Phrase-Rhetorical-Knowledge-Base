import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";

import { EvidenceLabel, PageHeader, PhraseFrame, SelectField, SeverityBadge } from "@/components/domain";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  api,
  type ClaimType,
  type EpistemicStrength,
  type FallbackTier,
  type Genre,
  type RecommendationRequest,
  type Section,
  type Violation,
} from "@/shared/api";
import { pct } from "@/shared/lib";

const SECTIONS: Section[] = ["Introduction", "Methods", "Results", "Discussion", "Conclusion"];
const GENRES: Genre[] = ["Original Research", "SLR", "Review"];
const CLAIMS: ClaimType[] = ["background", "gap", "method", "result", "implication", "limitation"];
const LEVELS = [
  { value: "low", label: "Low" },
  { value: "moderate", label: "Moderate" },
  { value: "high", label: "High" },
];
const TIERS: Record<FallbackTier, string> = {
  journal_genre: "Journal + genre",
  similar_journal: "Similar journal",
  subfield: "Subfield",
  field: "Field",
  generic: "Generic",
};
const plain = (items: string[]) => items.map((item) => ({ value: item, label: item }));

interface Ctx extends RecommendationRequest {
  claim_id: string;
  evidence_level: EpistemicStrength;
  evidence_ids: string;
}

export function PlaygroundPage({ patternId }: { patternId?: string }) {
  const intents = useQuery({ queryKey: ["intents"], queryFn: api.intents });
  const journals = useQuery({ queryKey: ["journals"], queryFn: api.journals });
  const preset = useQuery({
    queryKey: ["pattern", patternId],
    queryFn: () => api.pattern(patternId!),
    enabled: !!patternId,
  });

  const [ctx, setCtx] = useState<Ctx>({
    section: "Introduction",
    intent_id: "INT-GAP",
    genre: "Original Research",
    claim_id: "A3-C07",
    evidence_level: "moderate",
    evidence_ids: "A3-E12",
  });
  const set = (key: keyof Ctx, value: string) =>
    setCtx((c) => ({ ...c, [key]: key === "evidence_ids" || key === "claim_id" ? value : value || undefined }));

  // Opened from the Library: preset the context from the chosen pattern.
  useEffect(() => {
    if (preset.data) {
      setCtx((c) => ({
        ...c,
        section: preset.data!.section_scope[0],
        intent_id: preset.data!.intent_id,
        claim_type: preset.data!.claim_type,
      }));
    }
  }, [preset.data]);

  const recReq = {
    section: ctx.section,
    intent_id: ctx.intent_id,
    genre: ctx.genre,
    claim_type: ctx.claim_type,
    journal_id: ctx.journal_id,
    claim_id: ctx.claim_id,
    top_k: 3,
  };
  const rec = useMutation({ mutationFn: () => api.recommend(ctx) });
  const [picked, setPicked] = useState<string>();
  const [slots, setSlots] = useState<Record<string, string>>({});
  const candidate = rec.data?.candidates.find((c) => c.pattern.id === picked);

  const render = useMutation({
    mutationFn: () =>
      api.render({ pattern_id: candidate!.pattern.id, frame: candidate!.pattern.canonical_frame, slots }),
  });
  const validateReq = () => ({
    text: render.data?.text ?? "",
    evidence_level: ctx.evidence_level,
    evidence_ids: ctx.evidence_ids
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
    journal_id: ctx.journal_id,
    claim_id: ctx.claim_id,
  });
  const check = useMutation({ mutationFn: () => api.validate(validateReq()) });

  const { reset: resetRender } = render;
  const { reset: resetCheck } = check;
  useEffect(() => {
    resetRender();
    resetCheck();
  }, [picked, slots, resetRender, resetCheck]);
  useEffect(() => {
    const first = rec.data?.candidates.find((c) => c.pattern.id === patternId) ?? rec.data?.candidates[0];
    setPicked(first?.pattern.id);
    setSlots({});
  }, [rec.data, patternId]);

  // Only the button of the step in progress is the primary action.
  const stage = !rec.data ? "recommend" : !render.data ? "render" : !check.data ? "validate" : "done";

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Playground"
        description="Replay one Writing Engine call: recommend a frame, render it with the author's content, then
          validate. Each step shows the exact request and response."
      />
      <div className="grid grid-cols-[20rem_1fr] items-start gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Context sent by Writing</CardTitle>
          </CardHeader>
          <CardContent>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                rec.mutate();
              }}
            >
              <FieldGroup>
                <SelectField
                  id="pg-section"
                  label="Section"
                  value={ctx.section ?? ""}
                  options={plain(SECTIONS)}
                  onChange={(value) =>
                    setCtx((c) => ({ ...c, section: (value || undefined) as Section, intent_id: undefined }))
                  }
                />
                <SelectField
                  id="pg-intent"
                  label="Rhetorical intent"
                  value={ctx.intent_id ?? ""}
                  anyLabel="Any intent"
                  options={(intents.data ?? [])
                    .filter((i) => !ctx.section || i.sections.includes(ctx.section))
                    .map((i) => ({ value: i.intent_id, label: i.name }))}
                  onChange={(value) => set("intent_id", value)}
                />
                <SelectField
                  id="pg-claim-type"
                  label="Claim type"
                  value={ctx.claim_type ?? ""}
                  anyLabel="Any"
                  options={plain(CLAIMS)}
                  onChange={(value) => set("claim_type", value)}
                />
                <SelectField
                  id="pg-genre"
                  label="Genre"
                  value={ctx.genre ?? ""}
                  options={plain(GENRES)}
                  onChange={(value) => set("genre", value)}
                />
                <SelectField
                  id="pg-journal"
                  label="Target journal"
                  value={ctx.journal_id ?? ""}
                  anyLabel="Unspecified"
                  options={(journals.data ?? []).map((j) => ({ value: j.journal_id, label: j.title }))}
                  onChange={(value) => set("journal_id", value)}
                />
                <Field>
                  <FieldLabel htmlFor="pg-claim-id">claim_id</FieldLabel>
                  <Input id="pg-claim-id" value={ctx.claim_id} onChange={(e) => set("claim_id", e.target.value)} />
                  <FieldDescription>Passed through untouched for traceability (FR-09.2).</FieldDescription>
                </Field>
                <SelectField
                  id="pg-evidence"
                  label="Evidence level"
                  value={ctx.evidence_level}
                  options={LEVELS}
                  onChange={(value) => set("evidence_level", value)}
                />
                <Field>
                  <FieldLabel htmlFor="pg-evidence-ids">evidence_ids</FieldLabel>
                  <Input
                    id="pg-evidence-ids"
                    value={ctx.evidence_ids}
                    onChange={(e) => set("evidence_ids", e.target.value)}
                  />
                </Field>
                <Button
                  type="submit"
                  variant={stage === "recommend" ? "default" : "secondary"}
                  disabled={rec.isPending}
                >
                  {rec.isPending ? "Sending…" : "Send request"}
                </Button>
              </FieldGroup>
            </form>
          </CardContent>
        </Card>

        <div className="flex flex-col gap-6">
          <p className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground" aria-label="Context in use">
            Sending
            {[ctx.section, ctx.genre, ctx.claim_type, `${ctx.evidence_level} evidence`]
              .filter((item): item is string => Boolean(item))
              .map((item) => (
                <Badge key={item} variant="secondary">
                  {item}
                </Badge>
              ))}
          </p>
          <Step
            title="Recommend"
            endpoint="POST /v1/recommendations"
            done={!!rec.data}
            json={
              rec.data && (
                <>
                  <JsonBlock title="Request" value={recReq} />
                  <JsonBlock
                    title="Response"
                    value={{
                      request_id: rec.data.request_id,
                      fallback_tier: rec.data.fallback_tier,
                      gated_out: rec.data.gated_out,
                      candidates: rec.data.candidates.slice(0, 3).map((c) => ({
                        candidate_id: c.pattern.id,
                        rank: c.rank,
                        score: +c.score.toFixed(2),
                        frame: c.pattern.canonical_frame,
                      })),
                    }}
                  />
                </>
              )
            }
          >
            {!rec.data ? (
              <Waiting>Set the context and send a request.</Waiting>
            ) : (
              <>
                <Alert role="status">
                  <AlertDescription>
                    <strong className="font-medium">
                      Fallback tier: {TIERS[rec.data.fallback_tier] ?? rec.data.fallback_tier}.
                    </strong>
                    {rec.data.fallback_reason && ` ${rec.data.fallback_reason}`}
                  </AlertDescription>
                </Alert>
                <RadioGroup value={picked ?? ""} onValueChange={setPicked} aria-label="Candidates">
                  {rec.data.candidates.slice(0, 3).map((c) => (
                    <label
                      key={c.pattern.id}
                      className="flex cursor-pointer items-start gap-3 rounded-[var(--radius)] p-3 hover:bg-muted
                        has-data-[state=checked]:bg-muted"
                    >
                      <RadioGroupItem value={c.pattern.id} className="mt-1.5" />
                      <span className="flex flex-col gap-1">
                        <PhraseFrame frame={c.pattern.canonical_frame} className="text-[18px]" />
                        <span className="text-sm text-muted-foreground">
                          {c.rank}. {c.pattern.id} · score {pct(c.score)}
                        </span>
                      </span>
                    </label>
                  ))}
                </RadioGroup>
              </>
            )}
          </Step>

          <Step
            title="Render"
            endpoint="POST /v1/render"
            done={!!render.data}
            json={
              render.data &&
              candidate && (
                <>
                  <JsonBlock
                    title="Request"
                    value={{ pattern_id: candidate.pattern.id, slots, claim_id: ctx.claim_id }}
                  />
                  <JsonBlock title="Response" value={render.data} />
                </>
              )
            }
            action={
              candidate && (
                <Button
                  variant={stage === "render" ? "default" : "secondary"}
                  disabled={render.isPending}
                  onClick={() => render.mutate()}
                >
                  Render sentence
                </Button>
              )
            }
          >
            {!candidate ? (
              <Waiting>Waiting for a candidate from the recommendation.</Waiting>
            ) : (
              <>
                <FieldGroup>
                  <div className="grid grid-cols-2 gap-4">
                    {candidate.pattern.slots_schema.map((s) => (
                      <Field key={s.name}>
                        <FieldLabel htmlFor={`pg-slot-${s.name}`}>{`{${s.name}}${s.required ? " *" : ""}`}</FieldLabel>
                        <Input
                          id={`pg-slot-${s.name}`}
                          value={slots[s.name] ?? ""}
                          onChange={(e) => setSlots((v) => ({ ...v, [s.name]: e.target.value }))}
                        />
                        {s.guidance && <FieldDescription>{s.guidance}</FieldDescription>}
                      </Field>
                    ))}
                  </div>
                </FieldGroup>
                <PhraseFrame frame={candidate.pattern.canonical_frame} values={slots} className="text-[20px]" />
                {render.data && render.data.unfilled_slots.length > 0 && (
                  <p className="text-sm text-muted-foreground">
                    Returned with placeholders for {render.data.unfilled_slots.map((s) => `{${s}}`).join(", ")}.
                    No content is invented (BR-02).
                  </p>
                )}
              </>
            )}
          </Step>

          <Step
            title="Validate"
            endpoint="POST /v1/validate"
            done={!!check.data}
            json={
              check.data && (
                <>
                  <JsonBlock title="Request" value={validateReq()} />
                  <JsonBlock
                    title="Response"
                    value={{
                      verdict: check.data.verdict,
                      violations: check.data.violations.map(({ code, severity, message }) => ({
                        code,
                        severity,
                        message,
                      })),
                    }}
                  />
                </>
              )
            }
            action={
              render.data && (
                <Button
                  variant={stage === "validate" ? "default" : "secondary"}
                  disabled={check.isPending}
                  onClick={() => check.mutate()}
                >
                  Validate
                </Button>
              )
            }
          >
            {!render.data ? (
              <Waiting>Waiting for a rendered sentence.</Waiting>
            ) : !check.data ? (
              <p className="text-[18px] leading-relaxed">{render.data.text}</p>
            ) : (
              <>
                <p className="text-[18px] leading-relaxed">
                  <Highlighted text={render.data.text} violations={check.data.violations} />
                </p>
                {check.data.violations.length === 0 ? (
                  <Alert>
                    <AlertDescription>
                      No issues across checks V01 to V08. Writing may use this sentence.
                    </AlertDescription>
                  </Alert>
                ) : (
                  check.data.violations.map((v, i) => (
                    <Alert key={i} variant={v.severity === "block" ? "destructive" : "default"}>
                      <AlertDescription className="flex flex-col gap-1.5">
                        <span className="flex items-center gap-2">
                          <code>{v.code}</code>
                          <SeverityBadge value={v.severity} />
                        </span>
                        <span>{v.message}</span>
                        <span className="text-muted-foreground">Recommended: {v.recommended_action}</span>
                        {v.source && (
                          <span className="flex items-center gap-2">
                            <EvidenceLabel kind="required" /> {v.source}
                          </span>
                        )}
                      </AlertDescription>
                    </Alert>
                  ))
                )}
              </>
            )}
          </Step>
        </div>
      </div>
    </div>
  );
}

function Waiting({ children }: { children: ReactNode }) {
  return <p className="text-sm text-muted-foreground">{children}</p>;
}

function JsonBlock({ title, value }: { title: string; value: unknown }) {
  const [copied, setCopied] = useState(false);
  const text = JSON.stringify(value, null, 2);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };
  return (
    <figure className="flex min-w-0 flex-col gap-2">
      <figcaption className="flex items-center justify-between text-sm text-muted-foreground">
        {title}
        <Button type="button" variant="ghost" size="sm" onClick={() => void copy()}>
          {copied ? "Copied" : "Copy"}
        </Button>
      </figcaption>
      <pre className="overflow-x-auto bg-muted p-3 text-sm">
        <code>{text}</code>
      </pre>
    </figure>
  );
}

function Step({
  title,
  endpoint,
  done,
  json,
  action,
  children,
}: {
  title: string;
  endpoint: string;
  done: boolean;
  json?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <CardTitle>{title}</CardTitle>
          <Badge variant={done ? "success" : "secondary"}>{done ? "200 OK" : "Idle"}</Badge>
          <code className="text-sm text-muted-foreground">{endpoint}</code>
        </div>
        {action}
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {children}
        {json && (
          <details>
            <summary className="cursor-pointer text-sm text-muted-foreground">Request and response</summary>
            <div className="mt-3 grid grid-cols-2 gap-4">{json}</div>
          </details>
        )}
      </CardContent>
    </Card>
  );
}

function Highlighted({ text, violations }: { text: string; violations: Violation[] }) {
  const spans = violations.filter((v) => v.location).sort((a, b) => a.location!.start - b.location!.start);
  const out: ReactNode[] = [];
  let pos = 0;
  for (const v of spans) {
    const { start, end } = v.location!;
    if (start < pos) continue;
    out.push(text.slice(pos, start));
    out.push(
      <mark
        key={start}
        className={
          v.severity === "block"
            ? "bg-destructive/15"
            : v.severity === "warn"
              ? "bg-warning-bg text-warning-foreground"
              : undefined
        }
        title={`${v.code}: ${v.message}`}
      >
        {text.slice(start, end)}
      </mark>,
    );
    pos = end;
  }
  out.push(text.slice(pos));
  return <>{out}</>;
}
