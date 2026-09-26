import ipaddress
from urllib.parse import urlparse

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split


FEATURE_NAMES = [
    "url_length",
    "dot_count",
    "has_ip_address",
    "has_at_symbol",
    "starts_with_https",
    "hyphen_count",
]


def extract_features(url):
    """Return URL features in the same order used by the backend."""
    url = str(url).strip()
    parsed = urlparse(url if "://" in url else f"//{url}")
    hostname = parsed.hostname or ""

    try:
        ipaddress.ip_address(hostname)
        has_ip_address = 1
    except ValueError:
        has_ip_address = 0

    return [
        len(url),
        url.count("."),
        has_ip_address,
        int("@" in url),
        int(url.lower().startswith("https://")),
        url.count("-"),
    ]


def read_url_list(filename, label):
    """Read a CSV URL list and attach its phishing/legitimate label."""
    values = pd.read_csv(filename, header=None, dtype=str).iloc[:, 0].dropna()
    values = values.str.strip()
    values = values[~values.str.lower().isin({"url", "urls", "domain"})]
    return pd.DataFrame({"url": values, "label": label})


def main():
    phishing = read_url_list("urlsfish.csv", label=1)
    legitimate = read_url_list("urlsgood.csv", label=0)
    data = pd.concat([phishing, legitimate], ignore_index=True)

    X = pd.DataFrame(
        data["url"].map(extract_features).tolist(),
        columns=FEATURE_NAMES,
    )
    y = data["label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    model = RandomForestClassifier(
        n_estimators=200,
        random_state=42,
        class_weight="balanced",
    )
    model.fit(X_train, y_train)

    print(f"Test accuracy: {model.score(X_test, y_test):.4f}")
    joblib.dump(model, "aegis_model.pkl")
    print("Saved model to aegis_model.pkl")


if __name__ == "__main__":
    main()