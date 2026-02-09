import streamlit as st
from risk_model import get_medicine_info

st.set_page_config(page_title="MedGuard AI", layout="centered")

st.markdown("## 🧠 MedGuard AI")
st.caption("Detect risky food interactions for your medicines in seconds")

medicine = st.text_input("Enter Medicine Name")
st.caption("Examples: Paracetamol, Doxycycline, Metformin (try even with typos)")

if st.button("Check"):
    if medicine.strip() == "":
        st.warning("Please enter a medicine name")
    else:
        with st.spinner("Analyzing interactions..."):
            result, matched_name, score = get_medicine_info(medicine)

        if result is not None and not result.empty:
            if medicine.lower() != matched_name.lower():
                st.info(f"Showing results for: {matched_name}")
            st.dataframe(result[["Food", "Severity", "Effect", "Recommendation"]])
        else:
            if result is None and score >= 50:
                st.warning(f"Did you mean: {matched_name}?")
            st.error("Medicine not found. Try a different spelling.")
