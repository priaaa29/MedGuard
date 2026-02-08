import pandas as pd
from rapidfuzz import process

df = pd.read_csv("data/drug_food_interactions.csv")

df["Medicine"] = df["Medicine"].str.strip()
df["Food"] = df["Food"].str.strip()
df["Severity"] = df["Severity"].str.capitalize()

def get_medicine_info(medicine):
    medicine_list = df["Medicine"].str.lower().unique()

    match, score, _ = process.extractOne(medicine.lower(), medicine_list)

    if score >= 70:
        result = df[df["Medicine"].str.lower() == match]
        return result, match, score
    else:
        return None, match, score
