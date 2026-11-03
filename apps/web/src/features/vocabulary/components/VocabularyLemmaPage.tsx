import { getRouteApi, Link } from "@tanstack/react-router";
import type { CSSProperties } from "react";

import { Badge, Card, Empty, ErrorState, Loading, PageHeader, Stat } from "@/shared/ui";
import { useLemma } from "../api/client";

const route = getRouteApi("/vocabulary/$lemmaId");

export function VocabularyLemmaPage() {
  const { lemmaId } = route.useParams();
  const search = route.useSearch();
  const lemma = useLemma(lemmaId);

  if (lemma.isPending) {
    return (
      <div className="stack">
        <Loading />
      </div>
    );
  }

  if (lemma.isError) {
    return (
      <div className="stack">
        <ErrorState onRetry={() => void lemma.refetch()} message={lemma.error.message} />
      </div>
    );
  }

  if (!lemma.data) {
    return (
      <div className="stack">
        <Empty>Vocabulary lemma not found.</Empty>
      </div>
    );
  }

  const item = lemma.data;
  const hasDomainStats = item.domain_stats.length > 0;
  const hasFamilies = item.families.length > 0;

  const maxRatio = Math.max(1.2, ...item.domain_stats.map((stat) => stat.relative_ratio));
  const expectationPosition = Math.min(100, (1 / maxRatio) * 100);

  return (
    <div className="stack">
      <PageHeader
        code="Lexicon · Academic Vocabulary List (AVL)"
        title={
          <span className="vocab-lemma-title">
            <span className="vocab-lemma-word">{item.word}</span>
            <span className="vocab-lemma-pos">({item.pos_label})</span>
          </span>
        }
        lead={`Academic lemma #${item.rank ?? "—"} · Band ${item.band ?? "—"} · Status: ${item.status_label}`}
        actions={
          <div className="vocab-header-actions">
            <Badge tone={item.is_core ? "ok" : "neutral"}>{item.status_label}</Badge>
            <Link to="/vocabulary" search={search} className="btn btn-ghost btn-sm">
              ← Back to Vocabulary
            </Link>
          </div>
        }
      />

      <div className="stat-row vocab-stat-row">
        <Stat
          label="Rank"
          value={item.rank !== null ? `#${item.rank}` : "—"}
          note="AVL overall frequency rank"
        />
        <Stat
          label="Band"
          value={item.band !== null ? `Band ${item.band}` : "—"}
          note="Core academic band"
        />
        <Stat
          label="COCA-Acad"
          value={
            item.coca_acad !== null ? (
              <span title={`${item.coca_acad.toLocaleString()} occurrences`}>
                {item.coca_acad.toLocaleString()}
              </span>
            ) : (
              "—"
            )
          }
          note="Academic occurrences"
        />
        <Stat
          label="COCA-All"
          value={
            item.coca_all !== null ? (
              <span title={`${item.coca_all.toLocaleString()} occurrences`}>
                {item.coca_all.toLocaleString()}
              </span>
            ) : (
              "—"
            )
          }
          note="Total corpus occurrences"
        />
        <Stat
          label="Ratio"
          value={item.ratio !== null ? `${item.ratio.toFixed(2)}x` : "—"}
          note="Academic vs general ratio"
          tone={item.ratio !== null && item.ratio >= 1.5 ? "ok" : undefined}
        />
        <Stat
          label="Dispersion"
          value={item.disp !== null ? item.disp.toFixed(2) : "—"}
          note="Cross-disciplinary spread (0–1)"
        />
        <Stat
          label="Range"
          value={item.range !== null ? `${item.range}/9` : "—"}
          note="Disciplines represented"
        />
      </div>

      {hasDomainStats && (
        <Card
          title="Disciplinary Distribution"
          aside={<span className="caption">Relative Ratio · 1.0 = General Expectation</span>}
        >
          <div className="vocab-chart-wrapper">
            <p className="caption vocab-chart-desc">
              Relative ratio compares frequency in a discipline against uniform academic distribution.
              Values greater than 1.0 indicate higher specialization in that field.
            </p>
            <div className="vocab-chart" role="list" aria-label="Relative ratio by academic domain">
              {item.domain_stats.map((stat) => {
                const isOverIndex = stat.relative_ratio >= 1.0;
                return (
                  <div className="vocab-chart-row" key={stat.domain} role="listitem">
                    <span className="vocab-chart-label" title={stat.domain_label}>
                      {stat.domain_label}
                    </span>
                    <div
                      className="vocab-chart-track"
                      style={{ "--vocab-expectation": `${expectationPosition}%` } as CSSProperties}
                    >
                      <span
                        className="vocab-chart-expectation"
                        title="1.0 Expectation threshold"
                        aria-hidden
                      />
                      <span
                        className={`vocab-chart-bar ${isOverIndex ? "is-enriched" : ""}`}
                        style={{ width: `${Math.min(100, (stat.relative_ratio / maxRatio) * 100)}%` }}
                        title={`${stat.domain_label}: ${stat.freq.toLocaleString()} occurrences (${stat.relative_ratio.toFixed(2)}x)`}
                      />
                    </div>
                    <div className="vocab-chart-values">
                      <strong className={isOverIndex ? "text-ok" : ""}>
                        {stat.relative_ratio.toFixed(2)}x
                      </strong>
                      <span className="caption vocab-chart-count">
                        {stat.freq.toLocaleString()}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </Card>
      )}

      {hasFamilies && (
        <Card
          title="Morphological Word Family"
          aside={
            <span className="caption">
              {item.families.reduce((sum, f) => sum + f.members.length, 0)} member form(s)
            </span>
          }
        >
          <div className="vocab-family-group">
            {item.families.map((family) => (
              <section className="vocab-family" key={family.id}>
                <div className="vocab-family-heading">
                  <div className="vocab-family-title-block">
                    <h3>Headword: <em>{family.headword}</em></h3>
                    <Badge tone="info">{family.members.length} members</Badge>
                  </div>
                  <span className="caption">
                    Family Rank #{family.rank} · {family.family_freq.toLocaleString()} total frequency
                  </span>
                </div>
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Word Form</th>
                        <th>Part of Speech</th>
                        <th className="num">Frequency</th>
                        <th>Category</th>
                        <th>Domains</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {family.members.map((member) => {
                        const isCurrent = member.lemma_id === item.id;
                        return (
                          <tr
                            className={isCurrent ? "vocab-current-row" : undefined}
                            key={`${family.id}-${member.lemma_id}`}
                          >
                            <td>
                              <div className="vocab-word-cell">
                                {isCurrent ? (
                                  <>
                                    <strong>{member.word}</strong>
                                    <Badge tone="info">Current</Badge>
                                  </>
                                ) : (
                                  <Link
                                    to="/vocabulary/$lemmaId"
                                    params={{ lemmaId: member.lemma_id }}
                                    search={search}
                                    className="vocab-word-link"
                                  >
                                    <strong>{member.word}</strong>
                                  </Link>
                                )}
                              </div>
                            </td>
                            <td>
                              <Badge tone="neutral">{member.pos_label}</Badge>
                            </td>
                            <td className="num">{member.freq.toLocaleString()}</td>
                            <td>
                              <Badge>{member.category_label}</Badge>
                            </td>
                            <td>{member.domains.join(", ") || "—"}</td>
                            <td>
                              {isCurrent ? (
                                <span className="caption">Selected</span>
                              ) : (
                                <Link
                                  to="/vocabulary/$lemmaId"
                                  params={{ lemmaId: member.lemma_id }}
                                  search={search}
                                  className="btn btn-ghost btn-sm"
                                >
                                  Inspect →
                                </Link>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </section>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
