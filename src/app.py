import streamlit as st
from risk_model import get_medicine_info
result = None

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
            result = result.copy()

            severity_order = {"High": 3, "Medium": 2, "Low": 1}
            result["Severity Score"] = result["Severity"].map(severity_order)

            # Split into groups
            high_risk = result[result["Severity"] == "High"]
            medium_risk = result[result["Severity"] == "Medium"]
            low_risk = result[result["Severity"] == "Low"]

            # 🔴 HIGH RISK
            if not high_risk.empty:
                st.error("🔴 High Risk Interactions")
                for _, row in high_risk.iterrows():
                    st.markdown(f"**{row['Medicine']} + {row['Food']}**")
                    st.write(f"Why: {row['Effect']}")
                    st.write(f"Fix: {row['Recommendation']}")
                    st.markdown("---")

            # 🟡 MEDIUM RISK
            if not medium_risk.empty:
                st.warning("🟡 Medium Risk Interactions")
                for _, row in medium_risk.iterrows():
                    st.markdown(f"**{row['Medicine']} + {row['Food']}**")
                    st.write(f"Why: {row['Effect']}")
                    st.write(f"Fix: {row['Recommendation']}")
                    st.markdown("---")

            # 🟢 LOW RISK
            if not low_risk.empty:
                st.success("🟢 Low Risk Interactions")
                for _, row in low_risk.iterrows():
                    st.markdown(f"**{row['Medicine']} + {row['Food']}**")
                    st.write(f"Why: {row['Effect']}")
                    st.write(f"Fix: {row['Recommendation']}")
                    st.markdown("---")

            if result is not None and not result.empty:
                if any(result["Severity"] == "High"):
                    st.error("🚨 Critical interactions detected. Adjust habits immediately.")
                elif any(result["Severity"] == "Medium"):
                    st.warning("⚠️ Some interactions may affect effectiveness.")
                else:
                    st.success("✅ No major risks detected.")

        else:
            if result is None and score >= 50:
                st.warning(f"Did you mean: {matched_name}?")
            st.error("Medicine not found. Try a different spelling.")



st.markdown("---")
st.info("⚠️ This tool is for awareness only and not a substitute for professional medical advice.")
st.caption("Dataset currently covers ~100 common medicines. Results may not include all possible interactions.")
