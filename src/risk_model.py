from pathlib import Path

import pandas as pd
from rapidfuzz import process


DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "drug_food_interactions.csv"
REQUIRED_COLUMNS = {
    "Medicine",
    "Food",
    "Interaction_Type",
    "Severity",
    "Effect",
    "Recommendation",
}
ALLOWED_SEVERITIES = {"Low", "Medium", "High"}


class DatasetValidationError(ValueError):
    """Raised when the interaction dataset is unsafe to use."""


def load_dataset(path=DATA_PATH):
    dataset = pd.read_csv(path)
    missing_columns = sorted(REQUIRED_COLUMNS - set(dataset.columns))
    if missing_columns:
        raise DatasetValidationError(
            f"Dataset is missing required columns: {', '.join(missing_columns)}"
        )

    dataset["Medicine"] = dataset["Medicine"].str.strip()
    dataset["Food"] = dataset["Food"].str.strip()
    dataset["Severity"] = dataset["Severity"].str.strip().str.capitalize()
    return dataset


def validate_dataset(dataset):
    issues = {
        "missing_columns": [],
        "null_counts": {},
        "invalid_severities": [],
        "duplicate_pairs": [],
    }

    missing_columns = sorted(REQUIRED_COLUMNS - set(dataset.columns))
    issues["missing_columns"] = missing_columns
    if missing_columns:
        raise DatasetValidationError(
            f"Dataset is missing required columns: {', '.join(missing_columns)}"
        )

    null_counts = dataset[list(REQUIRED_COLUMNS)].isna().sum()
    issues["null_counts"] = {
        column: int(count) for column, count in null_counts.items() if count > 0
    }
    if issues["null_counts"]:
        raise DatasetValidationError(
            f"Dataset contains null values: {issues['null_counts']}"
        )

    invalid_severities = sorted(set(dataset["Severity"]) - ALLOWED_SEVERITIES)
    issues["invalid_severities"] = invalid_severities
    if invalid_severities:
        raise DatasetValidationError(
            f"Dataset contains invalid severity values: {', '.join(invalid_severities)}"
        )

    duplicates = dataset[
        dataset.duplicated(["Medicine", "Food"], keep=False)
    ][["Medicine", "Food"]].drop_duplicates()
    issues["duplicate_pairs"] = duplicates.to_dict("records")

    return issues


df = load_dataset()
DATASET_VALIDATION = validate_dataset(df)

severity_map = {
    "Low": 1,
    "Medium": 2,
    "High": 3
}

frequency_map = {
    "Rare": 1,
    "Sometimes": 2,
    "Daily": 3
}


def get_medicine_info(medicine):
    medicine = medicine.strip()
    medicine_lookup = {
        med.lower(): med for med in sorted(df["Medicine"].dropna().unique())
    }
    medicine_list = list(medicine_lookup.keys())

    match, score, _ = process.extractOne(medicine.lower(), medicine_list)

    if score >= 70:
        result = df[df["Medicine"].str.lower() == match]
        return result, medicine_lookup[match], score
    else:
        return None, medicine_lookup.get(match, match), score


def calculate_risk(medicines, habits):
    results = []

    for med in medicines:
        for food, freq in habits.items():
            match = df[(df["Medicine"] == med) & (df["Food"] == food)]

            if not match.empty:
                severity = match.iloc[0]["Severity"]
                score = severity_map[severity] * frequency_map[freq]

                results.append({
                    "Medicine": med,
                    "Food": food,
                    "Risk Score": score,
                    "Severity": severity,
                    "Effect": match.iloc[0]["Effect"],
                    "Recommendation": match.iloc[0]["Recommendation"]
                })

    return results
