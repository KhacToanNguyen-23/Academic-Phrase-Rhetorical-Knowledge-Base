import { Link } from "@tanstack/react-router";

import { useSlotSuggestions } from "../api/client";

/** Reviewed catalog suggestions for one slot. Renders nothing when there are none. */
export function MeasurementSlotSuggestions({ patternId, slot }: { patternId: string; slot: string }) {
  const suggestions = useSlotSuggestions(patternId, slot);
  const items = suggestions.data?.items ?? [];
  if (!items.length) return null;
  return (
    <p>
      <span className="text-muted-foreground">Measurement ideas: </span>
      {items.map((item, index) => (
        <span key={item.code}>
          {index ? ", " : ""}
          <Link to="/measurements/$code" params={{ code: item.code }} className="text-primary hover:underline">
            {item.name}
          </Link>
        </span>
      ))}
      <span className="text-muted-foreground"> (suggestions only)</span>
    </p>
  );
}
