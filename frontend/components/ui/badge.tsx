import type { ElementType, ReactNode } from "react";
import type { Tone } from "@/lib/labels";

export const TONE_CLASSES: Record<Tone, string> = {
  success: "bg-success-bg text-success border-success-line",
  warning: "bg-warning-bg text-warning border-warning-line",
  info: "bg-info-bg text-info border-info-line",
  danger: "bg-danger-bg text-danger border-danger-line",
  neutral: "bg-neutral-bg text-neutral border-neutral-line",
  brand: "bg-brand-50 text-brand-700 border-brand-100",
};

export const TONE_TEXT: Record<Tone, string> = {
  success: "text-success",
  warning: "text-warning",
  info: "text-info",
  danger: "text-danger",
  neutral: "text-neutral",
  brand: "text-brand-700",
};

export function Badge({
  tone = "neutral",
  icon: Icon,
  children,
  className = "",
  title,
  size = "sm",
}: {
  tone?: Tone;
  icon?: ElementType;
  children: ReactNode;
  className?: string;
  title?: string;
  size?: "sm" | "md";
}) {
  const sizing = size === "md" ? "px-2 py-1 text-[13px] gap-1.5" : "px-1.5 py-0.5 text-xs gap-1";
  return (
    <span title={title} className={`inline-flex items-center rounded-md border font-medium whitespace-nowrap ${sizing} ${TONE_CLASSES[tone]} ${className}`}>
      {Icon ? <Icon className={size === "md" ? "size-4 shrink-0" : "size-3.5 shrink-0"} aria-hidden="true" /> : null}
      {children}
    </span>
  );
}
