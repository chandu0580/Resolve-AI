from resolveai.data.clean import clean_tweet, is_dm_handoff, outcome_from_followup, redact_pii, strip_signature


def test_clean_removes_mentions_urls_and_html():
    t = clean_tweet("@AppleSupport my phone &amp; watch broke https://t.co/abc @115858")
    assert t == "my phone & watch broke <url>"


def test_signature_stripped():
    assert strip_signature("Glad to help! ^EC") == "Glad to help!"
    assert strip_signature("Please DM your address 2/3") == "Please DM your address"
    assert strip_signature("iOS 11.1.1 fixes it") == "iOS 11.1.1 fixes it"   # version numbers survive


def test_redact_email_phone_order():
    r = redact_pii("email me at john.doe@gmail.com or call +1 (415) 555-0134, order 123-4567890-1234567")
    assert r.text == "email me at <EMAIL> or call <PHONE>, order <ORDER_ID>"
    assert r.counts == {"EMAIL": 1, "PHONE": 1, "ORDER_ID": 1}


def test_redact_leaves_prices_versions_times_alone():
    s = "paid $1,299 for iOS 11.1.1 at 10:30, battery 4% in 2 hrs, iPhone 7"
    assert redact_pii(s).text == s


def test_redact_serial_and_card():
    assert redact_pii("serial C02XG1ZTJG5H").text == "serial <LONG_ID>"
    assert redact_pii("card 4111 1111 1111 1111").text == "card <CARD>"


def test_dm_handoff():
    assert is_dm_handoff("We'd love to help. DM us the details.")
    assert not is_dm_handoff("Try restarting the device and let us know.")


def test_outcome_signal():
    assert outcome_from_followup("Thank you, that worked!") == "positive"
    assert outcome_from_followup("still not working") == "negative"
    assert outcome_from_followup("thanks but still broken") == "mixed"
    assert outcome_from_followup("which settings?") == "none"
    assert outcome_from_followup(None) == "none"
