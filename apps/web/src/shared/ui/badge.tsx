import type { HTMLAttributes } from "react";

import { cn } from "./utils";

export type BadgeVariant = "default" | "secondary" | "success" | "warning" | "destructive" | "info";

export function BadgePrimitive({ className, variant = "default", ...props }: HTMLAttributes<HTMLSpanElement> & { variant?: BadgeVariant }) {
  return <span className={cn("ui-badge", `ui-badge-${variant}`, className)} {...props} />;
}
