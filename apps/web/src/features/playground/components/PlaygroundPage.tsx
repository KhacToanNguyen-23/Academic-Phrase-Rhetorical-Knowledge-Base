import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";

import { api, type ClaimType, type EpistemicStrength, type Genre, type RecommendationRequest, type Section, type Violation } from "@/shared/api";
import { pct } from "@/shared/lib";
import { Badge, Card, Empty, EvidenceLabel, FallbackNotice, Field, Frame, JsonBlock, PageHeader, SeverityBadge } from "@/shared/ui";

const SECTIONS: Section[] = ["Introduction", "Methods", "Results", "Discussion", "Conclusion"];
const GENRES: Genre[] = ["Original Research", "SLR", "Review"];
const CLAIMS: ClaimType[] = ["background", "gap", "method", "result", "implication", "limitation"];

interface Ctx extends RecommendationRequest {
  claim_id: string;
  evidence_level: EpistemicStrength;
  evidence_ids: string;
}

export function PlaygroundPage({ patternId }: { patternId?: string }) {
  const intents = useQuery({ queryKey: ["intents"], queryFn: api.intents });
  const journals = useQuery({ queryKey: ["journals"], queryFn: api.journals });
  const preset = useQuery({ queryKey: ["pattern", patternId], queryFn: () => api.pattern(patternId!), enabled: !!patternId });

  const [ctx, setCtx] = useState<Ctx>({ section: "Introduction", intent_id: "INT-GAP", genre: "Original Research", claim_id: "A3-C07", evidence_level: "moderate", evidence_ids: "A3-E12" });
  const set = (k: keyof Ctx, v: string) => setCtx((c) => ({ ...c, [k]: k === "evidence_ids" || k === "claim_id" ? v : v || undefined }));

  // Mở từ Library: đặt sẵn ngữ cảnh theo pattern được chọn
  useEffect(() => {
    if (preset.data) setCtx((c) => ({ ...c, section: preset.data!.section_scope[0], intent_id: preset.data!.intent_id, claim_type: preset.data!.claim_type }));
  }, [preset.data]);

  const recReq = { section: ctx.section, intent_id: ctx.intent_id, genre: ctx.genre, claim_type: ctx.claim_type, journal_id: ctx.journal_id, claim_id: ctx.claim_id, top_k: 3 };
  const rec = useMutation({ mutationFn: () => api.recommend(ctx) });
  const [picked, setPicked] = useState<string>();
  const [slots, setSlots] = useState<Record<string, string>>({});
  const candidate = rec.data?.candidates.find((c) => c.pattern.id === picked);

  const render = useMutation({ mutationFn: () => api.render({ pattern_id: candidate!.pattern.id, frame: candidate!.pattern.canonical_frame, slots }) });
  const validateReq = () => ({ text: render.data?.text ?? "", evidence_level: ctx.evidence_level, evidence_ids: ctx.evidence_ids.split(",").map((s) => s.trim()).filter(Boolean), journal_id: ctx.journal_id, claim_id: ctx.claim_id });
  const check = useMutation({ mutationFn: () => api.validate(validateReq()) });

  const { reset: resetRender } = render;
  const { reset: resetCheck } = check;
  useEffect(() => { resetRender(); resetCheck(); }, [picked, slots, resetRender, resetCheck]);
  useEffect(() => {
    const first = rec.data?.candidates.find((c) => c.pattern.id === patternId) ?? rec.data?.candidates[0];
    setPicked(first?.pattern.id);
    setSlots({});
  }, [rec.data, patternId]);

  return (
    <>
      <PageHeader
        code="API simulation · WB-03 / WB-08"
        title="Playground"
        lead="A faithful simulation of one Writing Engine call: recommend a frame, render it with the author’s content, then validate. Each step shows the exact request and response."
      />
      <div className="layout-split">
        <form className="filters" onSubmit={(e) => { e.preventDefault(); rec.mutate(); }}>
          <div className="filters-title">Context sent by Writing</div>
          <Field label="Section">
            <select value={ctx.section ?? ""} onChange={(e) => setCtx((c) => ({ ...c, section: (e.target.value || undefined) as Section, intent_id: undefined }))}>
              {SECTIONS.map((s) => <option key={s}>{s}</option>)}
            </select>
          </Field>
          <Field label="Rhetorical intent">
            <select value={ctx.intent_id ?? ""} onChange={(e) => set("intent_id", e.target.value)}>
              <option value="">Any intent</option>
              {intents.data?.filter((i) => !ctx.section || i.sections.includes(ctx.section)).map((i) => <option key={i.intent_id} value={i.intent_id}>{i.name}</option>)}
            </select>
          </Field>
          <Field label="Claim type">
            <select value={ctx.claim_type ?? ""} onChange={(e) => set("claim_type", e.target.value)}>
              <option value="">Any</option>
              {CLAIMS.map((c) => <option key={c}>{c}</option>)}
            </select>
          </Field>
          <Field label="Genre">
            <select value={ctx.genre ?? ""} onChange={(e) => set("genre", e.target.value)}>
              {GENRES.map((g) => <option key={g}>{g}</option>)}
            </select>
          </Field>
          <Field label="Target journal">
            <select value={ctx.journal_id ?? ""} onChange={(e) => set("journal_id", e.target.value)}>
              <option value="">Unspecified</option>
              {journals.data?.map((j) => <option key={j.journal_id} value={j.journal_id}>{j.title}</option>)}
            </select>
          </Field>
          <Field label="claim_id" hint="Passed through untouched for traceability (FR-09.2).">
            <input value={ctx.claim_id} onChange={(e) => set("claim_id", e.target.value)} />
          </Field>
          <Field label="Evidence level">
            <select value={ctx.evidence_level} onChange={(e) => set("evidence_level", e.target.value)}>
              <option value="low">Low</option><option value="moderate">Moderate</option><option value="high">High</option>
            </select>
          </Field>
          <Field label="evidence_ids">
            <input value={ctx.evidence_ids} onChange={(e) => set("evidence_ids", e.target.value)} />
          </Field>
          <button className="btn btn-primary" type="submit" disabled={rec.isPending}>
            {rec.isPending ? "Sending…" : "Send request"} <span className="arrow">→</span>
          </button>
        </form>

        <div className="stack">
          <Step n="Recommend" endpoint="POST /v1/recommendations" done={!!rec.data}
            json={rec.data && <><JsonBlock title="Request" value={recReq} /><JsonBlock title="Response" value={{ request_id: rec.data.request_id, fallback_tier: rec.data.fallback_tier, gated_out: rec.data.gated_out, candidates: rec.data.candidates.slice(0, 3).map((c) => ({ candidate_id: c.pattern.id, rank: c.rank, score: +c.score.toFixed(2), frame: c.pattern.canonical_frame })) }} /></>}>
            {!rec.data ? <Empty>Set the context and send a request.</Empty> : (
              <>
                <FallbackNotice tier={rec.data.fallback_tier} reason={rec.data.fallback_reason} />
                <div className="choice-list" role="radiogroup" aria-label="Candidates">
                  {rec.data.candidates.slice(0, 3).map((c) => (
                    <label key={c.pattern.id} className={`choice ${c.pattern.id === picked ? "is-active" : ""}`}>
                      <input type="radio" name="cand" checked={c.pattern.id === picked} onChange={() => setPicked(c.pattern.id)} />
                      <span>
                        <Frame frame={c.pattern.canonical_frame} />
                        <small className="caption" style={{ margin: 0 }}>{c.rank}. {c.pattern.id} — score {pct(c.score)}</small>
                      </span>
                    </label>
                  ))}
                </div>
              </>
            )}
          </Step>

          <Step n="Render" endpoint="POST /v1/render" done={!!render.data}
            json={render.data && candidate && <><JsonBlock title="Request" value={{ pattern_id: candidate.pattern.id, slots, claim_id: ctx.claim_id }} /><JsonBlock title="Response" value={render.data} /></>}
            action={candidate && <button className="btn btn-primary" type="button" onClick={() => render.mutate()}>Render sentence <span className="arrow">→</span></button>}>
            {!candidate ? <Empty>Awaiting a candidate from step 1.</Empty> : (
              <>
                <div className="slot-grid">
                  {candidate.pattern.slots_schema.map((s) => (
                    <Field key={s.name} label={`{${s.name}}${s.required ? " *" : ""}`} hint={s.guidance}>
                      <input value={slots[s.name] ?? ""} onChange={(e) => setSlots((v) => ({ ...v, [s.name]: e.target.value }))} />
                    </Field>
                  ))}
                </div>
                <p className="sentence-preview"><Frame frame={candidate.pattern.canonical_frame} values={slots} /></p>
                {render.data && render.data.unfilled_slots.length > 0 && (
                  <p className="caption">Returned with placeholders for {render.data.unfilled_slots.map((s) => `{${s}}`).join(", ")} — no content is invented (BR-02).</p>
                )}
              </>
            )}
          </Step>

          <Step n="Validate" endpoint="POST /v1/validate" done={!!check.data}
            json={check.data && <><JsonBlock title="Request" value={validateReq()} /><JsonBlock title="Response" value={{ verdict: check.data.verdict, violations: check.data.violations.map(({ code, severity, message }) => ({ code, severity, message })) }} /></>}
            action={render.data && <button className="btn btn-primary" type="button" onClick={() => check.mutate()}>Validate <span className="arrow">→</span></button>}
            aside={check.data && <span className={`verdict verdict-${check.data.verdict}`}>{check.data.verdict}</span>}>
            {!render.data ? <Empty>Awaiting a rendered sentence from step 2.</Empty> : !check.data ? (
              <p className="sentence-preview">{render.data.text}</p>
            ) : (
              <>
                <p className="sentence-preview"><Highlighted text={render.data.text} violations={check.data.violations} /></p>
                {check.data.violations.length === 0 ? <p className="notice notice-ok">No issues across checks V01–V08. Writing may use this sentence.</p> : (
                  <ul className="violation-list compact">
                    {check.data.violations.map((v, i) => (
                      <li key={i} className={`violation sev-${v.severity}`}>
                        <div className="violation-head"><span className="code">{v.code}</span><SeverityBadge value={v.severity} /></div>
                        <p>{v.message}</p>
                        <p className="caption" style={{ margin: 0 }}>Recommended: {v.recommended_action}</p>
                        {v.source && <p className="small"><EvidenceLabel kind="required" /> {v.source}</p>}
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}
          </Step>
        </div>
      </div>
    </>
  );
}

function Step({ n, endpoint, done, json, action, aside, children }: { n: string; endpoint: string; done: boolean; json?: ReactNode; action?: ReactNode; aside?: ReactNode; children: ReactNode }) {
  return (
    <Card title={<>{n} <Badge tone={done ? "ok" : "neutral"}>{done ? "200 OK" : "idle"}</Badge></>} aside={aside ?? <code className="endpoint">{endpoint}</code>} confirm={action}>
      {children}
      {json && (
        <details className="json-details">
          <summary>Request &amp; response</summary>
          <div className="json-pair">{json}</div>
        </details>
      )}
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
    out.push(<mark key={start} className={`hl hl-${v.severity}`} title={`${v.code}: ${v.message}`}>{text.slice(start, end)}</mark>);
    pos = end;
  }
  out.push(text.slice(pos));
  return <>{out}</>;
}
