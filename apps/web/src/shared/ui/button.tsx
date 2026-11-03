import { forwardRef, type ButtonHTMLAttributes } from "react";

import { cn } from "./utils";

export type ButtonVariant = "default" | "outline" | "ghost" | "link" | "destructive";
export type ButtonSize = "default" | "sm" | "lg" | "icon";

export const Button = forwardRef<HTMLButtonElement, ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
}>(({ className, variant = "default", size = "default", type = "button", ...props }, ref) => (
  <button
    ref={ref}
    type={type}
    className={cn("ui-button", `ui-button-${variant}`, `ui-button-${size}`, className)}
    {...props}
  />
));

Button.displayName = "Button";
