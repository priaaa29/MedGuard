import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from agents.orchestrator import MedGuardOrchestrator
from memory.memory_bank import (
    add_medicine,
    check_cross_interactions,
    get_history,
    get_profile_stats,
    get_user_medicines,
    log_interaction,
)
from risk_model import DATASET_VALIDATION
from tools.audit_logger import get_recent_audit_entries
from tools.ocr_tool import extract_medicine_from_image


SEVERITY_DISPLAY = {
    "High": {"title": "High Risk Interactions", "icon": "🔴", "renderer": st.error},
    "Medium": {"title": "Medium Risk Interactions", "icon": "🟡", "renderer": st.warning},
    "Low": {"title": "Low Risk Interactions", "icon": "🟢", "renderer": st.success},
}
DEMO_MEDICINES = ["Warfarin", "Ibuprofen", "Paracetamol", "Metformin", "Simvastatin"]


st.set_page_config(page_title="MedGuard AI", layout="wide")
orchestrator = MedGuardOrchestrator()


def init_session_state():
    defaults = {
        "pending_match": None,
        "confirmed_match": None,
        "last_agent_result": None,
        "query_input": "",
        "ocr_text": "",
        "processed_upload_id": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def format_bytes(size):
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def risk_badge(risk_level):
    colors = {
        "High": "#b42318",
        "Medium": "#b54708",
        "Low": "#027a48",
        "Not Found": "#475467",
    }
    color = colors.get(risk_level, "#475467")
    st.markdown(
        f"""
        <span style="
            display:inline-block;
            padding:0.25rem 0.6rem;
            border-radius:999px;
            background:{color};
            color:white;
            font-weight:700;
            font-size:0.85rem;">
            {risk_level}
        </span>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar(user_id):
    stats = get_profile_stats(user_id)
    medicines = get_user_medicines(user_id)
    history = get_history(user_id, limit=5)

    st.sidebar.header("User")
    st.sidebar.caption("Local profile only. No authentication is applied.")
    st.sidebar.metric("Tracked medicines", stats["medicine_count"])
    st.sidebar.metric("Queries", stats["query_count"])
    st.sidebar.metric("High-risk queries", stats["high_risk_count"])
    st.sidebar.metric("Memory size", format_bytes(stats["memory_size_bytes"]))

    st.sidebar.markdown("### Tracked Medicines")
    if medicines:
        for medicine in medicines:
            st.sidebar.write(f"• {medicine['medicine_name']}")
    else:
        st.sidebar.caption("No saved medicines yet.")

    st.sidebar.markdown("### Recent Searches")
    if history:
        for item in history:
            st.sidebar.caption(
                f"{item['query']} → {item['medicine_name'] or 'Not found'} "
                f"({item['risk_level']}, {item['confidence_score']}/100)"
            )
    else:
        st.sidebar.caption("No recent searches yet.")

    st.sidebar.markdown("### Database Status")
    st.sidebar.success("SQLite memory ready")


def process_query(query, user_id):
    if not query.strip():
        st.warning("Please enter a medicine name")
        return

    with st.spinner("Analyzing interactions..."):
        agent_result = orchestrator.run(query, user_id=user_id)

    log_interaction(
        user_id=user_id,
        query=query,
        medicine_name=agent_result["medicine_name"],
        risk_level=agent_result["risk_level"],
        confidence_score=agent_result["confidence_score"],
    )

    st.session_state.last_agent_result = agent_result
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


def render_interaction_group(agent_result, severity):
    group = agent_result["interactions_by_severity"].get(severity, [])
    if not group:
        return

    display = SEVERITY_DISPLAY[severity]
    with st.expander(f"{display['icon']} {display['title']}", expanded=severity == "High"):
        for row in group:
            st.markdown(f"**{row['Medicine']} + {row['Food']}**")
            st.write(f"Why: {row['Effect']}")
            st.write(f"Fix: {row['Recommendation']}")
            st.divider()


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
            "High-risk interactions detected. Contact a doctor or pharmacist before "
            "changing habits or medication. Seek emergency help immediately for severe "
            "symptoms such as trouble breathing, fainting, chest pain, severe bleeding, "
            "or confusion."
        )
    elif agent_result["risk_level"] == "Medium":
        st.warning(
            "Some interactions may affect effectiveness or side effects. Ask a doctor "
            "or pharmacist for guidance."
        )
    else:
        st.success(
            "No major risks detected in this dataset. Check with a healthcare "
            "professional if you are unsure."
        )


def render_results(agent_result):
    if agent_result["error"] or not agent_result["safe_to_display"]:
        st.error("Medicine not found. Try a different spelling.")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Resolved medicine", agent_result["medicine_name"])
    col2.metric("Confidence", f"{agent_result['confidence_score']}/100")
    col3.metric("Known interactions", len(agent_result["interactions"]))
    st.progress(agent_result["confidence_score"] / 100)
    risk_badge(agent_result["risk_level"])

    if agent_result["query"].lower() != agent_result["medicine_name"].lower():
        st.info(
            f"Showing results for: {agent_result['medicine_name']} "
            f"(match score: {agent_result['match_score']:.0f}/100)"
        )

    for severity in ("High", "Medium", "Low"):
        render_interaction_group(agent_result, severity)

    render_safety_summary(agent_result)


def render_profile_tab(user_id):
    medicines = get_user_medicines(user_id)
    stats = get_profile_stats(user_id)

    col1, col2, col3 = st.columns(3)
    col1.metric("Tracked medicines", stats["medicine_count"])
    col2.metric("Total queries", stats["query_count"])
    col3.metric("High-risk queries", stats["high_risk_count"])

    st.subheader("Medicine Profile")
    if medicines:
        for medicine in medicines:
            st.write(f"• {medicine['medicine_name']}")
    else:
        st.caption("Save a medicine from the interaction checker to build a profile.")

    if st.button("Check cross-interactions"):
        conflicts = check_cross_interactions(user_id)
        if conflicts:
            st.warning("Possible interaction overlap found.")
            for conflict in conflicts:
                st.markdown(
                    f"- **{conflict['medicine']}** and "
                    f"**{conflict['other_medicine']}** both have guidance for "
                    f"**{conflict['shared_food']}**."
                )
                st.caption(conflict["explanation"])
        else:
            st.success("No known conflicts found.")


def render_agent_activity():
    result = st.session_state.last_agent_result
    st.subheader("Agent Execution Order")
    trace = result["trajectory"] if result else []
    if trace:
        labels = ["User Input"] + [item.replace("_", " ").title() for item in trace]
        st.markdown("\n\n↓\n\n".join(labels))
    else:
        st.caption("Run a query to see agent activity.")

    if result:
        col1, col2, col3 = st.columns(3)
        col1.metric("Confidence", f"{result['confidence_score']}/100")
        col2.metric("Final risk", result["risk_level"])
        col3.metric("Safety actions", len(result["modifications_made"]))
        if result["modifications_made"]:
            st.write(", ".join(result["modifications_made"]))
        else:
            st.caption("No safety modifications were needed.")

    st.subheader("Latest Audit Logs")
    entries = get_recent_audit_entries(limit=5)
    if not entries:
        st.caption("No audit log entries yet.")
        return

    for entry in entries:
        with st.expander(f"{entry['timestamp']} - {entry['query']}"):
            st.json(entry)


init_session_state()

user_id = st.sidebar.text_input("User ID", value="demo_user")
user_id = user_id.strip() or "demo_user"
render_sidebar(user_id)

st.markdown("## 🧠 MedGuard")
st.caption("Detect risky food interactions for your medicines in seconds")

duplicate_pairs = DATASET_VALIDATION["duplicate_pairs"]
if duplicate_pairs:
    st.warning(
        "Dataset validation detected duplicate Medicine + Food pairs. Results are "
        "still available, but the dataset should be reviewed."
    )

check_tab, profile_tab, activity_tab = st.tabs(
    ["Check Interactions", "My Profile", "Agent Activity"]
)

with check_tab:
    demo_mode = st.toggle("Demo Mode")
    if demo_mode:
        st.caption("One-click examples")
        demo_columns = st.columns(len(DEMO_MEDICINES))
        for index, example in enumerate(DEMO_MEDICINES):
            if demo_columns[index].button(example):
                st.session_state.query_input = example
                process_query(example, user_id)

    medicine = st.text_input("Enter Medicine Name", key="query_input")
    st.caption("Examples: Paracetamol, Doxycycline, Metformin (try even with typos)")

    uploaded_image = st.file_uploader(
        "Or upload prescription image", type=["jpg", "jpeg", "png"]
    )
    # Streamlit keeps the upload across reruns, so only run OCR once per file;
    # otherwise every button click re-runs OCR and logs a duplicate query.
    if (
        uploaded_image is not None
        and uploaded_image.file_id != st.session_state.processed_upload_id
    ):
        st.session_state.processed_upload_id = uploaded_image.file_id
        suffix = Path(uploaded_image.name).suffix or ".png"
        with NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(uploaded_image.getbuffer())
            temp_path = Path(temp_file.name)

        ocr_result = extract_medicine_from_image(temp_path)
        temp_path.unlink(missing_ok=True)
        st.session_state.ocr_text = ocr_result.get("text", "")

        if ocr_result["medicine_name"]:
            st.success(f"OCR detected: {ocr_result['medicine_name']}")
            process_query(ocr_result["medicine_name"], user_id)
        else:
            st.warning(ocr_result["error"])

    if st.button("Check"):
        process_query(st.session_state.query_input, user_id)

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

with profile_tab:
    render_profile_tab(user_id)

with activity_tab:
    render_agent_activity()

st.markdown("---")
st.info(
    "MedGuard is for awareness only and is not a substitute for professional medical "
    "advice. Do not stop or change medication without consulting a doctor or pharmacist."
)
st.caption(
    "Dataset currently covers ~100 common medicines. Results may not include all "
    "possible interactions."
)
