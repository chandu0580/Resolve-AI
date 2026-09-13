"""Intent taxonomy for AppleSupport (guide v1.1). Derived from k-means clusters over 6k customer messages in Phase 0
(artifacts/dataset_recon) and refined by the golden-set adjudication (data/golden/ANNOTATION_GUIDE.md)."""
from __future__ import annotations

TAXONOMY_VERSION = "1.1"

INTENTS: dict[str, str] = {
    "battery_power": "Battery draining fast, not charging, dying at N%, random shutdowns, device overheating.",
    "performance_crash": "OS/device-wide freezing, lag, slow, crashing, rebooting, boot loops, often after an iOS update.",
    "keyboard_text_bug": "Typing/autocorrect bugs: the letter 'I' becoming 'A?' or a question-mark box, 'it' -> 'I.T', emoji boxes.",
    "connectivity": "Wi-Fi, Bluetooth, cellular/SIM, hotspot, AirDrop, CarPlay, GPS/location, accessory connection or pairing.",
    "data_loss_sync": "Photos, contacts, messages, notes or library missing; iCloud sync, backup, restore, storage, migration.",
    "apps_services": "A specific app or service fails: Apple Music, App Store, iTunes, iMessage, FaceTime, Mail, Safari, Siri, Camera, Phone app, notifications, third-party apps, OS features like software update or clipboard.",
    "account_store_repair": "Apple ID / password / 2FA / activation lock, orders, delivery, billing, refunds, Apple Store or Genius Bar visits, repairs, warranty, AppleCare, appointments.",
    "hardware_damage": "Explicit physical damage or fault: cracked/black/lined screen, liquid, dead Mac, dead touch screen, blown speaker, smoke, burns.",
    "general_complaint": "Support request with no concrete actionable symptom, or no intent genuinely fits (taxonomy gap).",
    "non_english": "Message is not in English (Apple's Twitter support is English-only).",
    "other": "Not a support request: thanks, closures, jokes, product/price questions, praise, suggestions, off-topic.",
}
INTENT_NAMES = list(INTENTS)

ESCALATION_REASONS = ["safety", "legal_media", "private_info", "hardware", "repeat_contact", "vague_hostile"]
REASON_PRIORITY = ESCALATION_REASONS  # first wins when several apply

# Keyword seeds. Used ONLY for weak labelling (golden sampling strata) and the keyword baseline. Intentionally crude.
KEYWORDS: dict[str, list[str]] = {
    "battery_power": ["battery", "charg", "drain", "dies", "died", "dying", "power off", "shut down", "shuts off", "turning off", "%", "warm", "hot"],
    "performance_crash": ["freez", "froze", "slow", "lag", "crash", "glitch", "restart", "reboot", "stuck", "hang"],
    "keyboard_text_bug": ["letter i", "type i", "autocorrect", "keyboard", "question mark", "box", "a?", "typing", "emoji", "i.t"],
    "connectivity": ["wifi", "wi-fi", "bluetooth", "cellular", "signal", "hotspot", "airdrop", "carplay", "connect", "lte", "4g", "network", "gps", "sim"],
    "data_loss_sync": ["photo", "picture", "icloud", "backup", "restore", "storage", "deleted", "disappear", "lost my", "missing", "contacts"],
    "apps_services": ["apple music", "app store", "itunes", "imessage", "facetime", "siri", "mail", "notification", "spotify", "app ", "safari", "camera", "update", "software update"],
    "account_store_repair": ["apple id", "password", "order", "deliver", "refund", "charged", "billing", "store", "genius", "repair", "warranty", "applecare", "appointment", "replace", "case"],
    "hardware_damage": ["screen", "cracked", "water", "liquid", "smoke", "burn", "broke", "broken", "blew"],
    "non_english": ["que ", "por ", "não", "está", "mi ", "el ", "la ", "yo ", "je ", "ich ", "das "],
}
