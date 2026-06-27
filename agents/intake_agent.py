import sys
from pathlib import Path

SRC_PATH = Path(__file__).resolve().parent.parent / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.append(str(SRC_PATH))

from risk_model import get_medicine_info


class IntakeAgent:
    def run(self, raw_query):
        query = raw_query.strip()
        if not query:
            return {
                "query": query,
                "matched_name": None,
                "match_score": 0,
                "needs_confirmation": False,
                "error": "empty_query",
            }

        result, matched_name, score = get_medicine_info(query)
        found = result is not None and not result.empty

        return {
            "query": query,
            "matched_name": matched_name if found else None,
            "suggested_name": matched_name,
            "match_score": score,
            "needs_confirmation": found and query.lower() != matched_name.lower(),
            "error": None if found else "medicine_not_found",
        }
