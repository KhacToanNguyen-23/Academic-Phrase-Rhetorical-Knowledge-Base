import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { MeasurementSlotSuggestions } from "@/features/measurement";
import { SlotValidationApiError, type Render, type SlotDefinition, type Version } from "../live/api";
import { ErrorText } from "./WriterStatus";

export function WriterComposer({
  version,
  loading,
  error,
  slots,
  rendered,
  rendering,
  primary,
  onSlot,
  onRender,
}: {
  version: Version | undefined;
  loading: boolean;
  error: unknown;
  slots: Record<string, string>;
  rendered: Render | undefined;
  rendering: boolean;
  primary: boolean;
  onSlot: (name: string, value: string) => void;
  onRender: () => void;
}) {
  const fieldErrors = error instanceof SlotValidationApiError ? error.fieldErrors : {};
  // FR-02.1/.7 and FR-07.5: expose pattern provenance/version and render its typed slots.
  // BR-02 forbids invented values.
  return (
    <Card>
      <CardHeader>
        <CardTitle>Complete the pattern</CardTitle>
        {version && (
          <CardDescription>
            Source: {version.source_type === "authored" ? "Self-authored" : "Corpus"} · version {version.version_no}
          </CardDescription>
        )}
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <ErrorText error={error instanceof SlotValidationApiError ? undefined : error} />
        {loading && (
          <div className="flex flex-col gap-3" aria-busy="true" aria-label="Loading pattern">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-2/3" />
          </div>
        )}
        {version && (
          <FieldGroup>
            <div className="grid grid-cols-2 gap-4">
              {Object.entries(version.slots).map(([name, definition]) => {
                const metadata: Partial<SlotDefinition> = typeof definition === "string" ? {} : definition;
                const label = metadata.label ?? `{${name}}`;
                const hint = [
                  metadata.instruction,
                  metadata.example ? `Example: ${metadata.example}` : undefined,
                  metadata.min_length ? `Minimum ${metadata.min_length} characters.` : undefined,
                ]
                  .filter(Boolean)
                  .join(" ");
                return (
                  <Field key={name} data-invalid={fieldErrors[name] ? true : undefined}>
                    <FieldLabel htmlFor={`slot-${name}`}>{label}</FieldLabel>
                    <Input
                      id={`slot-${name}`}
                      aria-label={`{${name}} ${label}`}
                      aria-invalid={fieldErrors[name] ? true : undefined}
                      aria-describedby={fieldErrors[name] ? `${name}-error` : undefined}
                      value={slots[name] ?? ""}
                      onChange={(event) => onSlot(name, event.target.value)}
                    />
                    {hint && <FieldDescription>{hint}</FieldDescription>}
                    <MeasurementSlotSuggestions patternId={version.pattern_id} slot={name} linkToCatalog={false} />
                    {fieldErrors[name] && (
                      <FieldError id={`${name}-error`} role="alert">
                        {fieldErrors[name]}
                      </FieldError>
                    )}
                  </Field>
                );
              })}
            </div>
            <div>
              <Button type="button" variant={primary ? "default" : "secondary"} disabled={rendering} onClick={onRender}>
                Build sentence
              </Button>
            </div>
          </FieldGroup>
        )}
        {rendered && rendered.unfilled_slots.length > 0 && (
          <p className="text-sm text-muted-foreground">
            Unfilled slots: {rendered.unfilled_slots.map((slot) => `{${slot}}`).join(", ")}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
