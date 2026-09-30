import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

import joblib
from flask import Flask, jsonify, request
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from model.train_model import extract_features

MODEL_PATH = ROOT_DIR / "model" / "aegis_model.pkl"
model = joblib.load(MODEL_PATH)

app = Flask(__name__)
MAX_TEXT_LENGTH = 5000
MAX_REQUEST_BYTES = 64 * 1024
app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BYTES
FRONTEND_ORIGIN = "http://127.0.0.1:5500"
# Exact official event hosts only; subdomains and suffix matches are excluded.
VERIFIED_EVENT_HOSTS = frozenset({"quantumweek.tech", "www.quantumweek.tech"})


@app.after_request
def add_cors_headers(response):
    if request.headers.get("Origin") == FRONTEND_ORIGIN:
        response.headers["Access-Control-Allow-Origin"] = FRONTEND_ORIGIN
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


def _input_error(message, status=400):
    return jsonify({
        "risk_score": 0,
        "risk_level": "low",
        "signals": [],
        "explanation": message,
    }), status


@app.errorhandler(RequestEntityTooLarge)
def request_too_large(_error):
    return _input_error(
        f"Request body is too large. Keep it under {MAX_REQUEST_BYTES // 1024} KB.",
        413,
    )


def _read_text_payload(*, internship=False):
    context = (
        " This check analyzes only pasted offer text; it does not verify the "
        "company or search reviews or public records."
        if internship else ""
    )

    def invalid(message, status=400):
        return None, _input_error(message + context, status)

    if not request.is_json:
        return invalid("Content-Type must be application/json.")

    try:
        data = request.get_json()
    except BadRequest:
        return invalid("Request body contains malformed JSON.")

    if not isinstance(data, dict):
        return invalid("Request body must be a JSON object with a text field.")

    if "text" not in data:
        return invalid("Request JSON is missing the required text field.")

    text = data["text"]
    if not isinstance(text, str):
        return invalid("The text field must be a string.")

    if not text.strip():
        return invalid("The text field must not be empty.")

    if len(text) > MAX_TEXT_LENGTH:
        return invalid(f"Text is too long. Maximum length is {MAX_TEXT_LENGTH} characters.")

    return text, None

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
    for match in URL_PATTERN.finditer(text):
        candidate = match.group(0).rstrip(".,!?;:)]}")
        parsed_candidate = candidate if "://" in candidate else f"//{candidate}"
        try:
            parsed = urlsplit(parsed_candidate)
            hostname = parsed.hostname
            # Accessing .port validates malformed or out-of-range ports.
            parsed.port
        except (ValueError, UnicodeError):
            continue

        if hostname and parsed.scheme.lower() in {"", "http", "https"}:
            return candidate

    return None


def is_verified_event_host(url):
    candidate = url if "://" in url else f"//{url}"
    try:
        hostname = urlsplit(candidate).hostname
    except ValueError:
        return False
    return hostname in VERIFIED_EVENT_HOSTS


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

    if url and not is_verified_event_host(url):
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
    text, error = _read_text_payload()
    if error:
        return error
    return jsonify(make_result(text))


# Internship-offer checks deliberately use only the submitted text. They do not
# verify an employer or contact any external service.
INTERNSHIP_FEE_TERMS = re.compile(
    r"\b(?:fees?|deposits?|registration|application|enrollment|training|"
    r"processing|security)\b",
    re.IGNORECASE,
)
PAYMENT_DEMAND = re.compile(
    r"\b(?:you|applicants?|candidates?|interns?)\s+"
    r"(?:must|need to|have to|are required to|should|will have to)\s+"
    r"(?:pay|send|transfer|deposit)\b|"
    r"^\s*(?:please\s+)?(?:pay|send|transfer|deposit)\b",
    re.IGNORECASE,
)
UPFRONT_CONTEXT = re.compile(
    r"\bupfront\b|\b(?:before|prior to)\s+(?:you\s+)?"
    r"(?:apply|applying|application|accept|accepting|joining|starting|"
    r"beginning|onboarding|receiving|securing|confirming)\b|"
    r"\bto\s+(?:apply|be considered|accept|secure|confirm|receive|proceed|"
    r"join|start|begin|onboard)\b|"
    r"\b(?:today|tonight|now|immediately|right away|within\s+\d+\s+"
    r"(?:minutes?|hours?|days?))\b",
    re.IGNORECASE,
)
PAYMENT_WORD = re.compile(r"\b(?:pay|payment|send|transfer|deposit)\b", re.IGNORECASE)
FAST_PAYMENT_DEADLINE = re.compile(
    r"\b(?:today|tonight|now|immediately|right away|as soon as possible|"
    r"within\s+\d+\s+(?:minutes?|hours?|days?)|by\s+(?:today|tonight|\d{1,2}\s*(?:am|pm)?)|"
    r"before\s+the\s+deadline)\b",
    re.IGNORECASE,
)
GUARANTEED_OUTCOME = re.compile(
    r"\b(?:guaranteed|guarantees|guarantee|assured|assures|assurance)\b"
    r".{0,60}\b(?:job|placement|selection|internship|employment|offer|"
    r"salary|stipend|income)\b|"
    r"\b(?:job|placement|selection|internship|employment|offer|salary|"
    r"stipend|income)\b.{0,40}\b(?:guaranteed|assured)\b",
    re.IGNORECASE,
)
NEGATED_GUARANTEE = re.compile(
    r"\b(?:not|never|no|cannot|can't|can not|do not|don't|does not|doesn't)\s+"
    r"(?:be\s+)?(?:a\s+)?(?:guaranteed|guarantee|assured|assure|assurance)\b|"
    r"\b(?:job|placement|selection|internship|employment|offer|salary|stipend|income)\b"
    r".{0,40}\bnot\s+(?:guaranteed|assured)\b|\bno\s+guarantee\b",
    re.IGNORECASE,
)
NEGATED_FEE_REQUEST = re.compile(
    r"\b(?:no|without)\s+(?:upfront\s+)?(?:(?:registration|application|"
    r"enrollment|training|processing|security)\s+)?fees?\b|"
    r"\b(?:never|do not|don't|must not|should not|not required to)\s+"
    r"(?:pay|send|transfer|deposit)\b|\bno need to pay\b",
    re.IGNORECASE,
)


def _offer_sentences(text):
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+|\r?\n+", text) if part.strip()]


def _requests_upfront_fee(text):
    for sentence in _offer_sentences(text):
        # A plain mention of a fee is not enough: the same sentence must ask
        # the applicant/candidate to pay or transfer it. Negated statements
        # such as "no fee required" and "never pay an enrollment fee" are ignored.
        if NEGATED_FEE_REQUEST.search(sentence):
            continue
        if (
            PAYMENT_DEMAND.search(sentence)
            and INTERNSHIP_FEE_TERMS.search(sentence)
            and UPFRONT_CONTEXT.search(sentence)
        ):
            return True
    return False


def _pressures_quick_payment(text):
    for sentence in _offer_sentences(text):
        if PAYMENT_WORD.search(sentence) and FAST_PAYMENT_DEADLINE.search(sentence):
            if not NEGATED_FEE_REQUEST.search(sentence):
                return True
    return False


def _promises_guaranteed_outcome(text):
    return any(
        GUARANTEED_OUTCOME.search(sentence) and not NEGATED_GUARANTEE.search(sentence)
        for sentence in _offer_sentences(text)
    )


def make_internship_result(text):
    signals = []
    score = 0

    if _requests_upfront_fee(text):
        signals.append("Upfront payment requested")
        score += 60

    if _pressures_quick_payment(text):
        signals.append("Pressure to pay quickly")
        score += 25

    if _promises_guaranteed_outcome(text):
        signals.append("Guaranteed outcome claim detected")
        score += 20

    score = min(100, score)
    if score >= 70:
        level = "high"
    elif score >= 40:
        level = "medium"
    else:
        level = "low"

    if signals:
        finding_summary = ", ".join(signals)
        explanation = (
            f"This heuristic warning score is {score}/100 ({level}). "
            f"Warning signs in the pasted offer: {finding_summary}. "
        )
    else:
        explanation = (
            "No internship warning rules matched the pasted offer. "
            "That does not mean the offer is safe. "
        )

    explanation += (
        "This check analyzes only the pasted text. It does not verify the company "
        "or offer, or search reviews or public records. The score is not a probability "
        "or proof of fraud or safety; verify through the company’s official channels."
    )
    return {
        "risk_score": score,
        "risk_level": level,
        "signals": signals,
        "explanation": explanation,
    }


@app.post("/check/internship")
def check_internship():
    text, error = _read_text_payload(internship=True)
    if error:
        return error
    return jsonify(make_internship_result(text))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
