from agents.intake_agent import IntakeAgent
from agents.interaction_agent import InteractionAgent
from agents.recommendation_agent import RecommendationAgent
from agents.risk_agent import RiskAgent
from agents.safety_guard_agent import SafetyGuardAgent


class MedGuardOrchestrator:
    def __init__(self):
        self.intake_agent = IntakeAgent()
        self.interaction_agent = InteractionAgent()
        self.risk_agent = RiskAgent()
        self.recommendation_agent = RecommendationAgent()
        self.safety_guard_agent = SafetyGuardAgent()

    def run(self, query):
        trajectory = []

        trajectory.append("intake_agent")
        intake = self.intake_agent.run(query)

        trajectory.append("interaction_agent")
        interactions = self.interaction_agent.run(intake)

        trajectory.append("risk_agent")
        risk = self.risk_agent.run(intake, interactions)

        trajectory.append("recommendation_agent")
        recommendation = self.recommendation_agent.run(interactions, risk)

        trajectory.append("safety_guard_agent")
        safety = self.safety_guard_agent.run(intake, risk, recommendation)

        return {
            "query": query.strip(),
            "medicine_name": intake.get("matched_name"),
            "suggested_name": intake.get("suggested_name"),
            "match_score": intake.get("match_score", 0),
            "needs_confirmation": intake.get("needs_confirmation", False),
            "error": intake.get("error") or interactions.get("error"),
            "interactions": interactions.get("interactions", []),
            "interactions_by_severity": interactions.get("interactions_by_severity", {}),
            "risk_level": risk["risk_level"],
            "confidence_score": risk["confidence_score"],
            "recommendation": safety["final_recommendation"],
            "safe_to_display": safety["safe_to_display"],
            "modifications_made": safety["modifications_made"],
            "trajectory": trajectory,
        }
