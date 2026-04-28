import re

BLOCKED_TERMS = ("diagnose", "diagnosis", "cure", "treat", "prescription")
# Whole words only, so "treatment" or "untreated" are left alone.
BLOCKED_PATTERN = re.compile(
    r"\b(" + "|".join(BLOCKED_TERMS) + r")\b", flags=re.IGNORECASE
)


def _sanitize(text):
    def replace(match):
        word = match.group(0)
        return "Medical advice" if word[0].isupper() else "medical advice"

    return BLOCKED_PATTERN.sub(replace, text)
ESCALATION_TEXT = (
    "Contact a doctor or pharmacist before changing habits or medication. Seek "
    "emergency help immediately for severe symptoms such as trouble breathing, "
    "fainting, chest pain, severe bleeding, or confusion."
)


class SafetyGuardAgent:
    def run(self, intake_result, risk_result, recommendation_result):
        final_recommendation = dict(recommendation_result)
        modifications = []
        safe_to_display = True

        if intake_result.get("error") and risk_result["confidence_score"] <= 40:
            safe_to_display = False
            final_recommendation["summary"] = (
                "Insufficient data for this medicine. Please consult a pharmacist "
                "or doctor."
            )
            modifications.append("blocked_low_confidence")

        summary = final_recommendation.get("summary", "")
        sanitized_summary = _sanitize(summary)
        changed = sanitized_summary != summary
        final_recommendation["summary"] = sanitized_summary

        sanitized_items = []
        for item in final_recommendation.get("recommendations", []):
            item = dict(item)
            text = item.get("recommendation", "")
            item["recommendation"] = _sanitize(text)
            changed = changed or item["recommendation"] != text
            sanitized_items.append(item)
        final_recommendation["recommendations"] = sanitized_items

        if changed:
            modifications.append("removed_diagnosis_language")

        if risk_result["risk_level"] == "High":
            final_recommendation["see_doctor"] = True
            if ESCALATION_TEXT not in final_recommendation["summary"]:
                final_recommendation["summary"] = (
                    f"{final_recommendation['summary']} {ESCALATION_TEXT}"
                )
                modifications.append("added_high_risk_escalation")

        return {
            "safe_to_display": safe_to_display,
            "final_recommendation": final_recommendation,
            "modifications_made": modifications,
        }
