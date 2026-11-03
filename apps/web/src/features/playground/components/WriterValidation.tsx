import { Card, Field } from "@/shared/ui";
import type { Validation } from "../live/api";
import { ErrorText } from "./WriterStatus";

export function WriterValidation({
  text, validation, error, validating, canCopy, copyStatus, feedbackPending,
  feedbackDone, onText, onValidate, onCopy, onFeedback,
}: {
  text: string;
  validation: Validation | undefined;
  error: unknown;
  validating: boolean;
  canCopy: boolean;
  copyStatus: string;
  feedbackPending: boolean;
  feedbackDone: boolean;
  onText: (text: string) => void;
  onValidate: () => void;
  onCopy: () => void;
  onFeedback: () => void;
}) {
  // FR-08.1/.6 and BR-03: report claim/evidence validation, including when only part of the validator is available.
  const issues = validation?.rules.filter((rule) => rule.applied && rule.severity !== "pass") ?? [];

  return <Card title="4. Review and validate">
    <Field label="Draft sentence">
      <textarea value={text} rows={4} onChange={(event) => onText(event.target.value)} />
    </Field>
    <button className="btn btn-primary" type="button" disabled={!text.trim() || validating} onClick={onValidate}>Validate sentence</button>
    <ErrorText error={error} />
    {validation && <>
      <p><strong>Claim check: {validation.severity === "pass" ? "Pass" : validation.severity === "warn" ? "Warning" : "Blocked"}</strong> · {validation.complete ? "Complete" : "Partial"}</p>
      {validation.checks_unavailable.length > 0 && <>
        <p className="notice">Some checks are unavailable ({validation.checks_unavailable.join(", ")}). This sentence has not been fully validated.</p>
        {validation.checks_unavailable.includes("V05") && <p className="notice">V05 not checked: verified Offline guideline data is unavailable.</p>}
      </>}
      {issues.map((rule) => <p key={rule.code} className="notice">{rule.severity === "warn" ? "Warning" : rule.severity === "block" ? "Blocked" : "Pass"}: {rule.message} {rule.recommended_action && `— ${rule.recommended_action}`}</p>)}
      <button className="btn btn-primary" type="button" disabled={!canCopy} onClick={onCopy}>
        {validation.complete ? "Copy sentence" : "Copy draft"}
      </button>
      {copyStatus && <p role="status">{copyStatus}</p>}
      {canCopy && copyStatus.startsWith("Copied") && <button className="btn" type="button" disabled={feedbackPending || feedbackDone} onClick={onFeedback}>
        {feedbackDone ? "Feedback recorded" : "This pattern is useful"}
      </button>}
    </>}
  </Card>;
}
