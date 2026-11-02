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
  // FR-07.3/.4 and BR-08: explain prototype score inputs and provenance; avoid implying validated ranking.
  return <Card title="2. Recommended patterns">
    {recommendation.fallback_reason && <p className="notice">{recommendation.fallback_reason}</p>}
    {(recommendation.warnings ?? []).map((warning) => <p className="notice" key={warning}>{warning}</p>)}
    <p className="caption">Prototype score uses currently available signals; unavailable criteria are not scored.</p>
    {recommendation.items.length === 0 && <p>No patterns meet these criteria. Try changing the context or evidence level.</p>}
    <div className="choice-list" role="radiogroup" aria-label="Recommended patterns">
      {recommendation.items.map((item) => <label key={item.pattern_version_id} className="choice">
        <input type="radio" name="writer-candidate" checked={picked === item.pattern_version_id} onChange={() => onSelect(item.pattern_version_id)} />
        <span><strong>{item.canonical_frame}</strong><br />
          <small>Prototype score {item.score.toFixed(2)} · {fallbackLabels[item.fallback_tier] ?? "General"}</small><br />
          <small>Source: {item.source_type === "authored" ? "Self-authored" : "Corpus"} · Version {item.version_no}
            {item.source_reference && ` · ${item.source_reference}`}
            {(item.license_name || item.license_code) &&
              ` · License ${item.license_name ?? item.license_code}${item.license_name && item.license_code ? ` (${item.license_code})` : ""}`}
          </small><br />
          {item.license_flag && <small className="notice">Copyrighted source — internal use only</small>}
          {item.explanations.map((explanation) => <small key={explanation}>{explanation}<br /></small>)}
          <div className="score-grid" aria-label="Score criteria">
            {Object.entries(item.breakdown).map(([key, value]) => <span className="score-cell" key={key}>
              <small>{scoreLabels[key] ?? key.replaceAll("_", " ")}</small>
              <strong>{value === null ? "—" : value.toFixed(2)}</strong>
            </span>)}
          </div>
        </span>
      </label>)}
    </div>
  </Card>;
}
