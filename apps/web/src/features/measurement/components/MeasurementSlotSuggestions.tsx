import { Link } from "@tanstack/react-router";

import { useSlotSuggestions } from "../api/client";

/**
 * Reviewed catalog suggestions for one slot. Renders nothing when there are none.
 * Never fills the slot (FR-07.5, AT-08). `linkToCatalog` is off in the public Writer,
 * where the staff-only catalog pages are not reachable.
 */
export function MeasurementSlotSuggestions({
  patternId,
  slot,
  linkToCatalog = true,
}: {
  patternId: string;
  slot: string;
  linkToCatalog?: boolean;
}) {
  const suggestions = useSlotSuggestions(patternId, slot);
  const items = suggestions.data?.items ?? [];
  if (!items.length) return null;
  return (
    <p className="text-sm" data-testid={`measurement-ideas-${slot}`}>
      <span className="text-muted-foreground">Measurement ideas: </span>
      {items.map((item, index) => (
        <span key={item.code}>
          {index ? ", " : ""}
          {linkToCatalog ? (
            <Link to="/measurements/$code" params={{ code: item.code }} className="text-primary hover:underline">
              {item.name}
            </Link>
          ) : (
            <span title={item.example ?? undefined}>{item.name}</span>
          )}
        </span>
      ))}
      <span className="text-muted-foreground"> (suggestions only — write your own value)</span>
    </p>
  );
}
