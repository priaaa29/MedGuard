import pandas as pd

df = pd.read_csv("data/drug_food_interactions.csv")

df["Medicine"] = df["Medicine"].str.strip()
df["Food"] = df["Food"].str.strip()
df["Severity"] = df["Severity"].str.capitalize()

def get_medicine_info(medicine):
    result = df[df["Medicine"].str.lower() == medicine.lower()]
    if not result.empty:
        return result, medicine, 100
    return None, medicine, 0
