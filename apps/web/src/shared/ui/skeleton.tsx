import type { HTMLAttributes } from "react";

import { cn } from "./utils";

export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div aria-hidden className={cn("ui-skeleton", className)} {...props} />;
}
