import re
import sys
from pathlib import Path

import joblib
from flask import Flask, jsonify, request

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from model.train_model import extract_features

MODEL_PATH = ROOT_DIR / "model" / "aegis_model.pkl"
model = joblib.load(MODEL_PATH)

app = Flask(__name__)

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
            "Treat this as a warning, not a guarantee."
        )

    return (
        f"This message has a {risk_level} risk rating. "
        "No obvious warning signals were detected, but this is not a guarantee "
        "that the message is safe."
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

    model_risk = 0.0
    url = find_first_url(text)

    if url:
        features = extract_features(url)
        probabilities = model.predict_proba([features])[0]
        classes = list(model.classes_)
        phishing_index = classes.index(1)
        model_risk = float(probabilities[phishing_index])

        if model_risk >= 0.50:
            signals.append("Suspicious URL pattern detected")

    combined_risk = 1.0 - ((1.0 - rule_risk) * (1.0 - model_risk))
    risk_score = max(0, min(100, round(combined_risk * 100)))

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