"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";

async function writeClipboard(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* fall through to the textarea fallback (insecure origins, denied permission) */
  }
  try {
    const el = document.createElement("textarea");
    el.value = text;
    el.setAttribute("readonly", "");
    el.style.position = "fixed";
    el.style.opacity = "0";
    document.body.appendChild(el);
    el.select();
    const ok = document.execCommand("copy");
    el.remove();
    return ok;
  } catch {
    return false;
  }
}

export function CopyButton({ text, label, variant = "secondary", size = "md" }: { text: string; label: string; variant?: "primary" | "secondary" | "ghost"; size?: "sm" | "md" }) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");
  return (
    <span className="inline-flex items-center gap-2">
      <Button
        variant={variant}
        size={size}
        icon={state === "copied" ? Check : Copy}
        onClick={async () => {
          setState((await writeClipboard(text)) ? "copied" : "failed");
          window.setTimeout(() => setState("idle"), 2500);
        }}
      >
        {state === "copied" ? "Copied" : label}
      </Button>
      <span aria-live="polite" className="text-xs text-ink-3">
        {state === "failed" ? "Copy failed; select the text manually." : state === "copied" ? <span className="sr-only">Copied to clipboard</span> : null}
      </span>
    </span>
  );
}
