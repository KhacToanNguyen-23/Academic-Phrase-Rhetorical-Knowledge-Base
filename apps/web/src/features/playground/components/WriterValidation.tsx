import { SeverityBadge, type Severity } from "@/components/domain";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldLabel } from "@/components/ui/field";
import { Textarea } from "@/components/ui/textarea";
import type { Validation } from "../live/api";
import { ErrorText, Notice, type WriterStage } from "./WriterStatus";

export function WriterValidation({
  text,
  validation,
  error,
  validating,
  canCopy,
  copyStatus,
  feedbackPending,
  feedbackDone,
  copied,
  stage,
  onText,
  onValidate,
  onCopy,
  onFeedback,
}: {
  text: string;
  validation: Validation | undefined;
  error: unknown;
  validating: boolean;
  canCopy: boolean;
  copyStatus: string;
  feedbackPending: boolean;
  feedbackDone: boolean;
  copied: boolean;
  stage: WriterStage;
  onText: (text: string) => void;
  onValidate: () => void;
  onCopy: () => void;
  onFeedback: () => void;
}) {
  // FR-08.1/.6 and BR-03: report claim/evidence validation, including when only part of the validator is available.
  const asSeverity = (value: string) => value as Severity;
  const issues = validation?.rules.filter((rule) => rule.applied && rule.severity !== "pass") ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Review and validate</CardTitle>
        <CardDescription>
          Edit the sentence if you need to, then check it against your claim and evidence.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <Field>
          <FieldLabel htmlFor="writer-draft">Draft sentence</FieldLabel>
          <Textarea id="writer-draft" value={text} rows={4} onChange={(event) => onText(event.target.value)} />
        </Field>
        <div>
          <Button
            variant={stage === "validate" ? "default" : "secondary"}
            disabled={!text.trim() || validating}
            onClick={onValidate}
          >
            {validating ? "Validating…" : "Validate sentence"}
          </Button>
        </div>
        <ErrorText error={error} />
        {validation && (
          <>
            <Alert variant={validation.severity === "block" ? "destructive" : "default"}>
              <AlertTitle className="flex items-center gap-2">
                Claim check
                <SeverityBadge value={asSeverity(validation.severity)} />
                <span className="font-normal text-muted-foreground">
                  {validation.complete ? "Complete" : "Partial"}
                </span>
              </AlertTitle>
            </Alert>
            {validation.checks_unavailable.length > 0 && (
              <Notice>
                Some checks are unavailable ({validation.checks_unavailable.join(", ")}). This sentence has not been
                fully validated.
              </Notice>
            )}
            {validation.checks_not_applicable.length > 0 && (
              <Notice>
                Journal guideline compliance is outside this sentence-level check.
              </Notice>
            )}
            {(validation.metric_warnings ?? []).length > 0 && (
              // FR-08.2 / ADR-0015: report-only; it does not change the claim-check severity.
              <Notice>
                Check your measures:{" "}
                {(validation.metric_warnings ?? []).map((warning) => warning.name).join(", ")}{" "}
                {(validation.metric_warnings ?? []).length === 1 ? "is" : "are"} named in the sentence but not in
                your slots or context. Keep a metric only if your study actually measured it.
              </Notice>
            )}
            {issues.map((rule) => (
              <Alert key={rule.code} variant={rule.severity === "block" ? "destructive" : "default"}>
                <AlertTitle className="flex items-center gap-2">
                  {rule.code}
                  <SeverityBadge value={asSeverity(rule.severity)} />
                </AlertTitle>
                <AlertDescription>
                  {rule.message} {rule.recommended_action && `${rule.recommended_action}`}
                </AlertDescription>
              </Alert>
            ))}
            <div className="flex flex-wrap items-center gap-3">
              <Button variant={stage === "copy" ? "default" : "secondary"} disabled={!canCopy} onClick={onCopy}>
                {validation.complete ? "Copy sentence" : "Copy draft"}
              </Button>
              {canCopy && copied && (
                <Button variant="secondary" disabled={feedbackPending || feedbackDone} onClick={onFeedback}>
                  {feedbackDone ? "Feedback recorded" : "This pattern is useful"}
                </Button>
              )}
            </div>
            {copyStatus && (
              <p role="status" className="text-sm text-muted-foreground">
                {copyStatus}
              </p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
