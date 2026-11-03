import { getRouteApi, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";

import { useAuth } from "@/features/auth/AuthProvider";
import { Badge, Card, Empty, ErrorState, Loading, PageHeader, Tabs } from "@/shared/ui";
import { useFamilies, useLemmas, useLetters } from "../api/client";
import { VocabularyImportCard } from "./VocabularyImportCard";

const route = getRouteApi("/shell/guarded/vocabulary");
const alphabet = [..."abcdefghijklmnopqrstuvwxyz", "#"];

function statusTone(status: string | null): "ok" | "warn" | "info" | "neutral" {
  if (status === "y") return "ok";
  if (status === "r") return "warn";
  if (status === "x") return "info";
  return "neutral";
}

export function VocabularyPage() {
  const { client: authClient } = useAuth();
  const search = route.useSearch();
  const navigate = useNavigate({ from: "/vocabulary" });

  const [query, setQuery] = useState(search.q ?? "");
  const [debouncedQuery, setDebouncedQuery] = useState(search.q ?? "");
  const [showImport, setShowImport] = useState(false);

  const view = search.view ?? "lemmas";
  const coreOnly = search.coreOnly ?? false;
  const sort = search.sort ?? "alpha";
  const offset = search.offset ?? 0;
  const limit = 50;

  const isCurator = authClient?.role === "curator" || authClient?.role === "admin";
  const letters = useLetters(coreOnly);

  const lemmas = useLemmas({
    q: debouncedQuery || undefined,
    letter: search.letter,
    core_only: coreOnly,
    sort,
    limit,
    offset,
  });

  const families = useFamilies({
    q: debouncedQuery || undefined,
    limit,
    offset,
  });

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedQuery(query.trim());
      void navigate({
        search: (previous) => ({
          ...previous,
          q: query.trim() || undefined,
          letter: query.trim() ? undefined : previous.letter,
          offset: 0,
        }),
      });
    }, 250);
    return () => window.clearTimeout(timer);
  }, [navigate, query]);

  useEffect(() => {
    if (search.q !== undefined && search.q !== query) setQuery(search.q);
  }, [search.q, query]);

  const counts = useMemo(
    () => new Map((letters.data ?? []).map((item) => [item.letter, item.count])),
    [letters.data],
  );

  const totalLettersCount = useMemo(
    () => (letters.data ?? []).reduce((sum, item) => sum + item.count, 0),
    [letters.data],
  );

  const total = view === "families" ? (families.data?.total ?? 0) : (lemmas.data?.total ?? 0);
  const first = total === 0 ? 0 : offset + 1;
  const last = Math.min(offset + limit, total);

  const updateSearch = (patch: Partial<typeof search>) => {
    void navigate({ search: (previous) => ({ ...previous, ...patch }) });
  };

  const hasActiveFilters = Boolean(search.q || search.letter || coreOnly || sort !== "alpha");

  const clearFilters = () => {
    setQuery("");
    setDebouncedQuery("");
    updateSearch({ q: undefined, letter: undefined, coreOnly: undefined, sort: undefined, offset: 0 });
  };

  return (
    <div className="stack">
      <PageHeader
        code="Lexicon · Academic Vocabulary List (AVL)"
        title="Academic Vocabulary"
        lead="Browse, filter, and inspect the core academic vocabulary lexicon, frequency bands, and disciplinary distributions."
        actions={
          <div className="vocab-header-actions">
            {isCurator && (
              <button
                type="button"
                className={`btn ${showImport ? "btn-primary" : "btn-ghost"}`}
                onClick={() => setShowImport((prev) => !prev)}
              >
                {showImport ? "✕ Close Import" : "↑ Import AVL Data"}
              </button>
            )}
          </div>
        }
      />

      {showImport && isCurator && (
        <VocabularyImportCard onClose={() => setShowImport(false)} />
      )}

      <Tabs
        label="Vocabulary view navigation"
        value={view}
        onChange={(nextView) =>
          updateSearch({
            view: nextView,
            offset: 0,
            letter: nextView === "families" ? undefined : search.letter,
            coreOnly: nextView === "families" ? undefined : search.coreOnly,
            sort: nextView === "families" ? undefined : search.sort,
          })
        }
        items={[
          { id: "lemmas", label: "Lemmas", count: lemmas.data?.total },
          { id: "families", label: "Word Families", count: families.data?.total },
        ]}
      >
        <Card className="vocab-filter-card">
          <div className="vocab-toolbar">
            <div className="vocab-search-wrap">
              <input
                type="search"
                aria-label="Search vocabulary"
                placeholder={
                  view === "families"
                    ? "Search word families by headword..."
                    : "Search lemmas by prefix (e.g. analys, hypoth, meth)..."
                }
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
              {query && (
                <button
                  type="button"
                  className="vocab-search-clear"
                  onClick={() => setQuery("")}
                  aria-label="Clear search input"
                >
                  ✕
                </button>
              )}
            </div>

            {view === "lemmas" && (
              <div className="vocab-controls-row">
                <label className="vocab-checkbox-label">
                  <input
                    type="checkbox"
                    checked={coreOnly}
                    onChange={(event) =>
                      updateSearch({ coreOnly: event.target.checked || undefined, offset: 0 })
                    }
                  />
                  <span>Core only</span>
                </label>

                <label className="vocab-sort-label">
                  <span className="vocab-label-text">Sort:</span>
                  <select
                    value={sort}
                    aria-label="Sort order"
                    onChange={(event) =>
                      updateSearch({ sort: event.target.value as "alpha" | "rank", offset: 0 })
                    }
                  >
                    <option value="alpha">A–Z (Alphabetical)</option>
                    <option value="rank">Academic Rank</option>
                  </select>
                </label>

                {hasActiveFilters && (
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm vocab-reset-btn"
                    onClick={clearFilters}
                  >
                    Reset filters
                  </button>
                )}
              </div>
            )}
          </div>

          {view === "lemmas" && (
            <div className="vocab-letters-container">
              <div className="vocab-letters" role="toolbar" aria-label="Filter by initial letter">
                <button
                  type="button"
                  className={!search.letter ? "vocab-letter is-selected" : "vocab-letter"}
                  aria-pressed={!search.letter}
                  onClick={() => {
                    setQuery("");
                    setDebouncedQuery("");
                    updateSearch({ letter: undefined, q: undefined, offset: 0 });
                  }}
                >
                  <span className="vocab-letter-char">ALL</span>
                  <small className="vocab-letter-count">{totalLettersCount}</small>
                </button>
                {alphabet.map((letter) => {
                  const count = counts.get(letter) ?? 0;
                  const isSelected = search.letter === letter;
                  return (
                    <button
                      key={letter}
                      type="button"
                      className={isSelected ? "vocab-letter is-selected" : "vocab-letter"}
                      disabled={!letters.isPending && count === 0}
                      aria-pressed={isSelected}
                      onClick={() => {
                        setQuery("");
                        setDebouncedQuery("");
                        updateSearch({
                          letter: isSelected ? undefined : letter,
                          q: undefined,
                          offset: 0,
                        });
                      }}
                    >
                      <span className="vocab-letter-char">{letter.toUpperCase()}</span>
                      <small className="vocab-letter-count">{count}</small>
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </Card>

        <Card
          title={view === "families" ? "Academic Word Families" : "Academic Lemmas"}
          aside={
            total > 0 ? (
              <span className="caption">
                Showing {first.toLocaleString()}–{last.toLocaleString()} of {total.toLocaleString()}
              </span>
            ) : undefined
          }
        >
          {view === "families" ? (
            families.isPending ? (
              <Loading />
            ) : families.isError ? (
              <ErrorState onRetry={() => void families.refetch()} message={families.error.message} />
            ) : families.data.items.length === 0 ? (
              <Empty>
                {query ? (
                  <>
                    <p>No word families match &ldquo;{query}&rdquo;.</p>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => setQuery("")}
                    >
                      Clear search
                    </button>
                  </>
                ) : (
                  <>
                    <p>No word family groups recorded in the database.</p>
                    {isCurator && (
                      <p className="caption">
                        Curators can import the word families spreadsheet via the import tool above.
                      </p>
                    )}
                  </>
                )}
              </Empty>
            ) : (
              <div className="vocab-families-list">
                {families.data.items.map((family) => (
                  <details className="vocab-family-card" key={family.id}>
                    <summary className="vocab-family-summary">
                      <div className="vocab-family-summary-left">
                        <strong className="vocab-family-headword">{family.headword}</strong>
                        <Badge tone="info">{family.members.length} members</Badge>
                      </div>
                      <div className="vocab-family-summary-right">
                        <span className="caption">Rank #{family.rank}</span>
                        <span className="caption">
                          {family.family_freq.toLocaleString()} total frequency
                        </span>
                      </div>
                    </summary>
                    <div className="table-wrap vocab-family-table-wrap">
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
                          {family.members.map((member) => (
                            <tr key={`${family.id}-${member.lemma_id}`}>
                              <td>
                                <Link
                                  to="/vocabulary/$lemmaId"
                                  params={{ lemmaId: member.lemma_id }}
                                  search={search}
                                  className="vocab-word-link"
                                >
                                  <strong>{member.word}</strong>
                                </Link>
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
                                <Link
                                  to="/vocabulary/$lemmaId"
                                  params={{ lemmaId: member.lemma_id }}
                                  search={search}
                                  className="btn btn-ghost btn-sm"
                                >
                                  Inspect →
                                </Link>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </details>
                ))}
              </div>
            )
          ) : lemmas.isPending ? (
            <Loading />
          ) : lemmas.isError ? (
            <ErrorState onRetry={() => void lemmas.refetch()} message={lemmas.error.message} />
          ) : lemmas.data.items.length === 0 ? (
            <Empty>
              {hasActiveFilters ? (
                <div className="vocab-empty-filtered">
                  <p>
                    No lemmas found matching current filters
                    {search.letter ? ` (Letter: ${search.letter.toUpperCase()})` : ""}
                    {query ? ` (Query: "${query}")` : ""}.
                  </p>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={clearFilters}
                  >
                    Reset all filters
                  </button>
                </div>
              ) : (
                <div className="vocab-empty-initial">
                  <p>No academic lemmas loaded in the database yet.</p>
                  {isCurator && (
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={() => setShowImport(true)}
                    >
                      Open Import Tool
                    </button>
                  )}
                </div>
              )}
            </Empty>
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Lemma Word</th>
                    <th>Part of Speech</th>
                    <th className="num">Rank</th>
                    <th className="num">Band</th>
                    <th>Academic Status</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {lemmas.data.items.map((item) => (
                    <tr key={item.id}>
                      <td>
                        <Link
                          to="/vocabulary/$lemmaId"
                          params={{ lemmaId: item.id }}
                          search={search}
                          className="vocab-word-link"
                        >
                          <strong>{item.word}</strong>
                        </Link>
                      </td>
                      <td>
                        <Badge tone="neutral">{item.pos_label}</Badge>
                      </td>
                      <td className="num">{item.rank !== null ? `#${item.rank}` : "—"}</td>
                      <td className="num">{item.band !== null ? `Band ${item.band}` : "—"}</td>
                      <td>
                        <Badge tone={statusTone(item.status)}>{item.status_label || "—"}</Badge>
                      </td>
                      <td>
                        <Link
                          to="/vocabulary/$lemmaId"
                          params={{ lemmaId: item.id }}
                          search={search}
                          className="btn btn-ghost btn-sm"
                        >
                          Details →
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {total > 0 && (
            <div className="vocab-pagination">
              <span className="caption">
                Showing {first.toLocaleString()}–{last.toLocaleString()} of {total.toLocaleString()} {view === "families" ? "families" : "lemmas"}
              </span>
              <div className="vocab-pagination-controls">
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  disabled={offset === 0}
                  onClick={() => updateSearch({ offset: Math.max(0, offset - limit) })}
                >
                  ← Previous
                </button>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  disabled={last >= total}
                  onClick={() => updateSearch({ offset: offset + limit })}
                >
                  Next →
                </button>
              </div>
            </div>
          )}
        </Card>
      </Tabs>
    </div>
  );
}
