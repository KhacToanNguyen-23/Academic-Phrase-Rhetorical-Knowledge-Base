import { useMutation, useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { PageHeader } from "@/shared/ui";
import { liveApi, type RecommendationRequest } from "../live/api";
import { WriterComposer } from "./WriterComposer";
import { WriterContextForm, blankContext, type WriterContext } from "./WriterContextForm";
import { WriterResults } from "./WriterResults";
import { ErrorText } from "./WriterStatus";
import { WriterValidation } from "./WriterValidation";

export function OnlineWriterPage() {
  // Online Writer: FR-07 search → FR-07.5 render → FR-08 validation → FR-07.7 feedback.
  const apiKey = "";
  const [context, setContext] = useState<WriterContext>(blankContext);
  const [picked, setPicked] = useState("");
  const [slots, setSlots] = useState<Record<string, string>>({});
  const [draft, setDraft] = useState("");
  const [copyStatus, setCopyStatus] = useState("");
  const [searchSnapshot, setSearchSnapshot] = useState("");
  const [renderSnapshot, setRenderSnapshot] = useState("");
  const [validationSnapshot, setValidationSnapshot] = useState("");
  const epoch = useRef(0);

  const taxonomy = useQuery({
    queryKey: ["writer", "taxonomy"],
    queryFn: () => liveApi.taxonomy(apiKey), retry: false,
  });
  const options = useQuery({
    queryKey: ["writer", "options"],
    queryFn: () => liveApi.options(apiKey), retry: false,
  });
  const journals = useQuery({
    queryKey: ["writer", "journals"],
    queryFn: () => liveApi.journals(apiKey), retry: false,
  });
  const recommendation = useMutation({
    mutationFn: ({ request }: { request: RecommendationRequest; epoch: number }) => liveApi.recommend(apiKey, request),
    onSuccess: (result, request) => {
      if (request.epoch === epoch.current) setPicked(result.items[0]?.pattern_version_id ?? "");
    },
  });
  const activeRecommendation = searchSnapshot === JSON.stringify(context) ? recommendation.data : undefined;
  const version = useQuery({
    queryKey: ["writer", "version", picked],
    queryFn: () => liveApi.version(apiKey, picked), enabled: !!activeRecommendation && !!picked, retry: false,
  });
  const validation = useMutation({
    mutationFn: () => liveApi.validate(apiKey, draft, context.claimType, context.evidenceLevel),
  });
  const render = useMutation({
    mutationFn: ({ recommendationId, versionId, values }: {
      recommendationId: string; versionId: string; values: Record<string, string>; epoch: number;
    }) => liveApi.render(
      apiKey, recommendationId, versionId, values,
    ),
    onSuccess: (result, request) => {
      if (request.epoch === epoch.current) {
        setDraft(result.text); validation.reset(); setCopyStatus("");
      }
    },
  });
  const activeRender = renderSnapshot === JSON.stringify({
    recommendationId: activeRecommendation?.recommendation_id, versionId: picked, slots,
  }) ? render.data : undefined;
  const activeValidation = validationSnapshot === JSON.stringify({
    text: draft, claimType: context.claimType, evidenceLevel: context.evidenceLevel,
  }) ? validation.data : undefined;
  const feedback = useMutation({
    mutationFn: () => liveApi.feedback(apiKey, {
      recommendation_id: activeRecommendation!.recommendation_id,
      pattern_version_id: picked,
      signal: "accepted",
      payload: { context_hash: activeRecommendation!.context_hash },
    }),
  });

  const canCopy = !!activeValidation && !!activeRender &&
    activeValidation.severity !== "block" && activeRender.unfilled_slots.length === 0;

  function resetAfterContextChange(next: WriterContext) {
    epoch.current += 1;
    setContext(next);
    setSearchSnapshot(""); setRenderSnapshot(""); setValidationSnapshot("");
    recommendation.reset(); render.reset(); validation.reset(); feedback.reset();
    setPicked(""); setSlots({}); setDraft(""); setCopyStatus("");
  }

  function search() {
    // FR-07.1 sends the selected writing context; downstream hard gates must not be relaxed to fill results.
    if (!context.section || !context.intent || !context.genre || !context.claimType || !context.evidenceLevel) return;
    epoch.current += 1;
    setSearchSnapshot(JSON.stringify(context)); setRenderSnapshot(""); setValidationSnapshot("");
    setPicked(""); setSlots({}); setDraft(""); setCopyStatus("");
    recommendation.reset();
    render.reset(); validation.reset(); feedback.reset();
    recommendation.mutate({ epoch: epoch.current, request: {
      section: context.section,
      intent: context.intent,
      genre: context.genre,
      claim_type: context.claimType,
      evidence_level: context.evidenceLevel,
      journal_id: context.journalId || null,
      query: context.query.trim() || null,
      limit: 10,
    } });
  }

  function selectVersion(versionId: string) {
    epoch.current += 1;
    setPicked(versionId); setSlots({}); setDraft(""); setCopyStatus("");
    setRenderSnapshot(""); setValidationSnapshot("");
    render.reset(); validation.reset(); feedback.reset();
  }

  function changeSlot(name: string, value: string) {
    epoch.current += 1;
    setSlots((current) => ({ ...current, [name]: value }));
    setRenderSnapshot(""); setValidationSnapshot("");
    render.reset(); validation.reset(); feedback.reset(); setDraft(""); setCopyStatus("");
  }

  function renderSentence() {
    // FR-07.5 renders only the version issued in this recommendation; missing slots remain placeholders (BR-02).
    if (!activeRecommendation || !picked) return;
    setRenderSnapshot(JSON.stringify({
      recommendationId: activeRecommendation.recommendation_id, versionId: picked, slots,
    }));
    setValidationSnapshot("");
    render.mutate({
      recommendationId: activeRecommendation.recommendation_id,
      versionId: picked, values: { ...slots }, epoch: epoch.current,
    });
  }

  function changeDraft(text: string) {
    setValidationSnapshot("");
    setDraft(text); validation.reset(); feedback.reset(); setCopyStatus("");
  }

  function validateSentence() {
    // FR-08 validates the edited sentence against the claim/evidence context; raw text is not persisted (FR-09.6).
    setValidationSnapshot(JSON.stringify({
      text: draft, claimType: context.claimType, evidenceLevel: context.evidenceLevel,
    }));
    validation.mutate();
  }

  async function copy() {
    // Copy is enabled only after validation and after every required slot is filled (BR-02).
    if (!canCopy) return;
    try {
      await navigator.clipboard.writeText(draft);
      setCopyStatus(activeValidation?.complete ? "Copied validated sentence." : "Copied as a draft; some checks are unavailable.");
    } catch {
      setCopyStatus("Could not copy. Check your browser's clipboard permission.");
    }
  }

  return (
    <>
      <PageHeader
        title="Writer"
      />
      <div className="stack">
        {taxonomy.isPending && <p className="caption">Loading writing options…</p>}
        <ErrorText error={taxonomy.error || options.error || journals.error} />

        {taxonomy.data && options.data && <>
          <WriterContextForm
            context={context}
            taxonomy={taxonomy.data}
            options={options.data}
            journals={journals.data ?? []}
            searching={recommendation.isPending}
            onChange={resetAfterContextChange}
            onSearch={search}
          />
          <ErrorText error={recommendation.error} />
        </>}

        {activeRecommendation && <WriterResults
          recommendation={activeRecommendation}
          picked={picked}
          onSelect={selectVersion}
        />}

        {activeRecommendation && picked && <WriterComposer
          version={version.data}
          loading={version.isPending}
          error={version.error || render.error}
          slots={slots}
          rendered={activeRender}
          rendering={render.isPending}
          onSlot={changeSlot}
          onRender={renderSentence}
        />}

        {activeRender && <WriterValidation
          text={draft}
          validation={activeValidation}
          error={validation.error || feedback.error}
          validating={validation.isPending}
          canCopy={canCopy}
          copyStatus={copyStatus}
          feedbackPending={feedback.isPending}
          feedbackDone={feedback.isSuccess}
          onText={changeDraft}
          onValidate={validateSentence}
          onCopy={copy}
          onFeedback={() => feedback.mutate()}
        />}
      </div>
    </>
  );
}
