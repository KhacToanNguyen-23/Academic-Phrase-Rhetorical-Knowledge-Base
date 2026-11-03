import { Card, Field } from "@/shared/ui";
import { SlotValidationApiError, type Render, type SlotDefinition, type Version } from "../live/api";
import { ErrorText } from "./WriterStatus";

export function WriterComposer({
  version, loading, error, slots, rendered, rendering, onSlot, onRender,
}: {
  version: Version | undefined;
  loading: boolean;
  error: unknown;
  slots: Record<string, string>;
  rendered: Render | undefined;
  rendering: boolean;
  onSlot: (name: string, value: string) => void;
  onRender: () => void;
}) {
  const fieldErrors = error instanceof SlotValidationApiError ? error.fieldErrors : {};
  // FR-02.1/.7 and FR-07.5: expose pattern provenance/version and render its typed slots; BR-02 forbids invented values.
  return <Card title="3. Complete the pattern">
    <ErrorText error={error instanceof SlotValidationApiError ? undefined : error} />
    {loading && <p>Loading pattern…</p>}
    {version && <>
      <p className="caption">Source: {version.source_type === "authored" ? "Self-authored" : "Corpus"} · version {version.version_no}</p>
      <div className="slot-grid">{Object.entries(version.slots).map(([name, definition]) => {
        const metadata: Partial<SlotDefinition> = typeof definition === "string" ? {} : definition;
        const label = metadata.label ?? `{${name}}`;
        const hint = [metadata.instruction, metadata.example ? `Example: ${metadata.example}` : undefined,
          metadata.min_length ? `Minimum ${metadata.min_length} characters.` : undefined].filter(Boolean).join(" ");
        return <Field key={name} label={label} hint={hint || undefined}>
          <input
            aria-label={`{${name}} ${label}`}
            aria-invalid={fieldErrors[name] ? true : undefined}
            aria-describedby={fieldErrors[name] ? `${name}-error` : undefined}
            value={slots[name] ?? ""}
            onChange={(event) => onSlot(name, event.target.value)}
          />
          {fieldErrors[name] && <span id={`${name}-error`} className="field-error" role="alert">{fieldErrors[name]}</span>}
        </Field>;
      })}</div>
      <button className="btn btn-primary" type="button" disabled={rendering} onClick={onRender}>Build sentence</button>
    </>}
    {rendered && rendered.unfilled_slots.length > 0 && <p className="caption">Unfilled slots: {rendered.unfilled_slots.map((slot) => `{${slot}}`).join(", ")}</p>}
  </Card>;
}
