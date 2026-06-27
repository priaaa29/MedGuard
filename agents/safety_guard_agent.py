BLOCKED_TERMS = ("diagnose", "diagnosis", "cure", "treat", "prescription")
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
        sanitized_summary = summary
        for term in BLOCKED_TERMS:
            sanitized_summary = sanitized_summary.replace(term, "medical advice")
            sanitized_summary = sanitized_summary.replace(term.title(), "Medical advice")

        if sanitized_summary != summary:
            final_recommendation["summary"] = sanitized_summary
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
