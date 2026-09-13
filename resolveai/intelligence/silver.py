"""Silver intent labels for KB / dev rows (no human labels exist outside the frozen golden set).

Construction (deterministic, no LLM, never touches golden):
  1. hard rules with high confidence: non-English script/stopwords -> non_english; closure phrases -> other;
  2. keyword votes from the taxonomy seed lists (count of matched seeds per intent, word-boundary matching);
  3. prototype similarity: BGE-small cosine between the message and a prototype text per intent (definition + guide
     phrases, NOT golden rows);
  4. score(intent) = 0.5 * normalised keyword votes + 0.5 * prototype cosine, label = argmax, confidence = margin-based;
  5. rows with no keyword hit and a flat prototype distribution fall to general_complaint with LOW confidence.
silver-v2 (after the v1 noise check, artifacts/intelligence/silver_noise_check.md): the corrupted I-glyph rule from the
guide (U+0049 U+FE0F -> keyboard_text_bug), word-boundary matching for keyword seeds (v1 matched "el " inside "cancel "),
the non_english vote requires two non-English function words, and "won't turn on" / "dead phone" map to battery_power.
Silver labels are training signal only. Their noise is measured on a hand-inspected sample and reported next to every
number that depends on them.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

from resolveai.models.taxonomy import INTENT_NAMES, KEYWORDS
from resolveai.retrieval.dense import SUPPORTED, Embedder

SILVER_VERSION = "silver-v2"
NON_ENGLISH_WORDS = re.compile(r"\b(que|por|para|não|nao|está|esta|con|pero|gracias|hola|merci|bonjour|ich|nicht|bitte|het|niet|een|mijn|هل|في|من)\b", re.I)
GLYPH = re.compile("I\N{VARIATION SELECTOR-16}")
POWER = re.compile(r"\b(won.?t (turn|power|switch) on|not turning on|dead (phone|iphone|battery)|completely dead)\b", re.I)
CLOSURE = re.compile(r"^\s*(thank(s| you| u)!*|thanks!*|thx|ty|done|sent|ok(ay)?|yes|no|cool|great|perfect|got it|will do)[.! ]*$", re.I)
PROTOTYPES = {
    "battery_power": "battery drains fast, phone dies at 40 percent, not charging, overheating, shuts down randomly",
    "performance_crash": "phone freezes and lags, keeps restarting and crashing, stuck on apple logo, slow since the update",
    "keyboard_text_bug": "typing the letter I turns into A with a question mark box, autocorrect changes it to I.T, keyboard glitch",
    "connectivity": "wifi keeps disconnecting, bluetooth will not pair, no cellular signal, sim not valid, gps location wrong",
    "data_loss_sync": "photos disappeared after update, icloud backup not restoring, contacts and notes missing, storage full",
    "apps_services": "apple music not playing, app store will not download, imessage not delivered, mail app crashing, siri not working",
    "account_store_repair": "cannot reset apple id password, order not delivered, charged twice refund, genius bar appointment, repair warranty",
    "hardware_damage": "cracked screen, liquid damage, speaker blew out, black screen with lines, cable smoking, touch screen dead",
    "general_complaint": "fix this, worst update ever, apple sucks, why is this happening, so annoying",
    "non_english": "mi iphone no funciona desde la actualizacion, meu telefone nao carrega",
    "other": "thank you so much, when is the new iphone released, feature request, is this you",
}


@dataclass
class SilverLabel:
    intent: str
    confidence: float          # 0-1
    band: str                  # HIGH / MEDIUM / LOW
    source: str                # rule:non_english | rule:other | vote | fallback
    scores: dict[str, float]


class SilverLabeler:
    _seed_cache: dict[str, re.Pattern[str]] = {}

    def __init__(self, model_id: str = SUPPORTED["bge-small"]):
        self.embedder = Embedder(model_id)
        P, _ = self.embedder.encode([PROTOTYPES[i] for i in INTENT_NAMES], tag="proto")
        self.P = P

    @classmethod
    def _seed(cls, k: str) -> re.Pattern[str]:
        """'battery' -> \\bbattery\\b; a seed ending in a space ('app ') keeps the leading boundary and requires a following
        word boundary too; seeds starting with a symbol ('%', 'a?') get no leading boundary."""
        if k not in cls._seed_cache:
            core = re.escape(k.strip())
            lead = r"\b" if k[0].isalnum() else ""
            trail = r"\b" if k.strip()[-1].isalnum() else ""
            cls._seed_cache[k] = re.compile(lead + core + trail, re.I)
        return cls._seed_cache[k]

    @classmethod
    def keyword_votes(cls, text: str) -> dict[str, int]:
        t = text or ""
        votes = {i: sum(1 for k in KEYWORDS.get(i, []) if cls._seed(k).search(t)) for i in INTENT_NAMES}
        if votes["non_english"] < 2:
            votes["non_english"] = 0          # single stopword-like hits ("el", "la") are not evidence of another language
        if GLYPH.search(t):
            votes["keyboard_text_bug"] += 2   # the bug manifesting in the customer's own text (guide v1.1, R5)
        if POWER.search(t):
            votes["battery_power"] += 2
        return votes

    @staticmethod
    def hard_rule(text: str) -> str | None:
        t = text or ""
        non_ascii = sum(1 for ch in t if ord(ch) > 127 and not (0x1F000 <= ord(ch) <= 0x1FFFF or 0x2600 <= ord(ch) <= 0x27BF or ord(ch) == 0xFE0F)) / max(1, len(t))
        if non_ascii > 0.25 or len(NON_ENGLISH_WORDS.findall(t)) >= 2:
            return "non_english"
        if CLOSURE.match(t):
            return "other"
        return None

    def label_many(self, texts: list[str], tag: str = "silver") -> list[SilverLabel]:
        X, _ = self.embedder.encode(texts, tag=tag)
        cos = X @ self.P.T  # (n, 11)
        out = []
        for text, c in zip(texts, cos, strict=False):
            rule = self.hard_rule(text)
            if rule:
                out.append(SilverLabel(rule, 0.95, "HIGH", f"rule:{rule}", {rule: 1.0}))
                continue
            votes = self.keyword_votes(text)
            vmax = max(votes.values()) or 1
            kw = np.array([votes[i] / vmax for i in INTENT_NAMES])
            proto = (c - c.min()) / max(1e-6, (c.max() - c.min()))
            score = 0.5 * kw + 0.5 * proto
            order = np.argsort(-score)
            best, second = INTENT_NAMES[order[0]], INTENT_NAMES[order[1]]
            margin = float(score[order[0]] - score[order[1]])
            n_hits = votes[best]
            if n_hits == 0 and margin < 0.15:
                out.append(SilverLabel("general_complaint", 0.3, "LOW", "fallback", {k: float(v) for k, v in zip(INTENT_NAMES, score, strict=False)}))
                continue
            conf = min(0.95, 0.5 + margin + 0.1 * min(n_hits, 3))
            band = "HIGH" if conf >= 0.75 else "MEDIUM" if conf >= 0.55 else "LOW"
            out.append(SilverLabel(best, round(conf, 3), band, "vote", {best: float(score[order[0]]), second: float(score[order[1]])}))
        return out
