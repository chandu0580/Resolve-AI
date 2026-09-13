import Link from "next/link";
import type { ButtonHTMLAttributes, ElementType, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-brand-600 text-white border-brand-600 hover:bg-brand-700 disabled:bg-brand-600/60 disabled:border-transparent",
  secondary: "bg-surface text-ink border-line-strong hover:bg-subtle disabled:text-ink-3",
  ghost: "bg-transparent text-ink-2 border-transparent hover:bg-subtle disabled:text-ink-3",
};

const BASE = "inline-flex items-center justify-center gap-1.5 rounded-md border font-medium whitespace-nowrap transition-colors disabled:cursor-not-allowed";
const SIZES = { sm: "h-7 px-2.5 text-xs", md: "h-9 px-3.5 text-[13px]" };

export function Button({
  variant = "secondary",
  size = "md",
  icon: Icon,
  children,
  className = "",
  type = "button",
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: "sm" | "md"; icon?: ElementType; children: ReactNode }) {
  return (
    <button type={type} className={`${BASE} ${SIZES[size]} ${VARIANTS[variant]} ${className}`} {...rest}>
      {Icon ? <Icon className="size-4 shrink-0" aria-hidden="true" /> : null}
      {children}
    </button>
  );
}

export function ButtonLink({
  href,
  variant = "secondary",
  size = "md",
  icon: Icon,
  children,
  className = "",
}: {
  href: string;
  variant?: Variant;
  size?: "sm" | "md";
  icon?: ElementType;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Link href={href} className={`${BASE} ${SIZES[size]} ${VARIANTS[variant]} ${className}`}>
      {Icon ? <Icon className="size-4 shrink-0" aria-hidden="true" /> : null}
      {children}
    </Link>
  );
}
