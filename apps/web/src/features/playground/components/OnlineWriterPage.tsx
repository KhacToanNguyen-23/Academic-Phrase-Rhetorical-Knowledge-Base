import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { DataState, PageHeader } from "@/components/domain";
import { liveApi, type RecommendationRequest } from "../live/api";
import { WriterComposer } from "./WriterComposer";
import { WriterContextForm, blankContext, type WriterContext } from "./WriterContextForm";
import { WriterResults } from "./WriterResults";
import { ErrorText, type WriterStage } from "./WriterStatus";
import { WriterValidation } from "./WriterValidation";

export function OnlineWriterPage() {
  // Online Writer: FR-07 search → FR-07.5 render → FR-08 validation → FR-07.7 feedback.
  const apiKey = "";
  const [context, setContext] = useState<WriterContext>(blankContext);
  const [supportingContext, setSupportingContext] = useState("");
  const [picked, setPicked] = useState("");
  const [slots, setSlots] = useState<Record<string, string>>({});
  const [draft, setDraft] = useState("");
  const [copyStatus, setCopyStatus] = useState("");
  const [searchSnapshot, setSearchSnapshot] = useState("");
  const [renderSnapshot, setRenderSnapshot] = useState("");
  const [validationSnapshot, setValidationSnapshot] = useState("");
  const epoch = useRef(0);
  const initialSearchStarted = useRef(false);

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
    mutationFn: () => liveApi.validate(
      apiKey, draft, context.claimType, context.evidenceLevel, supportingContext, slots,
    ),
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
    sourceContext: supportingContext, slots,
  }) ? validation.data : undefined;
  const feedback = useMutation({
    mutationFn: () => liveApi.feedback(apiKey, {
      recommendation_id: activeRecommendation!.recommendation_id,
      pattern_version_id: picked,
      signal: "accepted",
      payload: { context_hash: activeRecommendation!.context_hash },
    }),
  });

  useEffect(() => {
    if (taxonomy.data && options.data && !initialSearchStarted.current) {
      initialSearchStarted.current = true;
      search();
    }
    // `search` is intentionally omitted: initialSearchStarted guards this to run once per
    // mount, and including the recreated-every-render `search` would re-fire the effect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taxonomy.data, options.data]);

  const canCopy = !!activeValidation && !!activeRender &&
    activeValidation.severity !== "block" && activeRender.unfilled_slots.length === 0;

  const optionLabel = (group: string, code: string) =>
    options.data?.find((item) => item.group === group && item.code === code)?.label;
  const intentName = (code: string) =>
    taxonomy.data?.sections
      .flatMap((s) => s.moves.flatMap((m) => m.steps.flatMap((step) => step.intents)))
      .find((item) => item.code === code)?.name;
  // What the current recommendations were searched with, shown next to them.
  const searchedWith = [
    taxonomy.data?.article_genres.find((item) => item.code === context.genre)?.name,
    taxonomy.data?.sections.find((item) => item.code === context.section)?.name,
    intentName(context.intent),
    optionLabel("claim_type", context.claimType),
    optionLabel("evidence_level", context.evidenceLevel),
    journals.data?.find((item) => item.id === context.journalId)?.name,
    context.query.trim() ? `"${context.query.trim()}"` : undefined,
  ].filter((item): item is string => Boolean(item));

  // Only the button of the step the writer is on is the primary action.
  const stage: WriterStage = !activeRecommendation
    ? "search"
    : !activeRender
      ? "build"
      : !activeValidation
        ? "validate"
        : "copy";

  function resetAfterContextChange(next: WriterContext) {
    epoch.current += 1;
    setContext(next);
    setSearchSnapshot(""); setRenderSnapshot(""); setValidationSnapshot("");
    recommendation.reset(); render.reset(); validation.reset(); feedback.reset();
    setPicked(""); setSlots({}); setDraft(""); setCopyStatus("");
  }

  function changeSupportingContext(value: string) {
    setSupportingContext(value);
    setValidationSnapshot("");
    validation.reset(); feedback.reset(); setCopyStatus("");
  }

  function search() {
    // CR-01: initial empty context lists every eligible pattern; selected fields only narrow it.
    epoch.current += 1;
    setSearchSnapshot(JSON.stringify(context)); setRenderSnapshot(""); setValidationSnapshot("");
    setPicked(""); setSlots({}); setDraft(""); setCopyStatus("");
    recommendation.reset();
    render.reset(); validation.reset(); feedback.reset();
    recommendation.mutate({ epoch: epoch.current, request: {
      section: context.section || null,
      intent: context.intent || null,
      genre: context.genre || null,
      claim_type: context.claimType || null,
      evidence_level: context.evidenceLevel || null,
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
      sourceContext: supportingContext, slots,
    }));
    validation.mutate();
  }

  async function copy() {
    // Copy is enabled only after validation and after every required slot is filled (BR-02).
    if (!canCopy) return;
    try {
      await navigator.clipboard.writeText(draft);
      setCopyStatus(
        activeValidation?.complete
          ? "Copied validated sentence."
          : "Copied as a draft; some checks are unavailable.",
      );
    } catch {
      setCopyStatus("Could not copy. Check your browser's clipboard permission.");
    }
  }

  return (
    <>
      <PageHeader
        title="Writer"
        description="Find a pattern for your claim, fill its slots, then check the sentence against your evidence."
      />
      <div className="mt-6 flex flex-col gap-6">
        {taxonomy.isPending && <DataState state="loading" loadingLabel="Loading writing options" />}
        <ErrorText error={taxonomy.error || options.error || journals.error} />

        {taxonomy.data && options.data && <>
          <WriterContextForm
            context={context}
            taxonomy={taxonomy.data}
            options={options.data}
            journals={journals.data ?? []}
            supportingContext={supportingContext}
            searching={recommendation.isPending}
            primary={stage === "search"}
            onChange={resetAfterContextChange}
            onSupportingContextChange={changeSupportingContext}
            onSearch={search}
          />
          <ErrorText error={recommendation.error} />
        </>}

        {activeRecommendation && <WriterResults
          recommendation={activeRecommendation}
          picked={picked}
          searchedWith={searchedWith}
          onSelect={selectVersion}
        />}

        {activeRecommendation && picked && <WriterComposer
          version={version.data}
          loading={version.isPending}
          error={version.error || render.error}
          slots={slots}
          rendered={activeRender}
          rendering={render.isPending}
          primary={stage === "build"}
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
          copied={copyStatus.startsWith("Copied")}
          stage={stage}
          onText={changeDraft}
          onValidate={validateSentence}
          onCopy={copy}
          onFeedback={() => feedback.mutate()}
        />}
      </div>
    </>
  );
}
