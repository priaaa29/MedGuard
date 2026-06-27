import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from agents.orchestrator import MedGuardOrchestrator
from memory.memory_bank import (
    add_medicine,
    get_history,
    get_user_medicines,
    log_interaction,
)
from risk_model import DATASET_VALIDATION


SEVERITY_DISPLAY = {
    "High": {
        "title": "🔴 High Risk Interactions",
        "renderer": st.error,
    },
    "Medium": {
        "title": "🟡 Medium Risk Interactions",
        "renderer": st.warning,
    },
    "Low": {
        "title": "🟢 Low Risk Interactions",
        "renderer": st.success,
    },
}


st.set_page_config(page_title="MedGuard AI", layout="centered")
orchestrator = MedGuardOrchestrator()


def render_sidebar(user_id):
    st.sidebar.header("User")
    st.sidebar.caption("Used only to separate local medicine profiles.")

    st.sidebar.markdown("### My Medicine Profile")
    medicines = get_user_medicines(user_id)
    if medicines:
        for medicine in medicines:
            st.sidebar.write(f"• {medicine['medicine_name']}")
    else:
        st.sidebar.caption("No saved medicines yet.")

    st.sidebar.markdown("### Recent Query History")
    history = get_history(user_id, limit=5)
    if history:
        for item in history:
            st.sidebar.caption(
                f"{item['query']} → {item['medicine_name'] or 'Not found'} "
                f"({item['risk_level']}, {item['confidence_score']}/100)"
            )
    else:
        st.sidebar.caption("No recent queries yet.")


def render_interaction_group(agent_result, severity):
    group = agent_result["interactions_by_severity"].get(severity, [])
    if not group:
        return

    display = SEVERITY_DISPLAY[severity]
    display["renderer"](display["title"])

    for row in group:
        st.markdown(f"**{row['Medicine']} + {row['Food']}**")
        st.write(f"Why: {row['Effect']}")
        st.write(f"Fix: {row['Recommendation']}")
        st.markdown("---")


def render_safety_summary(agent_result):
    recommendation = agent_result["recommendation"]

    st.info(
        "Do not stop, skip, or change any medication without speaking to a doctor "
        "or pharmacist."
    )

    if recommendation.get("summary"):
        st.write(recommendation["summary"])

    if agent_result["risk_level"] == "High":
        st.error(
            "🚨 High-risk interactions detected. Contact a doctor or pharmacist "
            "before changing habits or medication. Seek emergency help immediately "
            "for severe symptoms such as trouble breathing, fainting, chest pain, "
            "severe bleeding, or confusion."
        )
    elif agent_result["risk_level"] == "Medium":
        st.warning(
            "⚠️ Some interactions may affect effectiveness or side effects. "
            "Ask a doctor or pharmacist for guidance."
        )
    else:
        st.success(
            "✅ No major risks detected in this dataset. Check with a healthcare "
            "professional if you are unsure."
        )


def render_results(agent_result):
    if agent_result["error"] or not agent_result["safe_to_display"]:
        st.error("Medicine not found. Try a different spelling.")
        return

    if agent_result["query"].lower() != agent_result["medicine_name"].lower():
        st.info(
            f"Showing results for: {agent_result['medicine_name']} "
            f"(match score: {agent_result['match_score']:.0f}/100)"
        )

    for severity in ("High", "Medium", "Low"):
        render_interaction_group(agent_result, severity)

    render_safety_summary(agent_result)


user_id = st.sidebar.text_input("User ID", value="demo_user")
user_id = user_id.strip() or "demo_user"
render_sidebar(user_id)

if "pending_match" not in st.session_state:
    st.session_state.pending_match = None

if "confirmed_match" not in st.session_state:
    st.session_state.confirmed_match = None


st.markdown("## 🧠 MedGuard ")
st.caption("Detect risky food interactions for your medicines in seconds")

duplicate_pairs = DATASET_VALIDATION["duplicate_pairs"]
if duplicate_pairs:
    st.warning(
        "Dataset validation detected duplicate Medicine + Food pairs. Results are "
        "still available, but the dataset should be reviewed."
    )

medicine = st.text_input("Enter Medicine Name")
st.caption("Examples: Paracetamol, Doxycycline, Metformin (try even with typos)")

if st.button("Check"):

    if medicine.strip() == "":
        st.warning("Please enter a medicine name")

    else:
        with st.spinner("Analyzing interactions..."):
            agent_result = orchestrator.run(medicine)

        log_interaction(
            user_id=user_id,
            query=medicine,
            medicine_name=agent_result["medicine_name"],
            risk_level=agent_result["risk_level"],
            confidence_score=agent_result["confidence_score"],
        )

        if not agent_result["error"] and agent_result["interactions"]:
            if agent_result["needs_confirmation"]:
                st.session_state.pending_match = agent_result
                st.session_state.confirmed_match = None
            else:
                st.session_state.pending_match = None
                st.session_state.confirmed_match = agent_result

        else:
            st.session_state.pending_match = None
            st.session_state.confirmed_match = None
            if agent_result["match_score"] >= 50:
                st.warning(
                    f"Did you mean: {agent_result['suggested_name']}? "
                    f"(match score: {agent_result['match_score']:.0f}/100)"
                )
            st.error("Medicine not found. Try a different spelling.")

if st.session_state.pending_match is not None:
    pending = st.session_state.pending_match
    st.warning(
        f"Possible match: {pending['medicine_name']} "
        f"(match score: {pending['match_score']:.0f}/100)."
    )
    st.caption("Please confirm this is the medicine you meant before viewing results.")

    if st.button("Confirm match"):
        st.session_state.confirmed_match = pending
        st.session_state.pending_match = None

if st.session_state.confirmed_match is not None:
    confirmed = st.session_state.confirmed_match
    render_results(confirmed)

    if st.button("Save to profile"):
        add_medicine(user_id, confirmed["medicine_name"])
        st.success(f"Saved {confirmed['medicine_name']} to your medicine profile.")


st.markdown("---")
st.info(
    "⚠️ This tool is for awareness only and is not a substitute for professional "
    "medical advice. Do not stop or change medication without consulting a doctor "
    "or pharmacist."
)
st.caption(
    "Dataset currently covers ~100 common medicines. Results may not include all "
    "possible interactions."
)
