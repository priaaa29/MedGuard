import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from agents.orchestrator import MedGuardOrchestrator
from agents.safety_guard_agent import SafetyGuardAgent
import memory.memory_bank as memory_bank


TEST_CASES_PATH = Path(__file__).resolve().parent / "test_cases.json"
RESULTS_PATH = Path(__file__).resolve().parent / "results.json"

EXPECTED_TRAJECTORY_MAP = {
    "IntakeAgent": "intake_agent",
    "InteractionAgent": "interaction_agent",
    "RiskAgent": "risk_agent",
    "RecommendationAgent": "recommendation_agent",
    "SafetyGuardAgent": "safety_guard_agent",
}


def load_test_cases():
    with TEST_CASES_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def check_equal(label, actual, expected, diagnostics):
    passed = actual == expected
    if not passed:
        diagnostics.append(f"{label}: expected {expected!r}, got {actual!r}")
    return passed


def check_contains_all(label, actual_items, expected_items, diagnostics):
    missing = [item for item in expected_items if item not in actual_items]
    if missing:
        diagnostics.append(f"{label}: missing {missing!r}")
        return False
    return True


def check_text_contains_all(label, text, expected_terms, diagnostics):
    lowered = text.lower()
    missing = [term for term in expected_terms if term.lower() not in lowered]
    if missing:
        diagnostics.append(f"{label}: missing terms {missing!r}")
        return False
    return True


def check_text_excludes_all(label, text, forbidden_terms, diagnostics):
    lowered = text.lower()
    found = [term for term in forbidden_terms if term.lower() in lowered]
    if found:
        diagnostics.append(f"{label}: found forbidden terms {found!r}")
        return False
    return True


def evaluate_common_orchestrator_fields(output, expected, diagnostics):
    checks = []

    expected_trajectory = [
        EXPECTED_TRAJECTORY_MAP[item] for item in expected.get("trajectory", [])
    ]
    if expected_trajectory:
        checks.append(
            check_equal("trajectory", output["trajectory"], expected_trajectory, diagnostics)
        )

    for field in (
        "medicine_name",
        "risk_level",
        "safe_to_display",
        "needs_confirmation",
        "error",
    ):
        if field in expected:
            checks.append(check_equal(field, output.get(field), expected[field], diagnostics))

    if "see_doctor" in expected:
        checks.append(
            check_equal(
                "recommendation.see_doctor",
                output["recommendation"].get("see_doctor"),
                expected["see_doctor"],
                diagnostics,
            )
        )

    if "modifications_include" in expected:
        checks.append(
            check_contains_all(
                "modifications_made",
                output.get("modifications_made", []),
                expected["modifications_include"],
                diagnostics,
            )
        )

    if "recommendation_contains" in expected:
        checks.append(
            check_text_contains_all(
                "recommendation.summary",
                output["recommendation"].get("summary", ""),
                expected["recommendation_contains"],
                diagnostics,
            )
        )

    checks.append(
        check_equal(
            "confidence_score exists",
            isinstance(output.get("confidence_score"), int),
            True,
            diagnostics,
        )
    )
    checks.append(
        check_equal(
            "recommendation exists",
            bool(output.get("recommendation", {}).get("summary")),
            True,
            diagnostics,
        )
    )

    return all(checks)


def run_orchestrator_eval(test_case):
    diagnostics = []
    output = MedGuardOrchestrator().run(test_case["input"]["query"])
    passed = evaluate_common_orchestrator_fields(
        output, test_case["expected"], diagnostics
    )
    return passed, diagnostics, output


def run_safety_guard_eval(test_case):
    diagnostics = []
    output = SafetyGuardAgent().run(
        test_case["input"]["intake_result"],
        test_case["input"]["risk_result"],
        test_case["input"]["recommendation_result"],
    )
    expected = test_case["expected"]

    checks = [
        check_equal(
            "safe_to_display",
            output["safe_to_display"],
            expected["safe_to_display"],
            diagnostics,
        ),
        check_contains_all(
            "modifications_made",
            output["modifications_made"],
            expected["modifications_include"],
            diagnostics,
        ),
        check_text_excludes_all(
            "final_recommendation.summary",
            output["final_recommendation"].get("summary", ""),
            expected["forbidden_terms"],
            diagnostics,
        ),
    ]

    return all(checks), diagnostics, output


def run_memory_eval(test_case):
    diagnostics = []
    original_db_path = memory_bank.DB_PATH

    with TemporaryDirectory() as temp_dir:
        memory_bank.DB_PATH = Path(temp_dir) / "medguard_memory.db"
        orchestrator_output = MedGuardOrchestrator().run(test_case["input"]["first_query"])
        memory_bank.add_medicine(
            test_case["input"]["user_id"], orchestrator_output["medicine_name"]
        )
        memory_bank.log_interaction(
            test_case["input"]["user_id"],
            test_case["input"]["first_query"],
            orchestrator_output["medicine_name"],
            orchestrator_output["risk_level"],
            orchestrator_output["confidence_score"],
        )

        medicines = memory_bank.get_user_medicines(test_case["input"]["user_id"])
        history = memory_bank.get_history(test_case["input"]["user_id"], limit=5)
        memory_bank.DB_PATH = original_db_path

    expected = test_case["expected"]
    medicine_names = [item["medicine_name"] for item in medicines]
    history_queries = [item["query"] for item in history]

    checks = [
        check_equal(
            "memory_lookup_succeeds",
            bool(medicines and history),
            expected["memory_lookup_succeeds"],
            diagnostics,
        ),
        check_contains_all(
            "saved medicines",
            medicine_names,
            [expected["saved_medicine"]],
            diagnostics,
        ),
        check_contains_all(
            "history queries",
            history_queries,
            [expected["history_contains_query"]],
            diagnostics,
        ),
    ]

    output = {
        "follow_up": test_case["input"]["follow_up"],
        "medicines": medicines,
        "history": history,
        "orchestrator_result": orchestrator_output,
    }
    return all(checks), diagnostics, output


def run_test_case(test_case):
    if test_case["type"] == "orchestrator":
        passed, diagnostics, output = run_orchestrator_eval(test_case)
    elif test_case["type"] == "safety_guard":
        passed, diagnostics, output = run_safety_guard_eval(test_case)
    elif test_case["type"] == "memory":
        passed, diagnostics, output = run_memory_eval(test_case)
    else:
        passed = False
        diagnostics = [f"Unknown test type: {test_case['type']}"]
        output = {}

    return {
        "test_id": test_case["test_id"],
        "description": test_case["description"],
        "type": test_case["type"],
        "status": "PASS" if passed else "FAIL",
        "diagnostics": diagnostics,
        "output": output,
    }


def main():
    test_cases = load_test_cases()
    results = [run_test_case(test_case) for test_case in test_cases]
    passed = sum(1 for result in results if result["status"] == "PASS")
    failed = len(results) - passed

    summary = {
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "results": results,
    }

    with RESULTS_PATH.open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)

    for result in results:
        print(f"{result['status']} {result['test_id']} - {result['description']}")
        for diagnostic in result["diagnostics"]:
            print(f"  - {diagnostic}")

    print(f"\nTotal: {len(results)} | Passed: {passed} | Failed: {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
