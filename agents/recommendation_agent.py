class RecommendationAgent:
    def run(self, interaction_result, risk_result):
        interactions = interaction_result.get("interactions", [])
        if not interactions:
            return {
                "summary": "Medicine not found. Try a different spelling.",
                "foods_to_avoid": [],
                "recommendations": [],
                "see_doctor": False,
            }

        foods_to_avoid = []
        recommendations = []
        for interaction in interactions:
            food = interaction["Food"]
            if food not in foods_to_avoid:
                foods_to_avoid.append(food)
            recommendations.append(
                {
                    "food": food,
                    "severity": interaction["Severity"],
                    "effect": interaction["Effect"],
                    "recommendation": interaction["Recommendation"],
                }
            )

        medicine_name = interaction_result["medicine_name"]
        risk_level = risk_result["risk_level"]
        if risk_level == "High":
            summary = (
                f"{medicine_name} has high-risk food or drink interactions in this "
                "dataset. Review the listed items and speak with a doctor or "
                "pharmacist before making changes."
            )
        elif risk_level == "Medium":
            summary = (
                f"{medicine_name} has interactions that may affect effectiveness or "
                "side effects. Ask a pharmacist or doctor if you use these foods or "
                "drinks often."
            )
        else:
            summary = (
                f"{medicine_name} has no major risks in this dataset, but the list "
                "may not include every possible interaction."
            )

        return {
            "summary": summary,
            "foods_to_avoid": foods_to_avoid,
            "recommendations": recommendations,
            "see_doctor": risk_level == "High",
        }
