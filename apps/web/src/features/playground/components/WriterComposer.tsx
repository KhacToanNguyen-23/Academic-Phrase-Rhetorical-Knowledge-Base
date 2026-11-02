import { Card, Field } from "@/shared/ui";
import type { Render, Version } from "../live/api";
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
  // FR-02.1/.7 and FR-07.5: expose pattern provenance/version and render its typed slots; BR-02 forbids invented values.
  return <Card title="3. Complete the pattern">
    <ErrorText error={error} />
    {loading && <p>Loading pattern…</p>}
    {version && <>
      <p className="caption">Source: {version.source_type === "authored" ? "Self-authored" : "Corpus"} · version {version.version_no}</p>
      <div className="slot-grid">{Object.keys(version.slots).map((name) => <Field key={name} label={`{${name}}`}>
        <input value={slots[name] ?? ""} onChange={(event) => onSlot(name, event.target.value)} />
      </Field>)}</div>
      <button className="btn btn-primary" type="button" disabled={rendering} onClick={onRender}>Build sentence</button>
    </>}
    {rendered && rendered.unfilled_slots.length > 0 && <p className="caption">Unfilled slots: {rendered.unfilled_slots.map((slot) => `{${slot}}`).join(", ")}</p>}
  </Card>;
}
