"""ResolveAI Golden Evaluation Set Manual Labelling Interface.

A lightweight, high-efficiency local interface for the project owner to genuinely
hand-label the 197 holdout golden examples, fulfilling the Hiver take-home requirement:
"Golden evaluation set - 150-250 hand-labelled examples you built yourself, with a short
note on how you sampled and labelled them."

Key Features:
- Loads data/golden/golden_final.csv (197 examples)
- Human labels saved separately to data/golden/golden_human_labels.csv (preserves AI artifacts)
- Does NOT pre-select or bias human with AI predictions
- Fast keyboard shortcuts:
  * Intents (1-9, 0, -)
  * Escalation (Y/N or E)
  * Escalation Reason (P, R, H, S, L, V)
  * Save & Advance (Enter)
  * Navigation (Left/Right Arrows, U to jump to unrated)
- Atomic auto-save per row with .bak backup
- Pause/resume anytime
- Progress tracking: X / 197, %, remaining count
- Strict validation (reason='none' iff should_escalate=False)
- Generates audit metadata manifest: data/golden/golden_human_labels_manifest.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_GOLDEN_INPUT = ROOT_DIR / "data" / "golden" / "golden_final.csv"
DEFAULT_OUTPUT_LABELS = ROOT_DIR / "data" / "golden" / "golden_human_labels.csv"
DEFAULT_MANIFEST_PATH = ROOT_DIR / "data" / "golden" / "golden_human_labels_manifest.json"

INTENT_TAXONOMY = [
    ("apps_services", "1", "Specific app/service failure (App Store, Music, Safari, Mail, OS feature mechanics, clipboard)"),
    ("performance_crash", "2", "Device/OS-wide freezing, lag, slow, reboot, crash, boot loop"),
    ("battery_power", "3", "Battery drain, won't charge, dies at N%, overheating / warm"),
    ("keyboard_text_bug", "4", "iOS 11 autocorrect bug ('I' -> '[?]', 'it' -> 'I.T'), keyboard glitches"),
    ("connectivity", "5", "Wi-Fi, Bluetooth, cellular, hotspot, AirDrop, accessories / dongle connection"),
    ("data_loss_sync", "6", "Missing photos/notes/contacts, iCloud sync/restore, storage full"),
    ("account_store_repair", "7", "Apple ID, password, 2FA, orders, billing, repair status, Store appointments"),
    ("hardware_damage", "8", "Explicit physical damage/fault: cracked screen, liquid, dead Mac/touch, blown speaker"),
    ("general_complaint", "9", "Support request with no concrete symptom (venting, 'fix it', sarcasm) or taxonomy fallback"),
    ("non_english", "0", "Message not in English"),
    ("other", "-", "Not a support request: thanks, closure ('fixed it'), suggestions, jokes, off-topic")
]

INTENT_NAMES = [it[0] for it in INTENT_TAXONOMY]

ESCALATION_REASONS = [
    ("private_info", "P", "Private identifiers required (serial, Apple ID, order/repair ID, account verification, DM)"),
    ("repeat_contact", "R", "Explicit prior attempts stated ('restarted 3 times', 'tried reset', 'sent DM', '3rd time')"),
    ("hardware", "H", "Explicit physical damage or hardware fault (liquid, broken screen, component failure)"),
    ("safety", "S", "Safety hazard: overheating / smoke / burns, battery swelling, electric shock, self-harm"),
    ("legal_media", "L", "Legal action, lawyer, media/press inquiry, regulatory complaint"),
    ("vague_hostile", "V", "Abusive language with zero actionable symptom (cannot be helped publicly)"),
    ("none", "None", "No escalation required (public reply, clarification question, or standard template is safe)")
]

REASON_NAMES = [r[0] for r in ESCALATION_REASONS]


class GoldenLabelManager:
    """Thread-safe manager for manual golden set annotation."""

    def __init__(
        self,
        input_csv: Path = DEFAULT_GOLDEN_INPUT,
        output_csv: Path = DEFAULT_OUTPUT_LABELS,
        manifest_path: Path = DEFAULT_MANIFEST_PATH
    ):
        self.input_csv = Path(input_csv)
        self.output_csv = Path(output_csv)
        self.manifest_path = Path(manifest_path)
        self._df: pd.DataFrame | None = None
        self.reload()

    def reload(self) -> None:
        if not self.input_csv.exists():
            raise FileNotFoundError(f"Source golden set not found at {self.input_csv}")

        src_df = pd.read_csv(self.input_csv, dtype=str, keep_default_na=False)

        if self.output_csv.exists():
            out_df = pd.read_csv(self.output_csv, dtype=str, keep_default_na=False)
            # Ensure shape matches
            if len(out_df) == len(src_df):
                self._df = out_df
                self._ensure_columns(src_df)
                self._update_manifest()
                return

        # Initialize fresh human labels DataFrame
        df = src_df.copy()
        df["ai_intent_reference"] = df["intent"]
        df["ai_escalate_reference"] = df["should_escalate"]
        df["ai_reason_reference"] = df["escalation_reason"]

        df["intent"] = ""
        df["should_escalate"] = ""
        df["escalation_reason"] = ""
        df["human_annotator"] = ""
        df["annotated_at"] = ""
        df["note"] = ""

        self._df = df
        self._persist()

    def _ensure_columns(self, src_df: pd.DataFrame) -> None:
        assert self._df is not None
        for col in ["intent", "should_escalate", "escalation_reason", "human_annotator", "annotated_at", "note"]:
            if col not in self._df.columns:
                self._df[col] = ""
        if "ai_intent_reference" not in self._df.columns and "intent" in src_df.columns:
            self._df["ai_intent_reference"] = src_df["intent"]
        if "ai_escalate_reference" not in self._df.columns and "should_escalate" in src_df.columns:
            self._df["ai_escalate_reference"] = src_df["should_escalate"]
        if "ai_reason_reference" not in self._df.columns and "escalation_reason" in src_df.columns:
            self._df["ai_reason_reference"] = src_df["escalation_reason"]

    @property
    def total_count(self) -> int:
        return len(self._df) if self._df is not None else 0

    def is_row_completed(self, row: pd.Series) -> bool:
        intent = str(row.get("intent", "")).strip()
        should_esc = str(row.get("should_escalate", "")).strip().lower()
        reason = str(row.get("escalation_reason", "")).strip()

        if intent not in INTENT_NAMES:
            return False
        if should_esc not in ("true", "false"):
            return False
        if should_esc == "false":
            return reason == "none"
        if should_esc == "true":
            return reason in REASON_NAMES and reason != "none"
        return False

    def get_summary(self) -> dict[str, Any]:
        assert self._df is not None
        total = len(self._df)
        completed_mask = [self.is_row_completed(row) for _, row in self._df.iterrows()]
        completed_count = sum(completed_mask)
        remaining = total - completed_count
        pct = round((completed_count / total) * 100.0, 1) if total > 0 else 0.0

        first_unrated = 0
        for idx, done in enumerate(completed_mask):
            if not done:
                first_unrated = idx
                break

        try:
            rel_output = str(self.output_csv.relative_to(ROOT_DIR)).replace("\\", "/")
        except ValueError:
            rel_output = str(self.output_csv).replace("\\", "/")

        return {
            "total": total,
            "completed_count": completed_count,
            "remaining_count": remaining,
            "percent_complete": pct,
            "is_complete": completed_count == total,
            "first_unrated_index": first_unrated,
            "output_path": rel_output
        }

    def get_item(self, index: int) -> dict[str, Any]:
        assert self._df is not None
        if index < 0 or index >= len(self._df):
            raise IndexError(f"Index {index} out of range [0, {len(self._df)-1}]")

        row = self._df.iloc[index]
        completed = self.is_row_completed(row)

        should_esc_val = None
        s_str = str(row.get("should_escalate", "")).strip().lower()
        if s_str == "true":
            should_esc_val = True
        elif s_str == "false":
            should_esc_val = False

        return {
            "index": index,
            "total": len(self._df),
            "gid": str(row.get("gid", f"g{index:03d}")),
            "customer_tweet_id": str(row.get("customer_tweet_id", "")),
            "created_at": str(row.get("created_at", "")),
            "customer_message": str(row.get("customer_message", "")),
            "context": str(row.get("context", "")),
            "brand_reply": str(row.get("brand_reply", "")),
            "n_context_turns": int(row.get("n_context_turns", 0) or 0),
            "current_labels": {
                "intent": str(row.get("intent", "")) or None,
                "should_escalate": should_esc_val,
                "escalation_reason": str(row.get("escalation_reason", "")) or None,
                "note": str(row.get("note", ""))
            },
            "is_completed": completed,
            "ai_reference": {
                "intent": str(row.get("ai_intent_reference", "")),
                "should_escalate": str(row.get("ai_escalate_reference", "")).lower() == "true",
                "escalation_reason": str(row.get("ai_reason_reference", ""))
            },
            "taxonomy": INTENT_TAXONOMY,
            "escalation_reasons": ESCALATION_REASONS
        }

    def save_item(self, index: int, payload: dict[str, Any]) -> dict[str, Any]:
        assert self._df is not None
        if index < 0 or index >= len(self._df):
            raise IndexError(f"Index {index} out of range [0, {len(self._df)-1}]")

        # 1. Validate intent
        intent = str(payload.get("intent", "")).strip()
        if intent not in INTENT_NAMES:
            raise ValueError(f"Invalid intent '{intent}'. Must be one of: {INTENT_NAMES}")

        # 2. Validate should_escalate
        raw_esc = payload.get("should_escalate")
        if isinstance(raw_esc, bool):
            should_esc = raw_esc
        elif isinstance(raw_esc, str) and raw_esc.lower() in ("true", "false"):
            should_esc = raw_esc.lower() == "true"
        else:
            raise ValueError("should_escalate is required and must be boolean True or False")

        # 3. Validate escalation_reason
        reason = str(payload.get("escalation_reason", "")).strip()
        if not should_esc:
            reason = "none"
        else:
            valid_non_none = [r[0] for r in ESCALATION_REASONS if r[0] != "none"]
            if reason not in valid_non_none:
                raise ValueError(f"When should_escalate=True, escalation_reason must be one of {valid_non_none} (got '{reason}')")

        # 4. Note
        note = str(payload.get("note", "")).strip()

        # Update DataFrame
        self._df.at[index, "intent"] = intent
        self._df.at[index, "should_escalate"] = "True" if should_esc else "False"
        self._df.at[index, "escalation_reason"] = reason
        self._df.at[index, "human_annotator"] = "human_owner"
        self._df.at[index, "annotated_at"] = datetime.now(timezone.utc).isoformat()
        self._df.at[index, "note"] = note

        # Persist
        self._persist()
        return self.get_summary()

    def _persist(self) -> None:
        assert self._df is not None
        tmp_path = self.output_csv.with_suffix(".tmp")
        bak_path = self.output_csv.with_suffix(".bak")

        if self.output_csv.exists():
            shutil.copyfile(self.output_csv, bak_path)

        self._df.to_csv(tmp_path, index=False, encoding="utf-8")

        if os.name == "nt":
            if self.output_csv.exists():
                try:
                    self.output_csv.unlink()
                except OSError:
                    pass
            tmp_path.replace(self.output_csv)
        else:
            tmp_path.replace(self.output_csv)

        self._update_manifest()

    def _update_manifest(self) -> None:
        assert self._df is not None
        summary = self.get_summary()

        sha256 = ""
        if self.output_csv.exists():
            h = hashlib.sha256()
            h.update(self.output_csv.read_bytes())
            sha256 = h.hexdigest()

        intent_counts = {}
        escalate_counts = {"True": 0, "False": 0}
        reason_counts = {}

        for _, row in self._df.iterrows():
            if self.is_row_completed(row):
                it = row["intent"]
                esc = row["should_escalate"]
                rs = row["escalation_reason"]
                intent_counts[it] = intent_counts.get(it, 0) + 1
                escalate_counts[esc] = escalate_counts.get(esc, 0) + 1
                reason_counts[rs] = reason_counts.get(rs, 0) + 1

        try:
            rel_target = str(self.output_csv.relative_to(ROOT_DIR)).replace("\\", "/")
        except ValueError:
            rel_target = str(self.output_csv).replace("\\", "/")

        manifest = {
            "dataset_name": "ResolveAI Golden Evaluation Set (Human-Labelled)",
            "annotator": "human owner",
            "schema_version": "v1.2 (human-labelled)",
            "source_split": "temporal holdout (2017-11-28 to 2017-12-03), seed 42",
            "source_file": "data/golden/golden_final.csv",
            "target_file": rel_target,
            "total_rows": summary["total"],
            "completed_rows": summary["completed_count"],
            "remaining_rows": summary["remaining_count"],
            "percent_complete": summary["percent_complete"],
            "is_complete": summary["is_complete"],
            "sha256": sha256,
            "last_updated_utc": datetime.now(timezone.utc).isoformat(),
            "distributions": {
                "intent": intent_counts,
                "should_escalate": escalate_counts,
                "escalation_reason": reason_counts
            }
        }

        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ResolveAI Golden Set Studio - Human Annotation</title>
<style>
:root {
  --bg-app: #0c0f17;
  --bg-card: #141926;
  --bg-card-subtle: #1c2236;
  --bg-hover: #262f49;
  --border: #28324e;
  --border-focus: #4f6ef7;
  --text-main: #e2e8f0;
  --text-muted: #8e9bb3;
  --text-dim: #64748b;
  --accent-blue: #3b82f6;
  --accent-indigo: #6366f1;
  --accent-emerald: #10b981;
  --accent-rose: #f43f5e;
  --accent-amber: #f59e0b;
  --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--bg-app);
  color: var(--text-main);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
header {
  background: rgba(20, 25, 38, 0.95);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--border);
  padding: 0.75rem 1.5rem;
  position: sticky;
  top: 0;
  z-index: 50;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-brand {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.badge-logo {
  background: linear-gradient(135deg, var(--accent-indigo), var(--accent-blue));
  color: white;
  font-weight: 700;
  font-size: 0.8rem;
  padding: 0.25rem 0.6rem;
  border-radius: 6px;
}
.badge-human {
  background: rgba(16, 185, 129, 0.15);
  border: 1px solid var(--accent-emerald);
  color: #34d399;
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  padding: 0.2rem 0.5rem;
  border-radius: 9999px;
}
.header-stats {
  display: flex;
  align-items: center;
  gap: 1.25rem;
}
.stat-count {
  font-size: 0.9rem;
  color: var(--text-muted);
}
.stat-count strong {
  color: var(--text-main);
}
.progress-bar-wrap {
  width: 130px;
  height: 8px;
  background: var(--bg-card-subtle);
  border-radius: 9999px;
  overflow: hidden;
  border: 1px solid var(--border);
}
.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--accent-indigo), var(--accent-emerald));
  width: 0%;
  transition: width 0.3s ease;
}
.btn-secondary {
  background: var(--bg-card-subtle);
  border: 1px solid var(--border);
  color: var(--text-main);
  padding: 0.35rem 0.7rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.8rem;
  font-weight: 500;
  transition: background 0.15s;
}
.btn-secondary:hover { background: var(--bg-hover); }
main {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.25rem;
  padding: 1.25rem;
  max-width: 1600px;
  margin: 0 auto;
  width: 100%;
}
.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.card-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.tag-gid {
  background: var(--bg-card-subtle);
  border: 1px solid var(--border);
  color: var(--accent-blue);
  font-family: var(--font-mono);
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
  font-size: 0.75rem;
}
.message-box {
  background: var(--bg-card-subtle);
  border: 1px solid var(--border);
  border-left: 4px solid var(--accent-blue);
  border-radius: 8px;
  padding: 1rem;
  font-size: 1.05rem;
  line-height: 1.5;
  color: #fff;
  white-space: pre-wrap;
}
.context-box {
  background: rgba(12, 15, 23, 0.6);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.85rem;
  font-size: 0.88rem;
  line-height: 1.45;
  color: var(--text-muted);
  white-space: pre-wrap;
  max-height: 220px;
  overflow-y: auto;
}
.turn-label {
  font-weight: 600;
  color: var(--accent-indigo);
}
.collapsible {
  background: rgba(28, 34, 54, 0.5);
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}
.collapsible-header {
  padding: 0.6rem 0.85rem;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-muted);
  user-select: none;
}
.collapsible-header:hover { background: var(--bg-card-subtle); }
.collapsible-content {
  padding: 0.85rem;
  border-top: 1px solid var(--border);
  font-size: 0.85rem;
  line-height: 1.45;
  color: var(--text-muted);
  display: none;
}
.intent-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.4rem;
}
.intent-btn {
  background: var(--bg-card-subtle);
  border: 1px solid var(--border);
  color: var(--text-main);
  padding: 0.6rem 0.75rem;
  border-radius: 6px;
  cursor: pointer;
  text-align: left;
  display: flex;
  align-items: center;
  gap: 0.6rem;
  font-size: 0.84rem;
  transition: all 0.15s;
}
.intent-btn:hover { background: var(--bg-hover); border-color: var(--accent-blue); }
.intent-btn.selected {
  background: rgba(59, 130, 246, 0.2);
  border-color: var(--accent-blue);
  color: white;
  font-weight: 600;
}
.key-badge {
  background: var(--bg-app);
  border: 1px solid var(--border);
  font-family: var(--font-mono);
  font-size: 0.72rem;
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
  color: var(--text-dim);
  font-weight: bold;
}
.intent-btn.selected .key-badge {
  background: var(--accent-blue);
  color: white;
  border-color: var(--accent-blue);
}
.escalate-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.6rem;
}
.esc-card {
  background: var(--bg-card-subtle);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.8rem;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  transition: all 0.15s;
}
.esc-card:hover { background: var(--bg-hover); }
.esc-card.selected-no {
  background: rgba(16, 185, 129, 0.18);
  border-color: var(--accent-emerald);
  color: white;
}
.esc-card.selected-yes {
  background: rgba(244, 63, 94, 0.18);
  border-color: var(--accent-rose);
  color: white;
}
.esc-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 0.92rem;
  font-weight: 600;
}
.esc-desc {
  font-size: 0.75rem;
  color: var(--text-dim);
}
.esc-card.selected-no .esc-desc, .esc-card.selected-yes .esc-desc {
  color: var(--text-muted);
}
.reason-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.4rem;
  opacity: 0.35;
  pointer-events: none;
  transition: opacity 0.2s;
}
.reason-grid.enabled {
  opacity: 1;
  pointer-events: auto;
}
.reason-btn {
  background: var(--bg-card-subtle);
  border: 1px solid var(--border);
  color: var(--text-main);
  padding: 0.5rem 0.65rem;
  border-radius: 6px;
  cursor: pointer;
  text-align: left;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.8rem;
  transition: all 0.15s;
}
.reason-btn:hover { background: var(--bg-hover); border-color: var(--accent-rose); }
.reason-btn.selected {
  background: rgba(244, 63, 94, 0.2);
  border-color: var(--accent-rose);
  color: white;
  font-weight: 600;
}
.reason-btn.selected .key-badge {
  background: var(--accent-rose);
  color: white;
  border-color: var(--accent-rose);
}
textarea.notes-input {
  width: 100%;
  background: var(--bg-card-subtle);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0.6rem;
  color: var(--text-main);
  font-family: inherit;
  font-size: 0.85rem;
  resize: vertical;
  min-height: 50px;
}
textarea.notes-input:focus {
  outline: none;
  border-color: var(--border-focus);
}
.footer-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 0.5rem;
}
.btn-nav {
  background: var(--bg-card-subtle);
  border: 1px solid var(--border);
  color: var(--text-main);
  padding: 0.55rem 1rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}
.btn-nav:hover { background: var(--bg-hover); }
.btn-save {
  background: var(--accent-blue);
  border: 1px solid var(--accent-blue);
  color: white;
  padding: 0.55rem 1.4rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 600;
  transition: all 0.15s;
}
.btn-save:hover { filter: brightness(1.1); }
.btn-save:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  filter: none;
}
.banner-complete {
  grid-column: 1 / -1;
  background: rgba(16, 185, 129, 0.15);
  border: 1px solid var(--accent-emerald);
  border-radius: 8px;
  padding: 1rem 1.5rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #34d399;
  font-size: 0.95rem;
}
.shortcuts-modal {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.7);
  display: none;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.modal-content {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1.5rem;
  max-width: 600px;
  width: 90%;
  max-height: 80vh;
  overflow-y: auto;
}
.rule-row {
  margin-bottom: 0.75rem;
  font-size: 0.85rem;
  color: var(--text-muted);
}
.rule-row strong { color: var(--text-main); }
</style>
</head>
<body>

<header>
  <div class="header-brand">
    <span class="badge-logo">RESOLVE AI</span>
    <span style="font-weight:600; font-size:1rem;">Golden Set Studio</span>
    <span class="badge-human">Human Ground Truth</span>
  </div>
  <div class="header-stats">
    <div class="stat-count">
      Progress: <strong id="progress-text">0 / 197</strong> (<span id="progress-pct">0%</span>)
      &bull; Remaining: <strong id="remaining-count" style="color:var(--accent-amber);">197</strong>
    </div>
    <div class="progress-bar-wrap">
      <div class="progress-bar-fill" id="progress-fill"></div>
    </div>
    <button class="btn-secondary" onclick="jumpToUnrated()">Jump Unrated [U]</button>
    <button class="btn-secondary" onclick="toggleHelp()">Guidelines [?]</button>
  </div>
</header>

<main id="main-content">
  <!-- Left: Customer Conversation -->
  <div class="card">
    <div class="card-title">
      <span>Incoming Message</span>
      <div>
        <span class="tag-gid" id="item-gid">g000</span>
        <span style="font-size:0.75rem; color:var(--text-dim); margin-left:0.5rem;" id="item-created-at"></span>
      </div>
    </div>

    <div class="message-box" id="item-message">Loading customer message...</div>

    <div id="context-container" style="display:none;">
      <div class="card-title" style="font-size:0.8rem; margin-top:0.25rem;">
        <span>Prior Thread Context</span>
      </div>
      <div class="context-box" id="item-context"></div>
    </div>

    <!-- Collapsible Brand Reply -->
    <div class="collapsible">
      <div class="collapsible-header" onclick="toggleCollapse(this)">
        <span>Historical Brand Reply (for reference)</span>
        <span style="font-size:0.75rem;">▼</span>
      </div>
      <div class="collapsible-content" id="item-brand-reply"></div>
    </div>

    <!-- Collapsible AI Reference (Audit only, never anchors) -->
    <div class="collapsible">
      <div class="collapsible-header" onclick="toggleCollapse(this)">
        <span style="color:var(--text-dim);">Audit Reference (Prior AI Pass - hidden to prevent bias)</span>
        <span style="font-size:0.75rem;">▼</span>
      </div>
      <div class="collapsible-content" id="item-ai-ref" style="font-family:var(--font-mono); font-size:0.78rem;"></div>
    </div>
  </div>

  <!-- Right: Decision Panel -->
  <div class="card">
    <div class="card-title">
      <span>1. Assign Intent (Press 1-9, 0, -)</span>
      <span style="font-size:0.75rem; color:var(--text-dim);">Required</span>
    </div>
    <div class="intent-grid" id="intent-buttons"></div>

    <div class="card-title" style="margin-top:0.5rem;">
      <span>2. Escalation Required? (Press N or Y)</span>
      <span style="font-size:0.75rem; color:var(--text-dim);">Required</span>
    </div>
    <div class="escalate-row">
      <div class="esc-card" id="esc-no" onclick="selectEscalate(false)">
        <div class="esc-title">
          <span style="color:#34d399;">No Escalation</span>
          <span class="key-badge">N</span>
        </div>
        <div class="esc-desc">Public bot troubleshooting, clarification, or template.</div>
      </div>
      <div class="esc-card" id="esc-yes" onclick="selectEscalate(true)">
        <div class="esc-title">
          <span style="color:#fb7185;">Yes - Escalate</span>
          <span class="key-badge">Y / E</span>
        </div>
        <div class="esc-desc">Private info needed, repeat contact, hardware damage, safety.</div>
      </div>
    </div>

    <div class="card-title" style="margin-top:0.5rem;">
      <span>3. Escalation Reason (when Escalate = Yes)</span>
      <span style="font-size:0.75rem; color:var(--text-dim);" id="reason-req-label">Disabled</span>
    </div>
    <div class="reason-grid" id="reason-buttons"></div>

    <div style="display:flex; flex-direction:column; gap:0.35rem; margin-top:0.25rem;">
      <label style="font-size:0.78rem; font-weight:600; color:var(--text-dim);">Optional Note:</label>
      <textarea class="notes-input" id="item-note" placeholder="Edge case reason, ambiguity, or notes..."></textarea>
    </div>

    <div class="footer-actions">
      <div style="display:flex; gap:0.5rem;">
        <button class="btn-nav" onclick="navPrev()">← Prev [ [ ]</button>
        <button class="btn-nav" onclick="navNext()">Next [ ] ] →</button>
      </div>
      <button class="btn-save" id="btn-save" onclick="saveCurrent()" disabled>Save & Next [Enter]</button>
    </div>
  </div>
</main>

<div class="shortcuts-modal" id="help-modal" onclick="if(event.target===this) toggleHelp()">
  <div class="modal-content">
    <h3 style="margin-bottom:1rem; font-size:1.1rem; color:white;">Annotation Rules & Guidelines (v1.1)</h3>
    <div class="rule-row"><strong>R1 (Repeat Contact):</strong> Escalate ONLY if the customer states prior attempts ('tried resets', 'restarted 3 times', 'sent DM', '3rd time contacting'). Vague phrases like 'nothing works' or problem recurring do NOT count.</div>
    <div class="rule-row"><strong>R2 (App vs Device-wide):</strong> Failure confined to one named app -> <code>apps_services</code>. Device-wide freeze/reboot/crash -> <code>performance_crash</code>.</div>
    <div class="rule-row"><strong>R3 (Accessories):</strong> Accessory connection/pairing -> <code>connectivity</code>. Accessory won't charge -> <code>battery_power</code>. Hardware damage requires explicit physical fault (cracked, smoke, liquid).</div>
    <div class="rule-row"><strong>R4 (Taxonomy Gaps):</strong> If no intent genuinely fits a support request, use <code>general_complaint</code>.</div>
    <div class="rule-row"><strong>R5 (Unseen Attachments):</strong> Label from words alone. If symptom is only in an attachment/screenshot, default to <code>general_complaint</code>. Exception: iOS 11 corrupted 'I' glyph in text = <code>keyboard_text_bug</code>.</div>
    <div class="rule-row"><strong>R6 (Priority when Multiple):</strong> Primary intent is the main blocker or requested resolution. Reason priority: safety > legal_media > private_info > hardware > repeat_contact > vague_hostile.</div>
    <button class="btn-secondary" style="margin-top:1rem; width:100%;" onclick="toggleHelp()">Close</button>
  </div>
</div>

<script>
let currentIndex = 0;
let currentItem = null;
let selectedIntent = null;
let selectedEscalate = null;
let selectedReason = null;

const INTENTS = """ + json.dumps(INTENT_TAXONOMY) + """;
const REASONS = """ + json.dumps(ESCALATION_REASONS) + """;

function init() {
  buildButtons();
  loadSummary();
  loadItem(0);
}

function buildButtons() {
  const iGrid = document.getElementById('intent-buttons');
  iGrid.innerHTML = INTENTS.map(([name, key, desc]) => `
    <button class="intent-btn" id="btn-intent-${name}" onclick="selectIntent('${name}')" title="${desc}">
      <span class="key-badge">${key}</span>
      <span>${name}</span>
    </button>
  `).join('');

  const rGrid = document.getElementById('reason-buttons');
  rGrid.innerHTML = REASONS.filter(r => r[0] !== 'none').map(([name, key, desc]) => `
    <button class="reason-btn" id="btn-reason-${name}" onclick="selectReason('${name}')" title="${desc}">
      <span class="key-badge">${key}</span>
      <span>${name}</span>
    </button>
  `).join('');
}

async function loadSummary() {
  try {
    const res = await fetch('/api/summary');
    const s = await res.json();
    document.getElementById('progress-text').innerText = `${s.completed_count} / ${s.total}`;
    document.getElementById('progress-pct').innerText = `${s.percent_complete}%`;
    document.getElementById('remaining-count').innerText = s.remaining_count;
    document.getElementById('progress-fill').style.width = `${s.percent_complete}%`;
    if (s.is_complete) {
      document.getElementById('remaining-count').style.color = 'var(--accent-emerald)';
    }
  } catch(e) { console.error(e); }
}

async function loadItem(index) {
  try {
    const res = await fetch(`/api/item?index=${index}`);
    if (!res.ok) return;
    const data = await res.json();
    currentIndex = index;
    currentItem = data;

    document.getElementById('item-gid').innerText = data.gid;
    document.getElementById('item-created-at').innerText = data.created_at;
    document.getElementById('item-message').innerText = data.customer_message;

    if (data.context && data.context.trim()) {
      document.getElementById('context-container').style.display = 'block';
      document.getElementById('item-context').innerText = data.context;
    } else {
      document.getElementById('context-container').style.display = 'none';
    }

    document.getElementById('item-brand-reply').innerText = data.brand_reply || 'None available';
    document.getElementById('item-ai-ref').innerText = 
      `AI Intent: ${data.ai_reference.intent}\\nAI Escalate: ${data.ai_reference.should_escalate} (${data.ai_reference.escalation_reason})`;

    document.getElementById('item-note').value = data.current_labels.note || '';

    // Reset selection state to current labels
    selectIntent(data.current_labels.intent, false);
    selectEscalate(data.current_labels.should_escalate, false);
    if (data.current_labels.should_escalate) {
      selectReason(data.current_labels.escalation_reason, false);
    } else {
      selectReason(null, false);
    }
    validateForm();
  } catch(e) { console.error(e); }
}

function selectIntent(intent, userAction = true) {
  selectedIntent = intent;
  document.querySelectorAll('.intent-btn').forEach(b => b.classList.remove('selected'));
  if (intent) {
    const el = document.getElementById(`btn-intent-${intent}`);
    if (el) el.classList.add('selected');
  }
  validateForm();
}

function selectEscalate(val, userAction = true) {
  selectedEscalate = val;
  const noCard = document.getElementById('esc-no');
  const yesCard = document.getElementById('esc-yes');
  const rGrid = document.getElementById('reason-buttons');
  const rLabel = document.getElementById('reason-req-label');

  noCard.classList.remove('selected-no');
  yesCard.classList.remove('selected-yes');

  if (val === false) {
    noCard.classList.add('selected-no');
    rGrid.classList.remove('enabled');
    rLabel.innerText = 'Auto: none';
    selectedReason = 'none';
    document.querySelectorAll('.reason-btn').forEach(b => b.classList.remove('selected'));
  } else if (val === true) {
    yesCard.classList.add('selected-yes');
    rGrid.classList.add('enabled');
    rLabel.innerText = 'Required';
    if (selectedReason === 'none') selectedReason = null;
  } else {
    rGrid.classList.remove('enabled');
    rLabel.innerText = 'Disabled';
    selectedReason = null;
  }
  validateForm();
}

function selectReason(reason, userAction = true) {
  selectedReason = reason;
  document.querySelectorAll('.reason-btn').forEach(b => b.classList.remove('selected'));
  if (reason && reason !== 'none') {
    const el = document.getElementById(`btn-reason-${reason}`);
    if (el) el.classList.add('selected');
  }
  validateForm();
}

function validateForm() {
  const saveBtn = document.getElementById('btn-save');
  let valid = true;
  if (!selectedIntent) valid = false;
  if (selectedEscalate === null || selectedEscalate === undefined) valid = false;
  if (selectedEscalate === true && (!selectedReason || selectedReason === 'none')) valid = false;
  saveBtn.disabled = !valid;
}

async function saveCurrent() {
  if (!selectedIntent || selectedEscalate === null) return;
  if (selectedEscalate === true && (!selectedReason || selectedReason === 'none')) return;

  const payload = {
    intent: selectedIntent,
    should_escalate: selectedEscalate,
    escalation_reason: selectedEscalate ? selectedReason : 'none',
    note: document.getElementById('item-note').value.trim()
  };

  try {
    const res = await fetch(`/api/save?index=${currentIndex}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      await loadSummary();
      navNext();
    }
  } catch(e) { console.error(e); }
}

function navPrev() {
  if (currentIndex > 0) loadItem(currentIndex - 1);
}

function navNext() {
  if (currentIndex < (currentItem?.total || 197) - 1) {
    loadItem(currentIndex + 1);
  }
}

async function jumpToUnrated() {
  const res = await fetch('/api/summary');
  const s = await res.json();
  loadItem(s.first_unrated_index);
}

function toggleCollapse(el) {
  const content = el.nextElementSibling;
  const arrow = el.querySelector('span:last-child');
  if (content.style.display === 'block') {
    content.style.display = 'none';
    arrow.innerText = '▼';
  } else {
    content.style.display = 'block';
    arrow.innerText = '▲';
  }
}

function toggleHelp() {
  const m = document.getElementById('help-modal');
  m.style.display = m.style.display === 'flex' ? 'none' : 'flex';
}

// Global hotkeys
document.addEventListener('keydown', (e) => {
  // If user is typing in notes textarea, don't trigger intent hotkeys
  if (e.target.tagName.toLowerCase() === 'textarea' || e.target.tagName.toLowerCase() === 'input') {
    if (e.key === 'Enter' && e.ctrlKey) {
      e.preventDefault();
      saveCurrent();
    }
    return;
  }

  // Intent hotkeys
  const keyMap = {
    '1': 'apps_services', '2': 'performance_crash', '3': 'battery_power',
    '4': 'keyboard_text_bug', '5': 'connectivity', '6': 'data_loss_sync',
    '7': 'account_store_repair', '8': 'hardware_damage', '9': 'general_complaint',
    '0': 'non_english', '-': 'other'
  };
  if (keyMap[e.key]) {
    e.preventDefault();
    selectIntent(keyMap[e.key]);
    return;
  }

  // Escalation hotkeys
  if (e.key === 'n' || e.key === 'N') {
    e.preventDefault();
    selectEscalate(false);
    return;
  }
  if (e.key === 'y' || e.key === 'Y' || e.key === 'e' || e.key === 'E') {
    e.preventDefault();
    selectEscalate(true);
    return;
  }

  // Reason hotkeys (when Escalate = Yes)
  if (selectedEscalate === true) {
    const rMap = {
      'p': 'private_info', 'P': 'private_info',
      'r': 'repeat_contact', 'R': 'repeat_contact',
      'h': 'hardware', 'H': 'hardware',
      's': 'safety', 'S': 'safety',
      'l': 'legal_media', 'L': 'legal_media',
      'v': 'vague_hostile', 'V': 'vague_hostile'
    };
    if (rMap[e.key]) {
      e.preventDefault();
      selectReason(rMap[e.key]);
      return;
    }
  }

  // Navigation
  if (e.key === 'Enter') {
    e.preventDefault();
    const btn = document.getElementById('btn-save');
    if (!btn.disabled) saveCurrent();
    return;
  }
  if (e.key === 'ArrowLeft' || e.key === '[') {
    e.preventDefault();
    navPrev();
    return;
  }
  if (e.key === 'ArrowRight' || e.key === ']') {
    e.preventDefault();
    navNext();
    return;
  }
  if (e.key === 'u' || e.key === 'U') {
    e.preventDefault();
    jumpToUnrated();
    return;
  }
  if (e.key === '?') {
    e.preventDefault();
    toggleHelp();
    return;
  }
});

window.onload = init;
</script>
</body>
</html>
"""


class GoldenLabelRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the Golden Set labelling application."""

    manager: GoldenLabelManager | None = None

    def _send_json(self, data: Any, status: int = HTTPStatus.OK) -> None:
        raw = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)

    def _send_html(self, html: str, status: int = HTTPStatus.OK) -> None:
        raw = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        assert self.manager is not None
        parsed = urlparse(self.path)

        if parsed.path in ("/", "/index.html"):
            self._send_html(HTML_TEMPLATE)
            return

        if parsed.path == "/api/summary":
            self._send_json(self.manager.get_summary())
            return

        if parsed.path == "/api/item":
            qs = parse_qs(parsed.query)
            idx_str = qs.get("index", ["0"])[0]
            try:
                idx = int(idx_str)
                item = self.manager.get_item(idx)
                self._send_json(item)
            except (ValueError, IndexError) as e:
                self._send_json({"error": str(e)}, status=HTTPStatus.BAD_REQUEST)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        assert self.manager is not None
        parsed = urlparse(self.path)

        if parsed.path == "/api/save":
            qs = parse_qs(parsed.query)
            idx_str = qs.get("index", ["0"])[0]
            try:
                idx = int(idx_str)
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8")
                payload = json.loads(body)
                summary = self.manager.save_item(idx, payload)
                self._send_json(summary)
            except Exception as e:
                self._send_json({"error": str(e)}, status=HTTPStatus.BAD_REQUEST)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def log_message(self, format: str, *args: Any) -> None:
        # Quieter logging
        pass


def run_server(
    host: str = "127.0.0.1",
    port: int = 8766,
    input_csv: Path = DEFAULT_GOLDEN_INPUT,
    output_csv: Path = DEFAULT_OUTPUT_LABELS,
    manifest_path: Path = DEFAULT_MANIFEST_PATH
) -> None:
    mgr = GoldenLabelManager(input_csv=input_csv, output_csv=output_csv, manifest_path=manifest_path)
    summary = mgr.get_summary()

    print("=" * 72)
    print("✨ RESOLVEAI GOLDEN SET LABELLING STUDIO ✨")
    print(f"Server address:   http://{host}:{port}")
    print(f"Target file:      {output_csv}")
    print(f"Audit manifest:   {manifest_path}")
    print(f"Total examples:   {summary['total']}")
    print(f"Completed:        {summary['completed_count']} ({summary['percent_complete']}%)")
    print(f"Remaining:        {summary['remaining_count']}")
    print("=" * 72)

    GoldenLabelRequestHandler.manager = mgr
    server = ThreadingHTTPServer((host, port), GoldenLabelRequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStudio stopped. Your progress has been saved.")
    finally:
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ResolveAI Golden Set Manual Labelling Studio")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8766, help="Port to listen on (default: 8766)")
    parser.add_argument("--input", type=Path, default=DEFAULT_GOLDEN_INPUT, help="Source golden CSV")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_LABELS, help="Target human labels CSV")
    args = parser.parse_args()

    run_server(host=args.host, port=args.port, input_csv=args.input, output_csv=args.output)
