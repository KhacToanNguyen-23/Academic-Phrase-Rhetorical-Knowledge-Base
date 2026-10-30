import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { api, type EpistemicStrength, type Violation } from "@/shared/api";
import { Badge, Card, Empty, EvidenceLabel, Field, PageHeader, SeverityBadge } from "@/shared/ui";

const KIND_LABEL: Record<Violation["kind"], string> = { scientific: "Scientific risk", language: "Language", policy: "Journal policy" };

export function ValidationConsolePage({ initialText }: { initialText?: string }) {
  const journals = useQuery({ queryKey: ["journals"], queryFn: api.journals });
  const [text, setText] = useState(initialText ?? "These findings prove that the proposed method outperforms all baselines by 23%.");
  const [evidenceLevel, setEvidenceLevel] = useState<EpistemicStrength>("moderate");
  const [evidenceIds, setEvidenceIds] = useState("");
  const [journalId, setJournalId] = useState("");

  const run = useMutation({
    mutationFn: (text: string) => api.validate({ text, evidence_level: evidenceLevel, evidence_ids: evidenceIds.split(",").map((s) => s.trim()).filter(Boolean), journal_id: journalId || undefined }),
  });
  const result = run.data;

  const groups = (["scientific", "policy", "language"] as const)
    .map((k) => ({ kind: k, items: result?.violations.filter((v) => v.kind === k) ?? [] }))
    .filter((g) => g.items.length);

  return (
    <>
      <PageHeader
        code="Section III · WB-08"
        title="Validation"
        lead="Checks claim strength against evidence, flags fabricated references or figures, enforces verified journal guidelines and reviews language quality."
      />
      <div className="layout-split">
        <form className="stack" onSubmit={(e) => { e.preventDefault(); run.mutate(text); }}>
          <Card
            title="Input"
            confirm={
              <button className="btn btn-primary" type="submit" disabled={!text.trim() || run.isPending}>
                {run.isPending ? "Checking…" : "Confirm & validate"} <span className="arrow">→</span>
              </button>
            }
          >
            <Field label="Sentence or passage">
              <textarea rows={6} value={text} onChange={(e) => setText(e.target.value)} />
            </Field>
            <Field label="Strength of available evidence">
              <select value={evidenceLevel} onChange={(e) => setEvidenceLevel(e.target.value as EpistemicStrength)}>
                <option value="low">Low</option><option value="moderate">Moderate</option><option value="high">High</option>
              </select>
            </Field>
            <Field label="Evidence references" hint="Leave empty if none are linked — unsupported figures and citations will be blocked (V03).">
              <input value={evidenceIds} onChange={(e) => setEvidenceIds(e.target.value)} />
            </Field>
            <Field label="Target journal">
              <select value={journalId} onChange={(e) => setJournalId(e.target.value)}>
                <option value="">Unspecified</option>
                {journals.data?.map((j) => <option key={j.journal_id} value={j.journal_id}>{j.title}</option>)}
              </select>
            </Field>
          </Card>
        </form>

        <div className="stack" aria-live="polite">
          {!result ? (
            <Card title="Report"><Empty>Submit a sentence to obtain a pass, warn or block verdict.</Empty></Card>
          ) : (
            <>
              <Card title="Verdict" aside={<span className={`verdict verdict-${result.verdict}`}>{result.verdict}</span>}>
                <p className="sentence-preview"><Highlighted text={run.variables ?? ""} violations={result.violations} /></p>
                <p className="caption">
                  {result.violations.length} issue{result.violations.length === 1 ? "" : "s"} found;{" "}
                  {result.violations.filter((v) => v.severity === "block").length} blocking.
                </p>
              </Card>
              {groups.map((g) => (
                <Card key={g.kind} title={KIND_LABEL[g.kind]}>
                  <ul className="violation-list">
                    {g.items.map((v, i) => (
                      <li key={i} className={`violation sev-${v.severity}`} style={{ animationDelay: `${i * 0.06}s` }}>
                        <div className="violation-head"><span className="code">{v.code}</span><SeverityBadge value={v.severity} /></div>
                        <p>{v.message}</p>
                        <p className="caption" style={{ margin: 0 }}>Recommended: {v.recommended_action}</p>
                        {v.source && <p className="small"><EvidenceLabel kind="required" /> {v.source}</p>}
                      </li>
                    ))}
                  </ul>
                </Card>
              ))}
              {result.suggestion && (
                <Card
                  title="Suggested revision"
                  aside={<EvidenceLabel kind="suggested" />}
                  confirm={<button type="button" className="btn btn-primary" onClick={() => setText(result.suggestion!)}>Accept revision <span className="arrow">→</span></button>}
                >
                  <p className="sentence-preview">{result.suggestion}</p>
                </Card>
              )}
              {result.violations.some((v) => v.severity === "block") && (
                <p className="caption">
                  Overrides require a written rationale and are audited (FR-08.5); licence and copyright restrictions cannot be overridden. <Badge>Forthcoming</Badge>
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </>
  );
}

/** Tô vị trí lỗi trong câu theo `location` (FR-08.6). */
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
