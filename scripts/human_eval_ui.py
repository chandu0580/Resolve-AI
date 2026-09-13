"""Local, blinded human-evaluation interface for ResolveAI's 50-example judge validation packet.

Requirements:
- Loads data/human_eval/human_scoring_packet.csv
- Reviewer is strictly BLINDED (no system names, model names, baseline names, or golden labels)
- One example at a time: conversation, available evidence, candidate response
- Collects: groundedness (1-5), relevance (1-5), actionability (1-5), completeness (1-5),
  policy_compliance (1-5), tone (1-5), hallucination (0/1), policy_violation (0/1), notes (str)
- Progress tracking (0/50), next, previous, jump to unrated, resume support, auto-save
- Safe atomic persistence with backup
- Completion banner instructing: python scripts/evaluate.py --cached
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pandas as pd

DEFAULT_PACKET_PATH = Path("data/human_eval/human_scoring_packet.csv")
ORDINAL_DIMS = ("groundedness", "relevance", "actionability", "completeness", "policy_compliance", "tone")
BINARY_DIMS = ("hallucination", "policy_violation")
ALL_HUMAN_COLS = [f"human_{d}" for d in ORDINAL_DIMS + BINARY_DIMS] + ["human_notes"]

RUBRIC_GUIDE = {
    "groundedness": {
        "title": "Groundedness",
        "question": "Is every factual or actionable claim in the response supported by the evidence shown (or by the customer's own words)?",
        "anchors": {
            "5": "Every claim, step and fact appears in evidence or customer message (questions / handoffs asserting nothing = 5)",
            "4": "All substantive claims supported; minor harmless phrasing",
            "3": "Main step supported, but secondary detail (version, menu path) is unsupported",
            "2": "Main step unsupported; response is plausible but unverified",
            "1": "Contradicts evidence or asserts specific facts with no evidence"
        }
    },
    "relevance": {
        "title": "Relevance",
        "question": "Does the response address the issue the customer actually raised (including thread context)?",
        "anchors": {
            "5": "Addresses exactly the stated issue and nothing else",
            "4": "Addresses the issue with minor generic filler",
            "3": "Addresses general topic area but not specific symptom",
            "2": "Mostly off-target; only generic acknowledgment",
            "1": "Answers a different problem or ignores the message"
        }
    },
    "actionability": {
        "title": "Actionability",
        "question": "Does the customer get a useful next step?",
        "anchors": {
            "5": "Concrete, complete step to do now (or exact missing detail asked / concrete handoff stated)",
            "4": "Concrete step with small gap (path shortened, 'see our support site')",
            "3": "Generic step ('update', 'restart') or partial question",
            "2": "Only reassurance or vague 'we will look into it'",
            "1": "Nothing actionable or impossible action"
        }
    },
    "completeness": {
        "title": "Completeness",
        "question": "Does the response cover what could reasonably be answered from the evidence and the message?",
        "anchors": {
            "5": "Covers the fix (or right question/handoff) plus needed caveat (back up first, which version)",
            "4": "Covers fix; minor caveat missing",
            "3": "Covers part of what evidence supports; needs another turn",
            "2": "Answers a small fragment of what was askable",
            "1": "Omits answerable content entirely"
        }
    },
    "policy_compliance": {
        "title": "Policy Compliance",
        "question": "Obeys support policy: no refund/replacement promises, no private IDs in public, no URLs/@handles, escalates when required?",
        "anchors": {
            "5": "Fully compliant and escalate/answer choice is right for the case",
            "4": "Compliant; escalate/answer choice is defensible",
            "3": "One minor policy slip (asks for device detail, soft promise)",
            "2": "Clear slip: public troubleshooting where handoff was required",
            "1": "Asks private IDs publicly, promises refund/replacement, or answers safety/legal/abuse routinely"
        }
    },
    "tone": {
        "title": "Tone",
        "question": "Is it concise, professional and appropriate for the brand on a public channel?",
        "anchors": {
            "5": "Concise, warm, brand-appropriate, no filler",
            "4": "Appropriate with slight verbosity or stiffness",
            "3": "Acceptable but templated, curt, or padded",
            "2": "Inappropriate register (defensive, sarcastic) or far too long",
            "1": "Rude, dismissive, or unreadable"
        }
    },
    "hallucination": {
        "title": "Hallucination",
        "question": "Does the response invent a fact, action, policy, product detail or step NOT in evidence and NOT in customer message?",
        "anchors": {
            "0": "No (fully grounded or unassertive)",
            "1": "Yes (at least one invented claim or unsupported fact)"
        }
    },
    "policy_violation": {
        "title": "Policy Violation",
        "question": "Does the response break a hard policy rule (private ID requested, refund promise, URL, public safety/abuse reply)?",
        "anchors": {
            "0": "No (safe and compliant)",
            "1": "Yes (breaks hard brand/escalation boundary)"
        }
    }
}


class PacketManager:
    """Thread-safe manager for the blinded evaluation packet."""

    def __init__(self, packet_path: Path = DEFAULT_PACKET_PATH):
        self.packet_path = packet_path
        self._df: pd.DataFrame | None = None
        self.reload()

    def reload(self) -> None:
        if not self.packet_path.exists():
            raise FileNotFoundError(f"Packet file not found at {self.packet_path}")
        df = pd.read_csv(self.packet_path, dtype=str, keep_default_na=False)
        # Ensure all human columns exist
        for col in ALL_HUMAN_COLS:
            if col not in df.columns:
                df[col] = ""
        self._df = df

    @property
    def total_count(self) -> int:
        return len(self._df) if self._df is not None else 0

    def verify_blinding(self) -> bool:
        """Confirms that no unblinded system or model attributes exist in the loaded data."""
        forbidden = ["system", "model", "judge_model", "expected", "golden", "stratum", "should_escalate"]
        cols = [c.lower() for c in (self._df.columns if self._df is not None else [])]
        for f in forbidden:
            if f in cols:
                return False
        return True

    def get_summary(self) -> dict[str, Any]:
        assert self._df is not None
        req_cols = [f"human_{d}" for d in ORDINAL_DIMS + BINARY_DIMS]
        # A row is rated if all 8 required rating fields are non-empty
        filled_mask = self._df[req_cols].apply(lambda row: all(str(val).strip() != "" for val in row), axis=1)
        rated_count = int(filled_mask.sum())
        total = len(self._df)

        item_statuses = []
        for idx in range(total):
            row = self._df.iloc[idx]
            is_rated = all(str(row[c]).strip() != "" for c in req_cols)
            item_statuses.append({
                "index": idx,
                "example_id": str(row["example_id"]),
                "is_rated": bool(is_rated)
            })

        first_unrated = next((i for i, s in enumerate(item_statuses) if not s["is_rated"]), None)
        is_complete = (rated_count == total)

        return {
            "total": total,
            "rated_count": rated_count,
            "unrated_count": total - rated_count,
            "percent_complete": round((rated_count / total * 100) if total else 0.0, 1),
            "is_complete": is_complete,
            "first_unrated_index": first_unrated,
            "item_statuses": item_statuses,
            "completion_command": "python scripts/evaluate.py --cached" if is_complete else None
        }

    def get_item(self, index: int) -> dict[str, Any]:
        assert self._df is not None
        if index < 0 or index >= len(self._df):
            raise IndexError(f"Index {index} out of range [0, {len(self._df)-1}]")

        row = self._df.iloc[index]
        req_cols = [f"human_{d}" for d in ORDINAL_DIMS + BINARY_DIMS]
        is_rated = all(str(row[c]).strip() != "" for c in req_cols)

        ratings = {}
        for d in ORDINAL_DIMS:
            val = str(row.get(f"human_{d}", "")).strip()
            ratings[d] = int(val) if val.isdigit() else None
        for d in BINARY_DIMS:
            val = str(row.get(f"human_{d}", "")).strip()
            ratings[d] = int(val) if val in ("0", "1") else None
        ratings["notes"] = str(row.get("human_notes", ""))

        return {
            "index": index,
            "total": len(self._df),
            "example_id": str(row["example_id"]),
            "conversation": str(row["conversation"]),
            "evidence": str(row["evidence"]),
            "candidate_response": str(row["candidate_response"]),
            "ratings": ratings,
            "is_rated": is_rated,
            "rubric_guide": RUBRIC_GUIDE
        }

    def save_item(self, index: int, ratings: dict[str, Any]) -> dict[str, Any]:
        assert self._df is not None
        if index < 0 or index >= len(self._df):
            raise IndexError(f"Index {index} out of range [0, {len(self._df)-1}]")

        # Validation
        for d in ORDINAL_DIMS:
            if d in ratings and ratings[d] is not None:
                val = int(ratings[d])
                if val < 1 or val > 5:
                    raise ValueError(f"{d} must be between 1 and 5 (got {val})")
                self._df.at[index, f"human_{d}"] = str(val)

        for d in BINARY_DIMS:
            if d in ratings and ratings[d] is not None:
                val = int(ratings[d])
                if val not in (0, 1):
                    raise ValueError(f"{d} must be 0 or 1 (got {val})")
                self._df.at[index, f"human_{d}"] = str(val)

        if "notes" in ratings:
            self._df.at[index, "human_notes"] = str(ratings["notes"] or "")

        # Atomic persistence with backup
        self._persist()
        return self.get_summary()

    def _persist(self) -> None:
        assert self._df is not None
        # Write to temporary file first
        tmp_path = self.packet_path.with_suffix(".tmp")
        bak_path = self.packet_path.with_suffix(".bak")

        # If original exists, ensure backup
        if self.packet_path.exists() and not bak_path.exists():
            shutil.copyfile(self.packet_path, bak_path)

        self._df.to_csv(tmp_path, index=False, encoding="utf-8")

        # Replace target
        if os.name == "nt":
            # On Windows, replace requires target removal or atomic replace
            if self.packet_path.exists():
                # Keep latest backup
                shutil.copyfile(self.packet_path, bak_path)
            tmp_path.replace(self.packet_path)
        else:
            tmp_path.replace(self.packet_path)


def render_html() -> str:
    """Returns the single-page application HTML with embedded CSS and JS."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ResolveAI — Human Evaluation (Blinded Review)</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {
  --bg-main: #0c0f17;
  --bg-card: #141926;
  --bg-card-subtle: #1a2234;
  --bg-input: #0e1320;
  --border-subtle: #242f47;
  --border-focus: #3b82f6;
  --text-main: #f1f5f9;
  --text-muted: #94a3b8;
  --text-dim: #64748b;
  --accent-blue: #38bdf8;
  --accent-indigo: #6366f1;
  --accent-emerald: #10b981;
  --accent-amber: #f59e0b;
  --accent-rose: #f43f5e;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  background-color: var(--bg-main);
  color: var(--text-main);
  line-height: 1.5;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
header {
  background: rgba(20, 25, 38, 0.85);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border-subtle);
  padding: 0.85rem 1.5rem;
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
.logo-badge {
  background: linear-gradient(135deg, var(--accent-indigo), var(--accent-blue));
  color: white;
  font-weight: 700;
  font-size: 0.8rem;
  padding: 0.25rem 0.6rem;
  border-radius: 6px;
  letter-spacing: 0.05em;
}
.header-title {
  font-size: 1.05rem;
  font-weight: 600;
  color: var(--text-main);
}
.blind-pill {
  background: rgba(245, 158, 11, 0.12);
  border: 1px solid rgba(245, 158, 11, 0.35);
  color: #fbbf24;
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  padding: 0.2rem 0.55rem;
  border-radius: 9999px;
  letter-spacing: 0.04em;
}
.header-progress {
  display: flex;
  align-items: center;
  gap: 1.25rem;
}
.progress-stat {
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--text-muted);
}
.progress-stat span {
  color: var(--text-main);
}
.progress-bar-container {
  width: 140px;
  height: 8px;
  background: var(--bg-card-subtle);
  border-radius: 9999px;
  overflow: hidden;
  border: 1px solid var(--border-subtle);
}
.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--accent-indigo), var(--accent-emerald));
  width: 0%;
  transition: width 0.3s ease;
}
.btn-drawer {
  background: var(--bg-card-subtle);
  border: 1px solid var(--border-subtle);
  color: var(--text-main);
  padding: 0.4rem 0.75rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.82rem;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  transition: all 0.2s;
}
.btn-drawer:hover {
  background: var(--border-subtle);
}
main {
  flex: 1;
  display: grid;
  grid-template-columns: 1.15fr 0.85fr;
  gap: 1.5rem;
  padding: 1.5rem;
  max-width: 1600px;
  margin: 0 auto;
  width: 100%;
}
@media (max-width: 1024px) {
  main { grid-template-columns: 1fr; }
}
.panel {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}
.card {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  padding: 1.25rem;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.85rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  padding-bottom: 0.5rem;
}
.card-title {
  font-size: 0.85rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.badge-id {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  background: var(--bg-card-subtle);
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  color: var(--accent-blue);
  border: 1px solid var(--border-subtle);
}
/* Conversation Thread */
.thread-container {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  max-height: 280px;
  overflow-y: auto;
  padding-right: 0.25rem;
}
.turn-bubble {
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  font-size: 0.9rem;
}
.turn-customer {
  background: rgba(56, 189, 248, 0.08);
  border-left: 3px solid var(--accent-blue);
}
.turn-brand {
  background: rgba(99, 102, 241, 0.08);
  border-left: 3px solid var(--accent-indigo);
}
.turn-role {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--text-dim);
  margin-bottom: 0.15rem;
}
.turn-text {
  color: var(--text-main);
  white-space: pre-wrap;
}
/* Evidence box */
.evidence-container {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  max-height: 250px;
  overflow-y: auto;
  padding-right: 0.25rem;
}
.evidence-item {
  background: var(--bg-card-subtle);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 0.65rem 0.85rem;
  font-size: 0.85rem;
}
.evidence-tag {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--accent-emerald);
  margin-bottom: 0.2rem;
}
.evidence-turn {
  margin-bottom: 0.35rem;
}
.evidence-turn:last-child {
  margin-bottom: 0;
}
.evidence-label {
  font-size: 0.7rem;
  color: var(--text-dim);
  font-weight: 600;
}
/* Candidate Response Card */
.candidate-card {
  background: linear-gradient(180deg, rgba(30, 41, 59, 0.7), rgba(20, 25, 38, 0.9));
  border: 2px solid #3b82f6;
  box-shadow: 0 0 25px rgba(59, 130, 246, 0.15);
}
.candidate-text {
  font-size: 1.02rem;
  color: #ffffff;
  padding: 0.5rem 0.25rem;
  font-weight: 500;
  white-space: pre-wrap;
}
/* Rating Form */
.rating-group {
  margin-bottom: 1.15rem;
  padding-bottom: 0.85rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}
.rating-group:last-child {
  margin-bottom: 0;
  padding-bottom: 0;
  border-bottom: none;
}
.dimension-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 0.4rem;
}
.dimension-title {
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--text-main);
}
.dimension-question {
  font-size: 0.78rem;
  color: var(--text-muted);
  margin-bottom: 0.5rem;
}
.scale-buttons {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 0.4rem;
}
.scale-btn {
  background: var(--bg-card-subtle);
  border: 1px solid var(--border-subtle);
  color: var(--text-muted);
  padding: 0.55rem 0.2rem;
  border-radius: 6px;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  text-align: center;
}
.scale-btn:hover {
  background: var(--border-subtle);
  color: var(--text-main);
}
.scale-btn.selected {
  background: var(--accent-indigo);
  border-color: var(--accent-indigo);
  color: white;
  box-shadow: 0 0 10px rgba(99, 102, 241, 0.4);
}
/* Binary toggles */
.binary-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-bottom: 1.15rem;
}
.binary-group {
  background: var(--bg-card-subtle);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 0.75rem;
}
.binary-title {
  font-size: 0.82rem;
  font-weight: 600;
  margin-bottom: 0.4rem;
  color: var(--text-main);
}
.binary-buttons {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.4rem;
}
.binary-btn {
  background: var(--bg-input);
  border: 1px solid var(--border-subtle);
  color: var(--text-muted);
  padding: 0.4rem;
  border-radius: 6px;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  text-align: center;
}
.binary-btn:hover {
  background: var(--border-subtle);
  color: var(--text-main);
}
.binary-btn.selected-no {
  background: rgba(16, 185, 129, 0.2);
  border-color: var(--accent-emerald);
  color: #34d399;
}
.binary-btn.selected-yes {
  background: rgba(244, 63, 94, 0.2);
  border-color: var(--accent-rose);
  color: #fb7185;
}
.notes-input {
  width: 100%;
  background: var(--bg-input);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  color: var(--text-main);
  padding: 0.55rem;
  font-family: inherit;
  font-size: 0.82rem;
  resize: vertical;
  min-height: 50px;
  outline: none;
}
.notes-input:focus {
  border-color: var(--border-focus);
}
/* Form navigation */
.form-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  margin-top: 1.25rem;
}
.btn {
  padding: 0.6rem 1.15rem;
  border-radius: 8px;
  font-size: 0.88rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}
.btn-secondary {
  background: var(--bg-card-subtle);
  border-color: var(--border-subtle);
  color: var(--text-main);
}
.btn-secondary:hover {
  background: var(--border-subtle);
}
.btn-primary {
  background: linear-gradient(135deg, var(--accent-indigo), var(--accent-blue));
  color: white;
}
.btn-primary:hover {
  opacity: 0.92;
  box-shadow: 0 0 15px rgba(99, 102, 241, 0.35);
}
/* Grid Drawer Modal */
.drawer-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
  display: none;
  justify-content: center;
  align-items: center;
  z-index: 100;
}
.drawer-modal {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  width: 90%;
  max-width: 750px;
  max-height: 80vh;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
}
.drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}
.item-grid {
  display: grid;
  grid-template-columns: repeat(10, 1fr);
  gap: 0.5rem;
  overflow-y: auto;
  padding: 0.5rem 0;
}
.grid-cell {
  aspect-ratio: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.8rem;
  font-weight: 600;
  border-radius: 6px;
  cursor: pointer;
  background: var(--bg-card-subtle);
  border: 1px solid var(--border-subtle);
  color: var(--text-muted);
  transition: all 0.15s;
}
.grid-cell:hover {
  border-color: var(--accent-blue);
  color: var(--text-main);
}
.grid-cell.rated {
  background: rgba(16, 185, 129, 0.15);
  border-color: var(--accent-emerald);
  color: #34d399;
}
.grid-cell.current {
  outline: 2px solid var(--accent-blue);
  outline-offset: 1px;
}
/* Completion Alert */
.completion-banner {
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.15), rgba(59, 130, 246, 0.15));
  border: 1px solid var(--accent-emerald);
  border-radius: 10px;
  padding: 1rem 1.25rem;
  margin-bottom: 1.25rem;
  display: none;
}
.completion-banner.show {
  display: block;
}
.completion-title {
  font-weight: 700;
  color: #34d399;
  font-size: 0.95rem;
  margin-bottom: 0.25rem;
}
.cmd-box {
  background: var(--bg-input);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
  color: var(--accent-blue);
  margin-top: 0.4rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.copy-btn {
  background: var(--bg-card-subtle);
  border: 1px solid var(--border-subtle);
  color: var(--text-muted);
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-size: 0.72rem;
  cursor: pointer;
}
.copy-btn:hover { color: var(--text-main); }
.status-tag {
  font-size: 0.75rem;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-weight: 600;
}
.status-saved { background: rgba(16, 185, 129, 0.15); color: #34d399; }
.status-unsaved { background: rgba(245, 158, 11, 0.15); color: #fbbf24; }
</style>
</head>
<body>

<header>
  <div class="header-brand">
    <div class="logo-badge">ResolveAI</div>
    <div class="header-title">Human Evaluation Interface</div>
    <div class="blind-pill">Blinded Review</div>
  </div>
  <div class="header-progress">
    <div class="progress-stat">
      Progress: <span id="progress-text">0 / 50</span> (<span id="progress-pct">0%</span>)
    </div>
    <div class="progress-bar-container">
      <div class="progress-bar-fill" id="progress-bar"></div>
    </div>
    <button class="btn-drawer" onclick="toggleDrawer()">
      Overview ▦
    </button>
  </div>
</header>

<main>
  <!-- Left Panel: Context -->
  <div class="panel">
    <div id="completion-box" class="completion-banner">
      <div class="completion-title">🎉 All 50 Examples Successfully Rated!</div>
      <div>To compute the human-judge agreement metrics and produce the evaluation report, run:</div>
      <div class="cmd-box">
        <span id="cmd-text">python scripts/evaluate.py --cached</span>
        <button class="copy-btn" onclick="copyCmd()">Copy Command</button>
      </div>
    </div>

    <!-- Conversation Card -->
    <div class="card">
      <div class="card-header">
        <div class="card-title">
          <span>Customer Conversation</span>
        </div>
        <span class="badge-id" id="badge-example-id">ex00000000</span>
      </div>
      <div class="thread-container" id="thread-content">
        <!-- Thread turns will be rendered here -->
      </div>
    </div>

    <!-- Historical Evidence Card -->
    <div class="card">
      <div class="card-header">
        <div class="card-title">
          <span>Available Historical Evidence</span>
        </div>
        <span style="font-size:0.75rem; color:var(--text-dim);">Historical AppleSupport cases</span>
      </div>
      <div class="evidence-container" id="evidence-content">
        <!-- Evidence items rendered here -->
      </div>
    </div>

    <!-- Candidate Response Card -->
    <div class="card candidate-card">
      <div class="card-header">
        <div class="card-title" style="color:var(--accent-blue);">
          <span>Candidate Response Under Evaluation</span>
        </div>
        <span id="save-indicator" class="status-tag status-saved">Ready</span>
      </div>
      <div class="candidate-text" id="candidate-content">
        <!-- Candidate text rendered here -->
      </div>
    </div>
  </div>

  <!-- Right Panel: Scoring Form -->
  <div class="panel">
    <div class="card">
      <div class="card-header">
        <div class="card-title">
          <span>Rubric Ratings (Example <span id="current-num">1</span> of 50)</span>
        </div>
        <button class="btn-drawer" style="padding:0.2rem 0.5rem; font-size:0.75rem;" onclick="jumpNextUnrated()">
          Next Unrated ⏩
        </button>
      </div>

      <div id="ratings-form">
        <!-- Ordinal dimensions -->
        <div class="rating-group" data-dim="groundedness">
          <div class="dimension-header">
            <div class="dimension-title">1. Groundedness</div>
            <span style="font-size:0.75rem; color:var(--text-dim);">1 = Hallucinated/Contradicts · 5 = Fully Grounded</span>
          </div>
          <div class="dimension-question">Is every claim supported by evidence or the customer's own words?</div>
          <div class="scale-buttons" data-dim="groundedness">
            <button class="scale-btn" data-val="1" onclick="selectScale('groundedness', 1)">1</button>
            <button class="scale-btn" data-val="2" onclick="selectScale('groundedness', 2)">2</button>
            <button class="scale-btn" data-val="3" onclick="selectScale('groundedness', 3)">3</button>
            <button class="scale-btn" data-val="4" onclick="selectScale('groundedness', 4)">4</button>
            <button class="scale-btn" data-val="5" onclick="selectScale('groundedness', 5)">5</button>
          </div>
        </div>

        <div class="rating-group" data-dim="relevance">
          <div class="dimension-header">
            <div class="dimension-title">2. Relevance</div>
            <span style="font-size:0.75rem; color:var(--text-dim);">1 = Off-target · 5 = Exact match</span>
          </div>
          <div class="dimension-question">Does the response address the specific issue the customer raised?</div>
          <div class="scale-buttons" data-dim="relevance">
            <button class="scale-btn" data-val="1" onclick="selectScale('relevance', 1)">1</button>
            <button class="scale-btn" data-val="2" onclick="selectScale('relevance', 2)">2</button>
            <button class="scale-btn" data-val="3" onclick="selectScale('relevance', 3)">3</button>
            <button class="scale-btn" data-val="4" onclick="selectScale('relevance', 4)">4</button>
            <button class="scale-btn" data-val="5" onclick="selectScale('relevance', 5)">5</button>
          </div>
        </div>

        <div class="rating-group" data-dim="actionability">
          <div class="dimension-header">
            <div class="dimension-title">3. Actionability</div>
            <span style="font-size:0.75rem; color:var(--text-dim);">1 = Useless · 5 = Concrete step / right question</span>
          </div>
          <div class="dimension-question">Does the customer get a useful, executable next step or concrete handoff?</div>
          <div class="scale-buttons" data-dim="actionability">
            <button class="scale-btn" data-val="1" onclick="selectScale('actionability', 1)">1</button>
            <button class="scale-btn" data-val="2" onclick="selectScale('actionability', 2)">2</button>
            <button class="scale-btn" data-val="3" onclick="selectScale('actionability', 3)">3</button>
            <button class="scale-btn" data-val="4" onclick="selectScale('actionability', 4)">4</button>
            <button class="scale-btn" data-val="5" onclick="selectScale('actionability', 5)">5</button>
          </div>
        </div>

        <div class="rating-group" data-dim="completeness">
          <div class="dimension-header">
            <div class="dimension-title">4. Completeness</div>
            <span style="font-size:0.75rem; color:var(--text-dim);">1 = Omitted · 5 = Full answer + caveats</span>
          </div>
          <div class="dimension-question">Does it cover what could reasonably be answered from evidence + message?</div>
          <div class="scale-buttons" data-dim="completeness">
            <button class="scale-btn" data-val="1" onclick="selectScale('completeness', 1)">1</button>
            <button class="scale-btn" data-val="2" onclick="selectScale('completeness', 2)">2</button>
            <button class="scale-btn" data-val="3" onclick="selectScale('completeness', 3)">3</button>
            <button class="scale-btn" data-val="4" onclick="selectScale('completeness', 4)">4</button>
            <button class="scale-btn" data-val="5" onclick="selectScale('completeness', 5)">5</button>
          </div>
        </div>

        <div class="rating-group" data-dim="policy_compliance">
          <div class="dimension-header">
            <div class="dimension-title">5. Policy Compliance</div>
            <span style="font-size:0.75rem; color:var(--text-dim);">1 = Hard breach · 5 = Fully compliant</span>
          </div>
          <div class="dimension-question">Obeys brand rules (no refund promises, no public PII, right escalation)?</div>
          <div class="scale-buttons" data-dim="policy_compliance">
            <button class="scale-btn" data-val="1" onclick="selectScale('policy_compliance', 1)">1</button>
            <button class="scale-btn" data-val="2" onclick="selectScale('policy_compliance', 2)">2</button>
            <button class="scale-btn" data-val="3" onclick="selectScale('policy_compliance', 3)">3</button>
            <button class="scale-btn" data-val="4" onclick="selectScale('policy_compliance', 4)">4</button>
            <button class="scale-btn" data-val="5" onclick="selectScale('policy_compliance', 5)">5</button>
          </div>
        </div>

        <div class="rating-group" data-dim="tone">
          <div class="dimension-header">
            <div class="dimension-title">6. Tone</div>
            <span style="font-size:0.75rem; color:var(--text-dim);">1 = Rude/Offensive · 5 = Warm & Professional</span>
          </div>
          <div class="dimension-question">Is it concise, professional, brand-appropriate on a public channel?</div>
          <div class="scale-buttons" data-dim="tone">
            <button class="scale-btn" data-val="1" onclick="selectScale('tone', 1)">1</button>
            <button class="scale-btn" data-val="2" onclick="selectScale('tone', 2)">2</button>
            <button class="scale-btn" data-val="3" onclick="selectScale('tone', 3)">3</button>
            <button class="scale-btn" data-val="4" onclick="selectScale('tone', 4)">4</button>
            <button class="scale-btn" data-val="5" onclick="selectScale('tone', 5)">5</button>
          </div>
        </div>

        <!-- Binary Toggles -->
        <div class="binary-grid">
          <div class="binary-group">
            <div class="binary-title">7. Hallucination?</div>
            <div style="font-size:0.72rem; color:var(--text-muted); margin-bottom:0.4rem;">Any invented facts/steps?</div>
            <div class="binary-buttons" data-dim="hallucination">
              <button class="binary-btn" data-val="0" onclick="selectBinary('hallucination', 0)">No (0)</button>
              <button class="binary-btn" data-val="1" onclick="selectBinary('hallucination', 1)">Yes (1)</button>
            </div>
          </div>
          <div class="binary-group">
            <div class="binary-title">8. Policy Violation?</div>
            <div style="font-size:0.72rem; color:var(--text-muted); margin-bottom:0.4rem;">Breaks hard policy rule?</div>
            <div class="binary-buttons" data-dim="policy_violation">
              <button class="binary-btn" data-val="0" onclick="selectBinary('policy_violation', 0)">No (0)</button>
              <button class="binary-btn" data-val="1" onclick="selectBinary('policy_violation', 1)">Yes (1)</button>
            </div>
          </div>
        </div>

        <!-- Notes -->
        <div style="margin-bottom:1rem;">
          <div style="font-size:0.8rem; font-weight:600; color:var(--text-muted); margin-bottom:0.25rem;">Optional Notes</div>
          <textarea id="notes-field" class="notes-input" placeholder="Notes on ambiguity, specific phrases, or rationale..."></textarea>
        </div>

        <!-- Actions -->
        <div class="form-actions">
          <button class="btn btn-secondary" onclick="prevItem()">← Previous</button>
          <button class="btn btn-secondary" onclick="saveCurrent(false)">Save Draft</button>
          <button class="btn btn-primary" onclick="saveCurrent(true)">Save & Next →</button>
        </div>
      </div>
    </div>
  </div>
</main>

<!-- Grid Drawer Modal -->
<div class="drawer-overlay" id="drawer" onclick="if(event.target===this) toggleDrawer()">
  <div class="drawer-modal">
    <div class="drawer-header">
      <div style="font-weight:700; font-size:1.1rem;">Review Progress Overview</div>
      <button class="btn-drawer" onclick="toggleDrawer()">Close ✕</button>
    </div>
    <div style="font-size:0.82rem; color:var(--text-muted); margin-bottom:0.75rem;">
      Green = Rated & Saved · Gray = Pending · Blue outline = Current item
    </div>
    <div class="item-grid" id="drawer-grid">
      <!-- 50 grid items will be injected here -->
    </div>
  </div>
</div>

<script>
let currentIndex = 0;
let totalItems = 50;
let currentRatings = {};
let currentSummary = {};

async function init() {
  await fetchStatus();
  // If first unrated index exists, resume there; else start at 0
  if (currentSummary.first_unrated_index !== null && currentSummary.first_unrated_index !== undefined) {
    currentIndex = currentSummary.first_unrated_index;
  }
  await loadItem(currentIndex);
}

async function fetchStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    currentSummary = data;
    updateProgressUI();
  } catch (e) {
    console.error('Status fetch failed:', e);
  }
}

function updateProgressUI() {
  document.getElementById('progress-text').innerText = `${currentSummary.rated_count} / ${currentSummary.total}`;
  document.getElementById('progress-pct').innerText = `${currentSummary.percent_complete}%`;
  document.getElementById('progress-bar').style.width = `${currentSummary.percent_complete}%`;

  const completionBox = document.getElementById('completion-box');
  if (currentSummary.is_complete) {
    completionBox.classList.add('show');
  } else {
    completionBox.classList.remove('show');
  }
  renderDrawerGrid();
}

async function loadItem(index) {
  try {
    const res = await fetch(`/api/item/${index}`);
    if (!res.ok) throw new Error('Failed to load item');
    const item = await res.json();

    currentIndex = index;
    document.getElementById('current-num').innerText = index + 1;
    document.getElementById('badge-example-id').innerText = item.example_id;

    // Render conversation
    renderConversation(item.conversation);

    // Render evidence
    renderEvidence(item.evidence);

    // Render candidate
    document.getElementById('candidate-content').innerText = item.candidate_response;

    // Set ratings
    currentRatings = item.ratings || {};
    populateForm(currentRatings);

    // Update status
    setSaveIndicator(item.is_rated ? 'Rated' : 'Unrated', item.is_rated ? 'status-saved' : 'status-unsaved');
    fetchStatus();
  } catch (e) {
    alert('Error loading item: ' + e.message);
  }
}

function renderConversation(raw) {
  const container = document.getElementById('thread-content');
  container.innerHTML = '';
  const lines = raw.split('\\n');
  
  lines.forEach(line => {
    line = line.trim();
    if (!line) return;
    const bubble = document.createElement('div');
    if (line.toLowerCase().startsWith('customer:')) {
      bubble.className = 'turn-bubble turn-customer';
      bubble.innerHTML = `<div class="turn-role">Customer</div><div class="turn-text">${escapeHtml(line.slice(9).trim())}</div>`;
    } else if (line.toLowerCase().startsWith('brand:')) {
      bubble.className = 'turn-bubble turn-brand';
      bubble.innerHTML = `<div class="turn-role">Brand</div><div class="turn-text">${escapeHtml(line.slice(6).trim())}</div>`;
    } else if (line.toLowerCase().startsWith('current customer message:')) {
      bubble.className = 'turn-bubble turn-customer';
      bubble.style.border = '1px solid var(--accent-blue)';
      bubble.innerHTML = `<div class="turn-role" style="color:var(--accent-blue);">Current Customer Message</div><div class="turn-text">${escapeHtml(line.slice(25).trim())}</div>`;
    } else {
      bubble.className = 'turn-bubble';
      bubble.style.background = 'var(--bg-card-subtle)';
      bubble.innerHTML = `<div class="turn-text">${escapeHtml(line)}</div>`;
    }
    container.appendChild(bubble);
  });
}

function renderEvidence(raw) {
  const container = document.getElementById('evidence-content');
  container.innerHTML = '';
  if (!raw || raw.includes('No historical evidence')) {
    container.innerHTML = '<div style="color:var(--text-dim); font-size:0.85rem; padding:0.5rem;">No historical evidence was available to the system.</div>';
    return;
  }
  // Split [E1], [E2]
  const chunks = raw.split(/(?=\\[E\\d+\\])/g);
  chunks.forEach(chunk => {
    chunk = chunk.trim();
    if (!chunk) return;
    const m = chunk.match(/^\\[E(\\d+)\\]([\\s\\S]*)$/);
    const item = document.createElement('div');
    item.className = 'evidence-item';
    if (m) {
      const eNum = m[1];
      const rest = m[2].trim();
      item.innerHTML = `<div class="evidence-tag">[E${eNum}] Case</div><div class="evidence-turn">${escapeHtml(rest)}</div>`;
    } else {
      item.innerHTML = `<div class="evidence-turn">${escapeHtml(chunk)}</div>`;
    }
    container.appendChild(item);
  });
}

function populateForm(ratings) {
  // Clear all button selections
  document.querySelectorAll('.scale-btn').forEach(btn => btn.classList.remove('selected'));
  document.querySelectorAll('.binary-btn').forEach(btn => {
    btn.classList.remove('selected-no');
    btn.classList.remove('selected-yes');
  });

  // Ordinal dimensions
  ['groundedness', 'relevance', 'actionability', 'completeness', 'policy_compliance', 'tone'].forEach(dim => {
    if (ratings[dim] !== null && ratings[dim] !== undefined) {
      const btn = document.querySelector(`.scale-buttons[data-dim="${dim}"] button[data-val="${ratings[dim]}"]`);
      if (btn) btn.classList.add('selected');
    }
  });

  // Binary dimensions
  ['hallucination', 'policy_violation'].forEach(dim => {
    if (ratings[dim] !== null && ratings[dim] !== undefined) {
      const val = ratings[dim];
      const btn = document.querySelector(`.binary-buttons[data-dim="${dim}"] button[data-val="${val}"]`);
      if (btn) {
        btn.classList.add(val === 0 ? 'selected-no' : 'selected-yes');
      }
    }
  });

  document.getElementById('notes-field').value = ratings.notes || '';
}

function selectScale(dim, val) {
  currentRatings[dim] = val;
  const container = document.querySelector(`.scale-buttons[data-dim="${dim}"]`);
  container.querySelectorAll('button').forEach(b => b.classList.remove('selected'));
  container.querySelector(`button[data-val="${val}"]`).classList.add('selected');
  setSaveIndicator('Unsaved Changes', 'status-unsaved');
}

function selectBinary(dim, val) {
  currentRatings[dim] = val;
  const container = document.querySelector(`.binary-buttons[data-dim="${dim}"]`);
  container.querySelectorAll('button').forEach(b => {
    b.classList.remove('selected-no');
    b.classList.remove('selected-yes');
  });
  const btn = container.querySelector(`button[data-val="${val}"]`);
  btn.classList.add(val === 0 ? 'selected-no' : 'selected-yes');
  setSaveIndicator('Unsaved Changes', 'status-unsaved');
}

async function saveCurrent(advanceAfter = false) {
  currentRatings.notes = document.getElementById('notes-field').value;

  try {
    const res = await fetch('/api/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        index: currentIndex,
        ratings: currentRatings
      })
    });
    if (!res.ok) throw new Error('Save failed');
    currentSummary = await res.json();
    updateProgressUI();
    setSaveIndicator('Saved', 'status-saved');

    if (advanceAfter) {
      if (currentIndex < 49) {
        await loadItem(currentIndex + 1);
      } else {
        alert('You have reached the final item (50 of 50).');
      }
    }
  } catch (e) {
    alert('Error saving: ' + e.message);
  }
}

async function prevItem() {
  if (currentIndex > 0) {
    await loadItem(currentIndex - 1);
  }
}

async function jumpNextUnrated() {
  await fetchStatus();
  if (currentSummary.first_unrated_index !== null && currentSummary.first_unrated_index !== undefined) {
    await loadItem(currentSummary.first_unrated_index);
  } else {
    alert('All 50 examples have been rated!');
  }
}

function toggleDrawer() {
  const d = document.getElementById('drawer');
  d.style.display = (d.style.display === 'flex') ? 'none' : 'flex';
  if (d.style.display === 'flex') renderDrawerGrid();
}

function renderDrawerGrid() {
  const grid = document.getElementById('drawer-grid');
  grid.innerHTML = '';
  if (!currentSummary.item_statuses) return;

  currentSummary.item_statuses.forEach((item, idx) => {
    const cell = document.createElement('div');
    cell.className = 'grid-cell' + (item.is_rated ? ' rated' : '') + (idx === currentIndex ? ' current' : '');
    cell.innerText = idx + 1;
    cell.onclick = () => {
      toggleDrawer();
      loadItem(idx);
    };
    grid.appendChild(cell);
  });
}

function setSaveIndicator(text, cls) {
  const ind = document.getElementById('save-indicator');
  ind.innerText = text;
  ind.className = 'status-tag ' + cls;
}

function copyCmd() {
  const cmd = document.getElementById('cmd-text').innerText;
  navigator.clipboard.writeText(cmd);
  alert('Copied command: ' + cmd);
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.innerText = text;
  return div.innerHTML;
}

// Keyboard navigation
window.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') return;
  if (e.key === 'ArrowRight' || e.key === 'n') {
    saveCurrent(true);
  } else if (e.key === 'ArrowLeft' || e.key === 'p') {
    prevItem();
  }
});

window.onload = init;
</script>
</body>
</html>
"""


class HumanEvalRequestHandler(BaseHTTPRequestHandler):
    manager: PacketManager

    def _send_json(self, data: Any, status: int = HTTPStatus.OK) -> None:
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(payload)

    def _send_html(self, html: str) -> None:
        payload = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            self._send_html(render_html())
            return

        if path == "/api/status":
            self._send_json(self.manager.get_summary())
            return

        m_item = re.match(r"^/api/item/(\d+)$", path)
        if m_item:
            idx = int(m_item.group(1))
            try:
                item = self.manager.get_item(idx)
                self._send_json(item)
            except IndexError as e:
                self._send_json({"error": str(e)}, status=HTTPStatus.NOT_FOUND)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/save":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            try:
                data = json.loads(body)
                idx = int(data.get("index", -1))
                ratings = data.get("ratings", {})
                updated_summary = self.manager.save_item(idx, ratings)
                self._send_json(updated_summary)
            except Exception as e:
                self._send_json({"error": str(e)}, status=HTTPStatus.BAD_REQUEST)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def log_message(self, format: str, *args: Any) -> None:
        # Keep quiet on standard 200 GETs, log saves and errors
        if args and str(args[1]) != "200":
            super().log_message(format, *args)


def run_server(host: str = "127.0.0.1", port: int = 8765, packet_path: Path = DEFAULT_PACKET_PATH) -> None:
    mgr = PacketManager(packet_path=packet_path)
    if not mgr.verify_blinding():
        print("[CRITICAL ERROR] The packet contains unblinded fields! Aborting to protect reviewer integrity.")
        sys.exit(1)

    summary = mgr.get_summary()
    print("=" * 70)
    print("RESOLVEAI BLINDED HUMAN EVALUATION SERVER")
    print("=" * 70)
    print(f"Packet path:       {packet_path}")
    print(f"Total examples:    {summary['total']}")
    print(f"Currently rated:   {summary['rated_count']} / {summary['total']} ({summary['percent_complete']}%)")
    print(f"Reviewer Blinding: VERIFIED (zero model, system, or golden labels exposed)")
    print(f"\nOpen the reviewer interface in your browser:")
    print(f"👉 http://{host}:{port}")
    print("=" * 70)
    if summary["is_complete"]:
        print("🎉 ALL 50 EXAMPLES COMPLETED!")
        print("To compute agreement metrics, run:")
        print("  python scripts/evaluate.py --cached\n")

    class CustomHandler(HumanEvalRequestHandler):
        manager = mgr

    httpd = ThreadingHTTPServer((host, port), CustomHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nEvaluator server stopped.")
        httpd.server_close()


def run_cli(packet_path: Path = DEFAULT_PACKET_PATH) -> None:
    """Terminal-based evaluator for reviewers who prefer CLI."""
    mgr = PacketManager(packet_path=packet_path)
    if not mgr.verify_blinding():
        print("[CRITICAL ERROR] The packet contains unblinded fields!")
        sys.exit(1)

    summary = mgr.get_summary()
    print("=" * 70)
    print("RESOLVEAI BLINDED HUMAN EVALUATION CLI")
    print(f"Total: {summary['total']} | Rated: {summary['rated_count']}")
    print("=" * 70)

    start_idx = summary["first_unrated_index"] if summary["first_unrated_index"] is not None else 0
    idx = start_idx

    while idx < summary["total"]:
        item = mgr.get_item(idx)
        print(f"\n[{idx+1}/{summary['total']}] Example ID: {item['example_id']}")
        print("-" * 50)
        print("CONVERSATION:")
        print(item["conversation"])
        print("\nAVAILABLE HISTORICAL EVIDENCE:")
        print(item["evidence"])
        print("\nCANDIDATE RESPONSE UNDER TEST:")
        print(f">>> {item['candidate_response']}")
        print("-" * 50)

        ratings = item["ratings"] or {}
        new_ratings = {}

        for d in ORDINAL_DIMS:
            prompt_q = RUBRIC_GUIDE[d]["question"]
            cur = ratings.get(d)
            cur_str = f" [current: {cur}]" if cur is not None else ""
            while True:
                val = input(f"{d.capitalize()} (1-5){cur_str}: ").strip()
                if not val and cur is not None:
                    new_ratings[d] = cur
                    break
                if val in ("1", "2", "3", "4", "5"):
                    new_ratings[d] = int(val)
                    break
                print("  Invalid. Enter 1, 2, 3, 4, or 5.")

        for d in BINARY_DIMS:
            cur = ratings.get(d)
            cur_str = f" [current: {cur}]" if cur is not None else ""
            while True:
                val = input(f"{d.replace('_', ' ').capitalize()} (0=No, 1=Yes){cur_str}: ").strip()
                if not val and cur is not None:
                    new_ratings[d] = cur
                    break
                if val in ("0", "1"):
                    new_ratings[d] = int(val)
                    break
                print("  Invalid. Enter 0 or 1.")

        cur_notes = ratings.get("notes", "")
        notes_input = input(f"Notes [{cur_notes}]: ").strip()
        new_ratings["notes"] = notes_input if notes_input else cur_notes

        mgr.save_item(idx, new_ratings)
        print(f"Saved example {idx+1}/{summary['total']}!")

        nav = input("Press [Enter] for next, 'p' for prev, 'q' to quit: ").strip().lower()
        if nav == "q":
            break
        elif nav == "p":
            idx = max(0, idx - 1)
        else:
            idx += 1

    summary = mgr.get_summary()
    if summary["is_complete"]:
        print("\n" + "=" * 70)
        print("🎉 ALL 50 EXAMPLES COMPLETED!")
        print("To compute the evaluation metrics, run:")
        print("  python scripts/evaluate.py --cached")
        print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ResolveAI Blinded Human Evaluation Interface")
    parser.add_argument("--cli", action="store_true", help="Run interactive terminal evaluation instead of web UI")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on (default: 8765)")
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH, help="Path to human scoring packet CSV")
    args = parser.parse_args()

    if args.cli:
        run_cli(packet_path=args.packet)
    else:
        run_server(host=args.host, port=args.port, packet_path=args.packet)
