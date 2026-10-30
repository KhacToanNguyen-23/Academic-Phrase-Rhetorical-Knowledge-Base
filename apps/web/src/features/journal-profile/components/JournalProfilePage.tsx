import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";

import { api, type JournalFingerprint, type JournalProfile } from "@/shared/api";
import { Badge, Card, Empty, EvidenceLabel, FallbackNotice, Loading, PageHeader } from "@/shared/ui";

const MIN_SAMPLE = 30; // ngưỡng admin cấu hình (FR-03.6); dưới ngưỡng → fallback

export function JournalProfilePage({ journalId }: { journalId?: string }) {
  const list = useQuery({ queryKey: ["journals"], queryFn: api.journals });
  const detail = useQuery({ queryKey: ["journal", journalId], queryFn: () => api.journal(journalId!), enabled: !!journalId });

  return (
    <>
      <PageHeader
        code="Journal intelligence · WB-04"
        title="Journal Profiles"
        lead="Verified author guidelines are reported separately from stylistic tendencies observed in the corpus. Corpus statistics are never presented as journal requirements."
      />
      <div className="layout-split">
        <nav className="journal-nav" aria-label="Journals">
          {list.isPending ? <Loading /> : list.data?.map((j) => (
            <Link key={j.journal_id} to="/journals/$journalId" params={{ journalId: j.journal_id }} className="journal-link" activeProps={{ "aria-current": "page" }}>
              <strong>{j.title}</strong>
              <small className="muted">ISSN-L {j.issn_l}</small>
            </Link>
          ))}
        </nav>
        <div className="stack">
          {!journalId ? <Card title="Overview"><Empty>Select a journal to view its profile.</Empty></Card>
            : detail.isPending ? <Loading />
            : detail.data ? <Profile j={detail.data} />
            : <Empty>Journal not found.</Empty>}
        </div>
      </div>
    </>
  );
}

function Profile({ j }: { j: JournalProfile }) {
  const lowSample = j.fingerprints.every((f) => f.sample_n < MIN_SAMPLE);
  return (
    <>
      <Card title={j.title} aside={<Badge>{j.field}</Badge>}>
        <dl className="kv">
          <dt>ISSN-L</dt><dd>{j.issn_l}</dd>
          <dt>Publisher</dt><dd>{j.publisher}</dd>
          <dt>Guidelines</dt>
          <dd>{j.guideline_url
            ? <><a href={j.guideline_url} target="_blank" rel="noreferrer">{j.guideline_url}</a> <span className="caption">v{j.guideline_version}, accessed {j.retrieved_at}</span></>
            : <span className="muted">No guideline source on record</span>}</dd>
        </dl>
        {lowSample && <FallbackNotice tier="field" reason={`All fingerprints have N < ${MIN_SAMPLE}; recommendations fall back to ${j.field}.`} />}
      </Card>

      <Card title="Author guidelines" aside={<EvidenceLabel kind="required" />}>
        {j.guidelines.length === 0 ? (
          <Empty>No rule has been verified. “Journal requires” is never inferred from corpus statistics (BR-09).</Empty>
        ) : (
          <table className="table">
            <thead><tr><th scope="col">Level</th><th scope="col">Rule</th><th scope="col">Source</th><th scope="col">Verified</th></tr></thead>
            <tbody>
              {j.guidelines.map((g) => (
                <tr key={g.rule_id}>
                  <td><Badge tone={g.level === "required" ? "bad" : g.level === "recommended" ? "warn" : "neutral"}>{g.level}</Badge></td>
                  <td>{g.text}</td>
                  <td className="small muted">{g.source_excerpt}</td>
                  <td className="small">{g.verified_at}<br /><span className="muted">{g.reviewer}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {j.fingerprints.map((f) => <Fingerprint key={f.genre + f.date_range} f={f} field={j.field} />)}
    </>
  );
}

function Fingerprint({ f, field }: { f: JournalFingerprint; field: string }) {
  const max = Math.max(...f.features.flatMap((x) => [x.journal_value, x.field_baseline]));
  return (
    <Card title={`Language fingerprint: ${f.genre}`} aside={<EvidenceLabel kind="observed" />}>
      <p className="caption" style={{ marginTop: 0 }}>
        N = {f.sample_n} articles, {f.date_range}; method {f.method_version}.{" "}
        <Badge tone={f.confidence === "low" ? "warn" : "ok"}>{f.confidence} confidence</Badge>
      </p>
      <table className="table fp-table">
        <caption className="sr-only">Journal compared with the {field} baseline</caption>
        <thead><tr><th scope="col">Feature</th><th scope="col">Journal vs. field baseline ({field})</th></tr></thead>
        <tbody>
          {f.features.map((x, i) => (
            <tr key={x.name}>
              <th scope="row">{x.name}</th>
              <td>
                <div className="bars">
                  <div className="bar bar-journal" style={{ width: `${(x.journal_value / max) * 100}%`, animationDelay: `${i * 0.08}s` }}><span>{x.journal_value} {x.unit}</span></div>
                  <div className="bar bar-field" style={{ width: `${(x.field_baseline / max) * 100}%`, animationDelay: `${i * 0.08 + 0.1}s` }}><span>{x.field_baseline} {x.unit}</span></div>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="legend small"><span className="swatch swatch-journal" /> Journal <span className="swatch swatch-field" /> Field baseline</p>
      <p className="caption">Descriptive statistics used for soft ranking only; they do not constitute journal policy.</p>
    </Card>
  );
}
