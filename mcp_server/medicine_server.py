import sys
from pathlib import Path


SRC_PATH = Path(__file__).resolve().parent.parent / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.append(str(SRC_PATH))

from risk_model import get_medicine_info


SEVERITY_ORDER = {"High": 3, "Medium": 2, "Low": 1}
EMPTY_GROUPS = {"High": [], "Medium": [], "Low": []}


def _records_for_medicine(medicine_name):
    result, matched_name, score = get_medicine_info(medicine_name)
    if result is None or result.empty:
        return [], matched_name, score

    records = (
        result.copy()
        .assign(**{"Severity Score": result["Severity"].map(SEVERITY_ORDER)})
        .sort_values("Severity Score", ascending=False)
        .drop(columns=["Severity Score"])
        .to_dict("records")
    )
    return records, matched_name, score


def _group_by_severity(interactions):
    grouped = {"High": [], "Medium": [], "Low": []}
    for interaction in interactions:
        grouped[interaction["Severity"]].append(interaction)
    return grouped


def search_medicine(name):
    result, matched_name, score = get_medicine_info(name)
    found = result is not None and not result.empty

    return {
        "query": name.strip(),
        "medicine_name": matched_name if found else None,
        "suggested_name": matched_name,
        "match_score": score,
        "found": found,
    }


def get_interactions(medicine_name):
    interactions, matched_name, score = _records_for_medicine(medicine_name)
    if not interactions:
        return {
            "medicine_name": None,
            "suggested_name": matched_name,
            "match_score": score,
            "interactions": [],
            "interactions_by_severity": dict(EMPTY_GROUPS),
            "error": "medicine_not_found",
        }

    return {
        "medicine_name": matched_name,
        "suggested_name": matched_name,
        "match_score": score,
        "interactions": interactions,
        "interactions_by_severity": _group_by_severity(interactions),
        "error": None,
    }


def get_severity_summary(medicine_name):
    interactions, matched_name, score = _records_for_medicine(medicine_name)
    summary = {"High": 0, "Medium": 0, "Low": 0}
    for interaction in interactions:
        summary[interaction["Severity"]] += 1

    return {
        "medicine_name": matched_name if interactions else None,
        "suggested_name": matched_name,
        "match_score": score,
        "severity_summary": summary,
        "error": None if interactions else "medicine_not_found",
    }


def run_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            "The optional 'mcp' package is required to run the MCP stdio server."
        ) from exc

    server = FastMCP("medguard-medicine-server")
    server.tool()(search_medicine)
    server.tool()(get_interactions)
    server.tool()(get_severity_summary)
    server.run(transport="stdio")


if __name__ == "__main__":
    run_server()
