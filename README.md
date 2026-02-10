# 🧠 MedGuard AI

MedGuard AI is a decision-support system that detects risky food–medicine interactions and provides clear, actionable recommendations.

Most people take medicines without realizing that everyday habits (like food or drinks) can reduce effectiveness or cause harm.  
This system is designed to surface those hidden risks in a simple and usable way.

---

## 🚨 The Problem

Medicine instructions often miss real-world context.

People unknowingly:
- reduce drug effectiveness  
- increase side effects  
- or create harmful interactions  

---

## 💡 What This System Does

MedGuard AI:
- Identifies food–medicine interactions  
- Classifies their severity (High / Medium / Low)  
- Explains why the interaction matters  
- Suggests what the user should do  

---

## ⚙️ Key Features

- 🔍 Fuzzy search (handles typos like *paracitamol*)
- ⚠️ Risk-based grouping (High / Medium / Low)
- 🧠 Structured interaction insights (not raw data)
- 💡 Actionable recommendations
- 📊 Custom dataset covering 100+ medicines

---

## 🧠 How It Works

1. User enters a medicine name  
2. System uses fuzzy matching to find the closest match  
3. Retrieves all known food interactions  
4. Groups them by severity  
5. Displays clear explanations and recommended actions  

---

## 📊 Dataset

The dataset is manually structured from real-world medical sources and designed for decision-making, not just analysis.

---

## 🛠️ Tech Stack

- Python  
- Pandas  
- Streamlit  
- RapidFuzz  

---

## 🎯 Project Goal

To move beyond basic data analysis and build systems that help people make better real-world decisions.

---

## 🚀 Future Improvements

- User habit-based risk scoring  
- Personalized recommendations  
- Expanded dataset coverage  
- API integration for dynamic updates  

---

## ⚠️ Disclaimer

This tool is for awareness only and not a substitute for professional medical advice.

## 🖥️ App Preview

### Home Screen
![Home](assets/Home-UI.png)

### Example Result
![Result](assets/Working.png)

## 🚀 Live Demo
[Try MedGuard AI](https://medguard29.streamlit.app)
