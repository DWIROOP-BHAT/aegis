# Aegis V2 test model

This folder is a self-contained test copy of the current Aegis frontend and a
backend connected to two local experimental models: URL phishing-pattern
scoring and English SMS spam-vs-ham scoring. The existing project files remain
separate. This is a V2 test package, not the later fast-track/main model.

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
fraud, safety, or genuineness. The current frontend does not yet display the
individual component scores.

## Run locally on Windows

Open two PowerShell terminals. In the first:

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

Open <http://127.0.0.1:5500>. Keep the backend terminal running at
<http://127.0.0.1:5000>. The backend allows the local frontend origin
`http://127.0.0.1:5500`.

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
