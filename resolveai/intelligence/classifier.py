"""Intent classifiers: majority, keyword rules, TF-IDF + LR, BGE-small embedding + LR (primary), with temperature
calibration, operational confidence bands and multi-intent detection. Output contract: schemas.IntentResult.

Confidence bands (purpose: consumed by retrieval gating strength, grounding and the escalation policy; the classifier
never decides escalation itself):
  HIGH   >= BAND_HIGH   act on the intent (intent-boosted retrieval, intent-specific canned strategies)
  MEDIUM >= BAND_MEDIUM use the intent as a hint only (mild retrieval boost, keep alternatives)
  LOW    otherwise      treat as unknown (no intent gating; policy may escalate on low confidence)
Thresholds are set on DEV calibration curves (scripts/phase3/b_train_eval.py) and frozen in the model artifact.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from resolveai.intelligence.silver import SilverLabeler
from resolveai.knowledge.procedural import match_procedural
from resolveai.models.taxonomy import INTENT_NAMES, TAXONOMY_VERSION
from resolveai.retrieval.dense import SUPPORTED, Embedder
from resolveai.schemas.core import IntentResult

ARTIFACT = Path(__file__).resolve().parent.parent / "models" / "artifacts" / "intent_bge_lr.json"
BAND_HIGH, BAND_MEDIUM = 0.75, 0.45
MULTI_RATIO, MULTI_MIN = 0.5, 0.20      # second prob >= 0.20 and >= 50% of the first -> multi-intent candidate
FLAT_MAX = 0.35                          # top probability below this with fallback class -> taxonomy_gap
# Action/symptom vocabulary per intent, used by the verifier's intent-consistency check (words only, lowercase).
CANONICAL_TERMS: dict[str, set[str]] = {
    "battery_power": {"battery", "charge", "charging", "charger", "drain", "draining", "power"},
    "performance_crash": {"restart", "restarting", "freeze", "freezing", "frozen", "crash", "crashing", "slow", "lag", "reboot"},
    "keyboard_text_bug": {"keyboard", "autocorrect", "typing", "letter", "predictive"},
    "connectivity": {"wifi", "bluetooth", "cellular", "network", "signal", "hotspot", "sim", "gps"},
    "data_loss_sync": {"photos", "icloud", "backup", "restore", "contacts", "notes", "storage", "library"},
    "apps_services": {"app", "music", "itunes", "imessage", "facetime", "mail", "safari", "siri", "store", "update", "software", "ios"},
    "account_store_repair": {"order", "refund", "billing", "warranty", "repair", "appointment", "password"},
    "hardware_damage": {"screen", "cracked", "liquid", "speaker", "damage", "repair"},
}


def softmax(z: np.ndarray, T: float = 1.0) -> np.ndarray:
    z = z / T
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def band(p: float, high: float = BAND_HIGH, medium: float = BAND_MEDIUM) -> str:
    return "HIGH" if p >= high else "MEDIUM" if p >= medium else "LOW"


# ------------------------------------------------------------------ baselines -----------------------------------------
class MajorityClassifier:
    method = "majority"

    def fit(self, texts, y):
        vals, counts = np.unique(y, return_counts=True)
        self.label = str(vals[np.argmax(counts)])
        return self

    def predict_proba(self, texts) -> np.ndarray:
        P = np.full((len(texts), len(INTENT_NAMES)), 1e-6)
        P[:, INTENT_NAMES.index(self.label)] = 1.0
        return P / P.sum(axis=1, keepdims=True)


class KeywordClassifier:
    """The silver labeller's rule + vote path, used as the rule baseline (no training)."""
    method = "keyword"

    def __init__(self):
        self.lab = SilverLabeler()

    def fit(self, texts, y):
        return self

    def predict_proba(self, texts) -> np.ndarray:
        P = np.full((len(texts), len(INTENT_NAMES)), 0.02)
        for i, s in enumerate(self.lab.label_many(list(texts), tag="kwclf")):
            P[i, INTENT_NAMES.index(s.intent)] += s.confidence
        return P / P.sum(axis=1, keepdims=True)


class TfidfLR:
    method = "tfidf_lr"

    def __init__(self, C: float = 2.0):
        self.vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)
        self.lr = LogisticRegression(C=C, max_iter=2000, class_weight="balanced")

    def fit(self, texts, y):
        self.lr.fit(self.vec.fit_transform(texts), y)
        return self

    def predict_proba(self, texts) -> np.ndarray:
        return _align(self.lr.predict_proba(self.vec.transform(texts)), self.lr.classes_)


def _align(P: np.ndarray, classes) -> np.ndarray:
    out = np.zeros((P.shape[0], len(INTENT_NAMES)))
    for j, c in enumerate(classes):
        out[:, INTENT_NAMES.index(str(c))] = P[:, j]
    return out


# ------------------------------------------------------------------ primary -------------------------------------------
@dataclass
class EmbedLR:
    """BGE-small embedding + multinomial logistic regression, temperature-calibrated on DEV. Serialisable to JSON."""
    model_id: str = SUPPORTED["bge-small"]
    C: float = 1.0
    class_weight: str | None = "balanced"
    temperature: float = 1.0
    band_high: float = BAND_HIGH
    band_medium: float = BAND_MEDIUM
    coef: np.ndarray | None = None
    intercept: np.ndarray | None = None
    meta: dict = field(default_factory=dict)
    method: str = "embed_lr"

    def _emb(self) -> Embedder:
        return Embedder(self.model_id)

    def fit(self, texts, y, *, X: np.ndarray | None = None, tag: str = "train"):
        if X is None:
            X, _ = self._emb().encode(list(texts), tag=tag)
        lr = LogisticRegression(C=self.C, max_iter=3000, class_weight=self.class_weight).fit(X, y)
        self.coef = np.zeros((len(INTENT_NAMES), X.shape[1]))
        self.intercept = np.zeros(len(INTENT_NAMES))
        for j, c in enumerate(lr.classes_):
            k = INTENT_NAMES.index(str(c))
            self.coef[k], self.intercept[k] = lr.coef_[j], lr.intercept_[j]
        return self

    def logits(self, texts=None, *, X: np.ndarray | None = None, tag: str = "q") -> np.ndarray:
        if X is None:
            X, _ = self._emb().encode(list(texts), tag=tag)
        return X @ self.coef.T + self.intercept

    def predict_proba(self, texts=None, *, X: np.ndarray | None = None, tag: str = "q") -> np.ndarray:
        return softmax(self.logits(texts, X=X, tag=tag), self.temperature)

    def calibrate(self, texts, y, *, X: np.ndarray | None = None, grid=(0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0)) -> dict:
        """Temperature scaling: choose T minimising NLL on DEV. Returns diagnostics."""
        Z = self.logits(texts, X=X, tag="silverdev")
        yi = np.array([INTENT_NAMES.index(v) for v in y])
        best = None
        for T in grid:
            P = softmax(Z, T)
            nll = -np.log(np.clip(P[np.arange(len(yi)), yi], 1e-9, 1)).mean()
            if best is None or nll < best[1]:
                best = (T, nll)
        self.temperature = float(best[0])
        return {"temperature": self.temperature, "dev_nll": round(float(best[1]), 4), "grid": list(grid)}

    def save(self, path: Path = ARTIFACT) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"model_id": self.model_id, "C": self.C, "class_weight": self.class_weight, "temperature": self.temperature,
                                    "band_high": self.band_high, "band_medium": self.band_medium, "classes": INTENT_NAMES, "taxonomy_version": TAXONOMY_VERSION,
                                    "coef": self.coef.tolist(), "intercept": self.intercept.tolist(), "meta": self.meta}), encoding="utf-8")

    @classmethod
    def load(cls, path: Path = ARTIFACT) -> EmbedLR:
        d = json.loads(path.read_text(encoding="utf-8"))
        assert d["classes"] == INTENT_NAMES, "artifact classes do not match the taxonomy"
        m = cls(model_id=d["model_id"], C=d["C"], class_weight=d["class_weight"], temperature=d["temperature"], band_high=d["band_high"], band_medium=d["band_medium"], meta=d.get("meta", {}))
        m.coef, m.intercept = np.array(d["coef"]), np.array(d["intercept"])
        return m


# ------------------------------------------------------------------ result construction -------------------------------
def to_result(P: np.ndarray, *, method: str, calibrated: bool, band_high: float = BAND_HIGH, band_medium: float = BAND_MEDIUM,
              context_used: bool = False, insufficient_context: bool = False, calibration: dict | None = None) -> IntentResult:
    order = np.argsort(-P)
    top = [(INTENT_NAMES[i], round(float(P[i]), 4)) for i in order[:3]]
    p1 = float(P[order[0]])
    primary = INTENT_NAMES[order[0]]
    secondary = [INTENT_NAMES[i] for i in order[1:3] if P[i] >= MULTI_MIN and P[i] >= MULTI_RATIO * p1]
    multi = bool(secondary)
    gap = primary == "general_complaint" and p1 < FLAT_MAX
    conf = p1
    b = band(conf, band_high, band_medium)
    if insufficient_context:
        b = "LOW"
    return IntentResult(intent=primary, confidence=round(conf, 4), top3=top, method=method, confidence_band=b, calibrated=calibrated,
                        calibration=calibration or {}, secondary_intents=secondary, multi_intent=multi, insufficient_context=insufficient_context,
                        taxonomy_gap=gap, context_used=context_used)


class IntentService:
    """Runtime wrapper: loads the frozen artifact once; classifies a ContextBundle."""

    def __init__(self, model: EmbedLR | None = None):
        self.model = model or EmbedLR.load()
        self.last_latency_ms = 0.0

    def classify(self, bundle, *, use_context: bool = False, X=None) -> IntentResult:
        """Default classifies the current message only: on golden, the concatenated context text did not beat message-only
        (0.609 vs 0.614 accuracy) because the model is trained on single messages. Context still drives the flags
        (short reply, insufficient context) and the retrieval query."""
        t0 = time.perf_counter()
        # Check Trusted Procedural Knowledge before normal symptom classification
        proc = match_procedural(bundle.current)
        if proc is not None:
            self.last_latency_ms = (time.perf_counter() - t0) * 1000
            return IntentResult(
                intent=proc.canonical_intent,
                confidence=0.99,
                confidence_band="HIGH",
                top3=[(proc.canonical_intent, 0.99)],
                method="procedural",
                procedural_id=proc.id,
                calibrated=True,
                calibration={"method": "procedural_rules", "procedure": proc.id},
                context_used=use_context and bundle.used_context,
                insufficient_context=False,
            )

        text = bundle.text_for_classification if use_context else bundle.current
        P = self.model.predict_proba([text])[0] if X is None else self.model.predict_proba(X=X)[0]
        r = to_result(P, method="embed_lr", calibrated=True, band_high=self.model.band_high, band_medium=self.model.band_medium,
                      context_used=use_context and bundle.used_context, insufficient_context=bundle.insufficient_context,
                      calibration={"method": "temperature", "temperature": self.model.temperature, "dev_ece": self.model.meta.get("dev_ece", "")})
        self.last_latency_ms = (time.perf_counter() - t0) * 1000
        return r
