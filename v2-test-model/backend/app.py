import re
import sys
from pathlib import Path

import joblib
import pandas as pd
from flask import Flask, jsonify, request

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from model.research_features import FEATURE_ORDER, extract_url_features

RESEARCH_MODEL_DIR = ROOT_DIR / "model" / "research"
url_model = joblib.load(RESEARCH_MODEL_DIR / "phiusiil_no_https_rf.pkl")
text_model = joblib.load(RESEARCH_MODEL_DIR / "sms_spam_word_char_logreg.pkl")

app = Flask(__name__)
FRONTEND_ORIGIN = "http://127.0.0.1:5500"


@app.after_request
def add_cors_headers(response):
    if request.headers.get("Origin") == FRONTEND_ORIGIN:
        response.headers["Access-Control-Allow-Origin"] = FRONTEND_ORIGIN
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response

URL_PATTERN = re.compile(
    r"""(?i)\b(?:https?://|www\.)[^\s<>'"]+"""
    r"""|\b(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s<>'"]*)?"""
)

LOOKALIKE_PATTERNS = ("arnaz0n", "paypa1", "g00gle")
URGENCY_PHRASES = (
    "urgent",
    "act now",
    "verify immediately",
    "account suspended",
)


def check_urgency(text):
    lowered = text.lower()
    return any(phrase in lowered for phrase in URGENCY_PHRASES)


def check_lookalike_domain(text):
    lowered = text.lower()
    return any(pattern in lowered for pattern in LOOKALIKE_PATTERNS)


def find_first_url(text):
    match = URL_PATTERN.search(text)
    if not match:
        return None
    return match.group(0).rstrip(".,!?;:)]}")


def simple_explanation(signals, risk_level):
    if signals:
        signal_text = ", ".join(signals)
        return (
            f"This message has a {risk_level} risk rating. "
            f"Warning signals: {signal_text}. "
            "The score is the strongest of separate experimental checks, not a "
            "calibrated overall probability. The text model covers English SMS "
            "spam-vs-ham and does not verify whether a message is genuine."
        )

    return (
        f"This message has a {risk_level} risk rating. "
        "No obvious warning signals were detected, but this does not prove the "
        "message is safe. The score is not a calibrated overall probability."
    )


def make_result(text):
    signals = []
    rule_risks = []

    if check_urgency(text):
        signals.append("Urgency language detected")
        rule_risks.append(0.45)

    if check_lookalike_domain(text):
        signals.append("Lookalike domain text detected")
        rule_risks.append(0.60)

    rule_risk = 1.0
    for risk in rule_risks:
        rule_risk *= 1.0 - risk
    rule_risk = 1.0 - rule_risk

    url_phishing_score = None
    url = find_first_url(text)

    if url:
        features = pd.DataFrame([extract_url_features(url)], columns=FEATURE_ORDER)
        probabilities = url_model.predict_proba(features)[0]
        phishing_index = list(url_model.classes_).index(1)
        url_phishing_score = float(probabilities[phishing_index])

        if url_phishing_score >= 0.50:
            signals.append("URL model found phishing-like URL patterns")

    text_probabilities = text_model.predict_proba([text])[0]
    spam_index = list(text_model.classes_).index(1)
    message_spam_score = float(text_probabilities[spam_index])
    if message_spam_score >= 0.50:
        signals.append("Text model found spam-like wording")

    # The component models have separate labels and are not calibrated as one
    # overall genuineness probability. Report the strongest component estimate.
    component_scores = [rule_risk, message_spam_score]
    if url_phishing_score is not None:
        component_scores.append(url_phishing_score)
    risk_score = max(0, min(100, round(max(component_scores) * 100)))

    if risk_score >= 70:
        risk_level = "high"
    elif risk_score >= 40:
        risk_level = "medium"
    else:
        risk_level = "low"

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "signals": signals,
        "explanation": simple_explanation(signals, risk_level),
        "component_scores": {
            "url_phishing": {
                "score": round(url_phishing_score * 100) if url_phishing_score is not None else None,
                "scope": "URL-only phishing-pattern estimate; not live reputation or page inspection",
            },
            "message_spam": {
                "score": round(message_spam_score * 100),
                "scope": "English SMS spam-vs-ham estimate; not a general scam or phishing classifier",
            },
        },
        "score_note": "The displayed score is the strongest of separate experimental signals, not a calibrated probability that a message is genuine or malicious.",
    }


@app.post("/check")
def check():
    data = request.get_json(silent=True)

    if not isinstance(data, dict) or not isinstance(data.get("text"), str):
        return jsonify({
            "risk_score": 0,
            "risk_level": "low",
            "signals": [],
            "explanation": "Please send JSON with a string field named text.",
        }), 400

    return jsonify(make_result(data["text"]))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
