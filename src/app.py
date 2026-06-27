import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from memory.memory_bank import (
    add_medicine,
    get_history,
    get_user_medicines,
    log_interaction,
)
from risk_model import DATASET_VALIDATION, get_medicine_info


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


def get_risk_level(result):
    if result is None or result.empty:
        return "Not Found"
    if any(result["Severity"] == "High"):
        return "High"
    if any(result["Severity"] == "Medium"):
        return "Medium"
    return "Low"


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


def render_interaction_group(result, severity):
    group = result[result["Severity"] == severity]
    if group.empty:
        return

    display = SEVERITY_DISPLAY[severity]
    display["renderer"](display["title"])

    for _, row in group.iterrows():
        st.markdown(f"**{row['Medicine']} + {row['Food']}**")
        st.write(f"Why: {row['Effect']}")
        st.write(f"Fix: {row['Recommendation']}")
        st.markdown("---")


def render_safety_summary(result):
    st.info(
        "Do not stop, skip, or change any medication without speaking to a doctor "
        "or pharmacist."
    )

    if any(result["Severity"] == "High"):
        st.error(
            "🚨 High-risk interactions detected. Contact a doctor or pharmacist "
            "before changing habits or medication. Seek emergency help immediately "
            "for severe symptoms such as trouble breathing, fainting, chest pain, "
            "severe bleeding, or confusion."
        )
    elif any(result["Severity"] == "Medium"):
        st.warning(
            "⚠️ Some interactions may affect effectiveness or side effects. "
            "Ask a doctor or pharmacist for guidance."
        )
    else:
        st.success(
            "✅ No major risks detected in this dataset. Check with a healthcare "
            "professional if you are unsure."
        )


def render_results(medicine, matched_name, score):
    result, _, _ = get_medicine_info(matched_name)
    if result is None or result.empty:
        st.error("Medicine not found. Try a different spelling.")
        return

    if medicine.strip().lower() != matched_name.lower():
        st.info(f"Showing results for: {matched_name} (match score: {score:.0f}/100)")

    result = result.copy()
    severity_order = {"High": 3, "Medium": 2, "Low": 1}
    result["Severity Score"] = result["Severity"].map(severity_order)
    result = result.sort_values("Severity Score", ascending=False)

    for severity in ("High", "Medium", "Low"):
        render_interaction_group(result, severity)

    render_safety_summary(result)


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
            result, matched_name, score = get_medicine_info(medicine)

        risk_level = get_risk_level(result)
        log_interaction(
            user_id=user_id,
            query=medicine,
            medicine_name=matched_name if result is not None else None,
            risk_level=risk_level,
            confidence_score=score,
        )

        if result is not None and not result.empty:
            lookup = {
                "medicine": medicine.strip(),
                "matched_name": matched_name,
                "score": score,
            }

            if medicine.strip().lower() != matched_name.lower():
                st.session_state.pending_match = lookup
                st.session_state.confirmed_match = None
            else:
                st.session_state.pending_match = None
                st.session_state.confirmed_match = lookup

        else:
            st.session_state.pending_match = None
            st.session_state.confirmed_match = None
            if result is None and score >= 50:
                st.warning(
                    f"Did you mean: {matched_name}? (match score: {score:.0f}/100)"
                )
            st.error("Medicine not found. Try a different spelling.")

if st.session_state.pending_match is not None:
    pending = st.session_state.pending_match
    st.warning(
        f"Possible match: {pending['matched_name']} "
        f"(match score: {pending['score']:.0f}/100)."
    )
    st.caption("Please confirm this is the medicine you meant before viewing results.")

    if st.button("Confirm match"):
        st.session_state.confirmed_match = pending
        st.session_state.pending_match = None

if st.session_state.confirmed_match is not None:
    confirmed = st.session_state.confirmed_match
    render_results(
        confirmed["medicine"],
        confirmed["matched_name"],
        confirmed["score"],
    )

    if st.button("Save to profile"):
        add_medicine(user_id, confirmed["matched_name"])
        st.success(f"Saved {confirmed['matched_name']} to your medicine profile.")


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
