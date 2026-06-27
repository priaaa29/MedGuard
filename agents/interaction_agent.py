import sys
from pathlib import Path

SRC_PATH = Path(__file__).resolve().parent.parent / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.append(str(SRC_PATH))

from risk_model import get_medicine_info


class InteractionAgent:
    def run(self, intake_result):
        medicine_name = intake_result.get("matched_name")
        if not medicine_name:
            return {
                "medicine_name": None,
                "interactions": [],
                "interactions_by_severity": {"High": [], "Medium": [], "Low": []},
                "error": intake_result.get("error") or "medicine_not_found",
            }

        result, _, _ = get_medicine_info(medicine_name)
        if result is None or result.empty:
            return {
                "medicine_name": medicine_name,
                "interactions": [],
                "interactions_by_severity": {"High": [], "Medium": [], "Low": []},
                "error": "interactions_not_found",
            }

        severity_order = {"High": 3, "Medium": 2, "Low": 1}
        records = (
            result.copy()
            .assign(**{"Severity Score": result["Severity"].map(severity_order)})
            .sort_values("Severity Score", ascending=False)
            .drop(columns=["Severity Score"])
            .to_dict("records")
        )

        grouped = {"High": [], "Medium": [], "Low": []}
        for interaction in records:
            grouped[interaction["Severity"]].append(interaction)

        return {
            "medicine_name": medicine_name,
            "interactions": records,
            "interactions_by_severity": grouped,
            "error": None,
        }
