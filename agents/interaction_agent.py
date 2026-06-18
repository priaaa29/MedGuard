from mcp_server.medicine_server import get_interactions, get_severity_summary


class InteractionAgent:
    def run(self, intake_result):
        medicine_name = intake_result.get("matched_name")
        if not medicine_name:
            return {
                "medicine_name": None,
                "interactions": [],
                "interactions_by_severity": {"High": [], "Medium": [], "Low": []},
                "severity_summary": {"High": 0, "Medium": 0, "Low": 0},
                "error": intake_result.get("error") or "medicine_not_found",
            }

        interaction_response = get_interactions(medicine_name)
        severity_response = get_severity_summary(medicine_name)

        if interaction_response["error"]:
            return {
                "medicine_name": medicine_name,
                "interactions": [],
                "interactions_by_severity": {"High": [], "Medium": [], "Low": []},
                "severity_summary": {"High": 0, "Medium": 0, "Low": 0},
                "error": interaction_response["error"],
            }

        return {
            "medicine_name": interaction_response["medicine_name"],
            "interactions": interaction_response["interactions"],
            "interactions_by_severity": interaction_response["interactions_by_severity"],
            "severity_summary": severity_response["severity_summary"],
            "error": None,
        }
