import { Link } from "@tanstack/react-router";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { KIND_LABELS, usePatternMeasurements } from "../api/client";

/**
 * Reviewed measures this pattern describes or reports (pattern-level links).
 * Renders nothing while the catalog is off or nothing is approved.
 */
export function MeasurementPatternContext({ patternId }: { patternId: string }) {
  const measurements = usePatternMeasurements(patternId);
  const items = (measurements.data?.items ?? []).filter((item) => item.slot_name == null);
  if (!items.length) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Measurement context</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <ul className="flex flex-col divide-y">
          {items.map((item) => (
            <li key={item.code} className="flex flex-wrap items-start justify-between gap-3 py-2">
              <span className="flex flex-col gap-1">
                <Link
                  to="/measurements/$code"
                  params={{ code: item.code }}
                  className="text-primary hover:underline"
                >
                  {item.name}
                </Link>
                <span className="text-sm text-muted-foreground">{item.definition}</span>
              </span>
              <Badge variant="outline">{KIND_LABELS[item.kind]}</Badge>
            </li>
          ))}
        </ul>
        <p className="text-sm text-muted-foreground">
          Curator-reviewed links from the measurement catalog. Report the measure your study actually used.
        </p>
      </CardContent>
    </Card>
  );
}
