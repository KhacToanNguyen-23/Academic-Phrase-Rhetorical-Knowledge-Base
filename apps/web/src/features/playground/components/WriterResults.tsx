import { Card } from "@/shared/ui";
import type { Recommendation } from "../live/api";

const fallbackLabels: Record<string, string> = {
  journal_genre: "Journal and genre",
  similar_journal_genre: "Similar journal",
  subfield_genre: "Subfield",
  field_genre: "Field",
  generic_genre: "General",
};

const scoreLabels: Record<string, string> = {
  discipline: "Discipline",
  journal_genre: "Journal / genre",
  evidence: "Evidence alignment",
  linguistic: "Keyword match",
  provenance: "Provenance",
};

export function WriterResults({
  recommendation, picked, onSelect,
}: {
  recommendation: Recommendation;
  picked: string;
  onSelect: (versionId: string) => void;
}) {
  const scoreKeys = recommendation.items[0] ? Object.keys(recommendation.items[0].breakdown) : [];

  // CR-01 / FR-07.3/.4: show eligible samples immediately in a filterable table.
  return <Card title="2. Recommended patterns">
    {recommendation.fallback_reason && <p className="notice">{recommendation.fallback_reason}</p>}
    {(recommendation.warnings ?? []).map((warning) => <p className="notice" key={warning}>{warning}</p>)}
    <p className="caption">Select an evidence level to hide patterns that exceed it. No evidence check is applied until one is selected.</p>
    {(recommendation.excluded.GATE_EVIDENCE ?? 0) > 0 && <p className="notice">
      {recommendation.excluded.GATE_EVIDENCE} samples hidden because they exceed the selected evidence level.
    </p>}
    {recommendation.items.length === 0 && <p>No patterns meet these criteria. Try changing the context or evidence level.</p>}
    {recommendation.items.length > 0 && <div className="table-scroll">
      <table className="table writer-table" aria-label="Recommended patterns">
        <thead><tr>
          <th scope="col">Select</th>
          <th scope="col">Sentence frame</th>
          <th scope="col">Score</th>
          <th scope="col">Fallback</th>
          {scoreKeys.map((key) => <th scope="col" key={key}>{scoreLabels[key] ?? key.replaceAll("_", " ")}</th>)}
          <th scope="col">Source and license</th>
        </tr></thead>
        <tbody>{recommendation.items.map((item) => <tr key={item.pattern_version_id}>
          <td><input
            type="radio"
            name="writer-candidate"
            aria-label={`Select ${item.canonical_frame}`}
            checked={picked === item.pattern_version_id}
            onChange={() => onSelect(item.pattern_version_id)}
          /></td>
          <td><strong>{item.canonical_frame}</strong>
            {item.explanations.map((explanation) => <small className="table-detail" key={explanation}>{explanation}</small>)}
          </td>
          <td>{item.score.toFixed(2)}</td>
          <td>{fallbackLabels[item.fallback_tier] ?? "General"}</td>
          {scoreKeys.map((key) => {
            const value = item.breakdown[key];
            return <td key={key}>{value === null ? "—" : value.toFixed(2)}</td>;
          })}
          <td>
            <span>{item.source_type === "authored" ? "Self-authored" : "Corpus"} · v{item.version_no}</span>
            {(item.license_name || item.license_code) && <small className="table-detail">
              {item.license_name ?? item.license_code}
              {item.license_name && item.license_code ? ` (${item.license_code})` : ""}
              {item.license_flag ? " · Copyrighted source, internal use only" : ""}
            </small>}
            {item.source_reference && <small className="table-detail">{item.source_reference}</small>}
          </td>
        </tr>)}</tbody>
      </table>
    </div>}
  </Card>;
}
