# V2 model artifact attribution

The model files in this folder were trained from the datasets listed below.
The datasets themselves are not included. Dataset labels are used for the
specific tasks stated here; they do not establish general scam or malware
detection.

## URL phishing model

- Artifact: `phiusiil_no_https_rf.pkl`
- SHA-256: `6F7F45AA8FE3D96EAD926CDBA3973E728B1CB458AF421C93999DE32CF457607F`
- Dataset: PhiUSIIL Phishing URL (Website), UCI dataset 967.
- Creators: Arvind Prasad and Shalini Chandra.
- License: Creative Commons Attribution 4.0 International (CC BY 4.0), as
  stated on the UCI dataset page.
- Required credit: Prasad, A. & Chandra, S. (2024). *PhiUSIIL Phishing URL
  (Website)* [Dataset]. UCI Machine Learning Repository. DOI:
  https://doi.org/10.1016/j.cose.2023.103545. License: CC BY 4.0.
- Model training used the dataset's raw `URL` and `label` columns. Website
  content and precomputed webpage-derived features were excluded.
- Class mapping for the model: `0 = legitimate`, `1 = phishing`.
- Dataset SHA-256 and feature order are in
  `final_candidate_phiusiil_no_https_rf.json`.

## SMS spam model

- Artifact: `sms_spam_word_char_logreg.pkl`
- SHA-256: `F7E83324A41652953406E169A194457EDBDD1354C22DEC747C19E69EB58ADD71`
- Dataset: SMS Spam Collection, UCI dataset 228, DOI `10.24432/C5CC84`.
- Creators: Tiago Almeida and Jos Hidalgo.
- License: Creative Commons Attribution 4.0 International (CC BY 4.0), as
  stated on the UCI dataset page.
- Required credit: Almeida, T. & Hidalgo, J. (2011). *SMS Spam Collection*
  [Dataset]. UCI Machine Learning Repository. DOI:
  https://doi.org/10.24432/C5CC84. License: CC BY 4.0.
- Model task: English SMS spam (`1`) versus ham (`0`). It is not a general
  scam, phishing-message, malware, virus, or genuineness classifier.
- Dataset checksum, preprocessing, and evaluation details are in
  `sms_spam_metrics.json`.

## Evaluation limitations

The URL model's grouped PhiUSIIL evaluation was exploratory; an evaluation fold
was inspected during model iteration. The SMS model was evaluated on grouped
templates from a small, historical English SMS corpus. Both scores are limited
to these datasets and are not real-world performance guarantees. The models
are published here for the explicitly requested V2 test package; they are not
approved as production classifiers.
