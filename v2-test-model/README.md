# Aegis V2 test model

This folder is a self-contained V2 test package connected to two local
experimental models: URL phishing-pattern scoring and English SMS
spam-vs-ham scoring. The existing project files remain separate. This is a
test package, not the later fast-track/main model.

## What it checks

- **URL phishing patterns:** a 23-feature Random Forest calculates features
  from the URL string. It does not open the URL, inspect its page, check DNS or
  certificates, follow redirects, or query threat-intelligence services.
- **SMS spam-like wording:** a word-and-character TF-IDF Logistic Regression
  distinguishes spam from ham using an older English SMS collection. It is not
  trained to identify general scams, phishing messages, malware, viruses, or
  whether a message is genuine.
- **Selected warning rules:** urgency phrases and a few hard-coded lookalike
  strings retained from the existing demo backend.

The API retains `risk_score`, `risk_level`, `signals`, and `explanation`, and
adds `component_scores` and `score_note`. The single score is the largest of
separate experimental signals; it is **not** a calibrated probability of
fraud, safety, or genuineness.

## Backend API contract

### `POST /check`

This endpoint checks pasted message text and, when it finds a parseable URL,
the URL string. It does not open the link, inspect its page, check DNS or
certificates, follow redirects, or query outside services.

Request header: `Content-Type: application/json`

Request JSON:

```json
{
  "text": "message or URL string"
}
```

`text` is required, must be a non-empty string, and can contain at most 5,000
characters. The complete request body must be at most 64 KB. Unknown JSON
fields are ignored.

Successful response JSON:

```json
{
  "risk_score": 0,
  "risk_level": "low",
  "signals": [],
  "explanation": "...",
  "component_scores": {
    "rule_warnings": {"score": 0, "scope": "..."},
    "url_phishing": {"score": null, "scope": "..."},
    "message_spam": {"score": 0, "scope": "..."}
  },
  "score_note": "..."
}
```

- `risk_score`: integer from 0 to 100; the largest available component score.
- `risk_level`: `low` below 40, `medium` from 40 through 69, `high` from 70
  through 100.
- `signals`: array of plain-English warning labels.
- `explanation`: plain-English result and model-scope limits.
- `component_scores`: objects named `rule_warnings`, `url_phishing`, and
  `message_spam`, each with a `score` and `scope`. Scores are integers from 0
  to 100; `url_phishing.score` is `null` when no valid URL string is scored.
- `score_note`: says how the scores are combined and what the models do not
  establish.

All values are experimental model or rule scores. The URL model scores
URL-string patterns only; it never fetches or inspects a site. The text model
is for English SMS spam-vs-ham only. Neither model proves that anything is safe
or fraudulent, and the combined score is not a calibrated probability.

Invalid requests return JSON with an `error` code and an `explanation`, plus an
appropriate HTTP status:

- `400`: malformed JSON, a non-object JSON body, missing `text`, a non-string
  value, or blank text.
- `413`: text over 5,000 characters or a request body over 64 KB.
- `415`: request does not use a JSON content type.
- `500`: an unexpected inference failure; details are available in the backend
  terminal, not returned to the caller.
- `404`: unknown endpoint; the error explains the two supported paths.
- `503`: one or both required model artifacts could not be loaded.

Malformed URL candidates are skipped by URL scoring rather than being allowed
to crash the request. The text model and warning rules can still evaluate the
message. When the URL model is not run, `component_scores.url_phishing.score`
is `null`.

### `GET /health`

Returns `status` and a `models` object with a `loaded` boolean and artifact name
for `url_phishing` and `message_spam`. It returns HTTP 200 when both artifacts
load and pass basic interface checks, or HTTP 503 otherwise. This endpoint
checks local artifact availability; it does not measure model accuracy.

This V2 backend supports `/check` and `/health` only. It does not provide
internship-offer verification, source research, live URL inspection, or
threat-intelligence lookups. The V2 frontend uses `/check` for message-and-URL
input. Do not present internship verification or online research as V2
capabilities.

## Run locally on Windows

Open two PowerShell terminals from this folder. In the first:

```powershell
cd path\to\aegis\v2-test-model
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python backend\app.py
```

In the second:

```powershell
cd path\to\aegis\v2-test-model
python -m http.server 5500 --directory frontend
```

Open <http://127.0.0.1:5500>. Keep the backend terminal running. Check model
availability at <http://127.0.0.1:5000/health>; the backend root path `/` is
not a web page. The backend allows the local frontend origin
`http://127.0.0.1:5500`.

## Manual smoke-check checklist

1. Start the backend and confirm `GET http://127.0.0.1:5000/health` returns
   HTTP 200 with both model `loaded` values set to `true`.
2. Start the frontend and submit a normal-looking message without a URL. Check
   that `/check` returns all six documented fields and that
   `component_scores.url_phishing.score` is `null`.
3. Submit a message with an HTTPS URL and urgency wording. Check that the
   response includes URL, text, and rule component scores where applicable,
   and that the explanation names the limited model scopes.
4. Send malformed JSON and confirm HTTP 400 with JSON `error` and
   `explanation` fields.
5. Send a string longer than 5,000 characters, then a body larger than 64 KB;
   confirm each gets HTTP 413 and a clear JSON explanation.
6. From the frontend at `http://127.0.0.1:5500`, confirm the browser request to
   `/check` succeeds and the rule, URL, and message component cards show the
   returned values (the URL score may be not applicable for text-only input).

## Evaluation summary

### URL model

- Dataset: PhiUSIIL Phishing URL (Website), UCI dataset 967; CC BY 4.0.
- Input used for training: raw URL and label only; webpage-derived features
  were excluded.
- After duplicate and near-duplicate filtering: 231,783 URLs.
- Evaluation: five-fold stratified grouping by registrable domain; seed 42.
- Pooled exploratory results at threshold 0.50: 614 false positives (0.46% of
  legitimate URLs), 996 false negatives (1.03% of phishing URLs), precision
  0.9936, recall 0.9897, F1 0.9917.
- Limitation: a fold was inspected during model iteration, and this evaluation
  is specific to PhiUSIIL. These numbers are not expected production accuracy.

### SMS model

- Dataset: SMS Spam Collection, UCI dataset 228; CC BY 4.0.
- After normalized-template grouping and duplicate handling: 5,093 messages
  (4,498 ham, 595 spam).
- Evaluation: five-fold stratified grouping by normalized message template;
  seed 42.
- Pooled results at threshold 0.50: 17 false positives (0.38% of ham), 35
  false negatives (5.88% of spam), precision 0.9705, recall 0.9412, F1 0.9556.
- Limitation: the corpus is small, old, English-only, and SMS-focused. It does
  not establish performance on current WhatsApp messages or multilingual
  scams.

Detailed metadata and artifact hashes are in `model/research/`. No raw training
datasets are included. Both model files are provided here for this V2 test
package with the dataset attributions below.

## Dataset attribution

**PhiUSIIL:** Prasad, A. & Chandra, S. (2024). *PhiUSIIL Phishing URL
(Website)* [Dataset]. UCI Machine Learning Repository, dataset 967. DOI:
<https://doi.org/10.1016/j.cose.2023.103545>. Dataset license: Creative
Commons Attribution 4.0 International (CC BY 4.0).

**SMS Spam Collection:** Almeida, T. & Hidalgo, J. (2011). *SMS Spam
Collection* [Dataset]. UCI Machine Learning Repository, dataset 228. DOI:
<https://doi.org/10.24432/C5CC84>. Dataset license: Creative Commons
Attribution 4.0 International (CC BY 4.0).

The datasets' CC BY 4.0 attributions are included with the model metadata. See
`model/research/ATTRIBUTION.md` for the model-to-dataset mapping and limitations.
Dataset licenses do not by themselves establish a separate license for these
trained model artifacts. Confirm model-weight redistribution terms before
merging or distributing them.
