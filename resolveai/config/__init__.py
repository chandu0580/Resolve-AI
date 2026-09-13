"""Central configuration. Everything tunable lives here; secrets come only from the environment / .env.

Import style everywhere: `from resolveai import config` then `config.NAME`. Never print `LLM_API_KEY`.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT / ".env")

# --- data -----------------------------------------------------------------------------------------
BRAND = "AppleSupport"
DATA_DIR = ROOT / "data"
# Raw Kaggle file (516 MB, never committed, never modified). Only needed to REBUILD the shipped subsample.
RAW_CSV = Path(os.getenv("TWCS_CSV", DATA_DIR / "raw" / "twcs.csv"))
PROCESSED_DIR = DATA_DIR / "processed"
GOLDEN_DIR = DATA_DIR / "golden"
CACHE_DIR = ROOT / ".cache"
TRACE_DIR = ROOT / "traces"
for _d in (PROCESSED_DIR, GOLDEN_DIR, CACHE_DIR):
    _d.mkdir(parents=True, exist_ok=True)

PREPROCESSING_VERSION = "2.0"   # bump whenever clean/ingest semantics change; recorded in the dataset manifest
SUBSAMPLE_SIZE = 20_000         # rows shipped in the repo so graders never touch the raw file
SEED = 42

# --- LLM ------------------------------------------------------------------------------------------
# Provider is pure configuration (any OpenAI-compatible endpoint). The MODEL was chosen by the Phase 1A
# benchmark (artifacts/llm_smoke/PHASE1A_MODEL_DECISION.md), not by preference.
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.z.ai/api/paas/v4/")
LLM_MODEL = os.getenv("LLM_MODEL", "glm-5.2")
LLM_TEMPERATURE = 0.0
LLM_TIMEOUT_S = 30.0            # a 71 s outlier was measured; a call must never block the agent indefinitely
LLM_MAX_RETRIES = 1
LLM_MAX_TOKENS = 700            # hidden reasoning consumes ~300 output tokens; lower caps produce empty JSON

# Which agent responsibilities may call the LLM. Everything else is deterministic code (locked decision).
LLM_ROLES: dict[str, str] = {
    "risk_flags": LLM_MODEL,
    "intent_second_opinion": LLM_MODEL,
    "draft": LLM_MODEL,
    "verify": LLM_MODEL,
    "judge": LLM_MODEL,
}
NON_LLM_RESPONSIBILITIES = ("primary_intent_classifier", "retrieval", "retrieval_ranking", "escalation_policy", "automation_decision", "policy_enforcement")

# --- embeddings / retrieval (used from Phase 2) ---------------------------------------------------
EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")  # selected in Phase 2 by measurement; MiniLM is the measured fallback
TOP_K = 5


def masked_summary() -> dict[str, str]:
    """Safe-to-log view of the configuration. Secrets are masked, never returned."""
    return {
        "brand": BRAND,
        "llm_model": LLM_MODEL,
        "llm_base_url": LLM_BASE_URL,
        "llm_api_key": ("set" if LLM_API_KEY else "missing"),
        "embed_model": EMBED_MODEL,
        "preprocessing_version": PREPROCESSING_VERSION,
        "seed": str(SEED),
    }
