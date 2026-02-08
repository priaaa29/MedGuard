import pandas as pd
from rapidfuzz import process

df = pd.read_csv("data/drug_food_interactions.csv")

df["Medicine"] = df["Medicine"].str.strip()
df["Food"] = df["Food"].str.strip()
df["Severity"] = df["Severity"].str.capitalize()

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
    # Get unique medicine names
    medicine_list = df["Medicine"].str.lower().unique()

    # Find best match
    match, score, _ = process.extractOne(medicine.lower(), medicine_list)

    # If match is good enough
    if score >= 70:
        result = df[df["Medicine"].str.lower() == match]
        return result, match, score
    else:
        return None, match, score

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
