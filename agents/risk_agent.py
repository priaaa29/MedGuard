class RiskAgent:
    def run(self, intake_result, interaction_result):
        interactions = interaction_result.get("interactions", [])
        severities = [item["Severity"] for item in interactions]

        high_count = severities.count("High")
        medium_count = severities.count("Medium")
        low_count = severities.count("Low")

        if high_count:
            risk_level = "High"
        elif medium_count:
            risk_level = "Medium"
        elif low_count:
            risk_level = "Low"
        else:
            risk_level = "Not Found"

        confidence_score = int(round(intake_result.get("match_score", 0)))
        if interaction_result.get("error"):
            confidence_score = min(confidence_score, 40)

        return {
            "risk_level": risk_level,
            "confidence_score": confidence_score,
            "interaction_count": len(interactions),
            "high_count": high_count,
            "medium_count": medium_count,
            "low_count": low_count,
        }
