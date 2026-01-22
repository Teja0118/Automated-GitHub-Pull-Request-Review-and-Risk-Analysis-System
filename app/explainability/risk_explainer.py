from typing import Dict, List


class RiskExplainer:
    # Generates human-readable explanations for PR risk using ML features, predictions, and AST metrics.

    def generate_explanation(
        self,
        predicted_risk: str,
        features: Dict,
        ast_metrics: Dict,
    ) -> Dict:

        key_factors: List[str] = []
        review_focus: List[str] = []

        # Feature-based reasoning 
        if features.get("code_churn", 0) > 500:
            key_factors.append("High code churn")
            review_focus.append("Review large code changes carefully")

        if features.get("change_request_count", 0) > 0:
            key_factors.append("Multiple change requests from reviewers")
            review_focus.append("Address reviewer feedback thoroughly")

        if features.get("review_count", 0) == 0:
            key_factors.append("Lack of peer review")
            review_focus.append("Ensure adequate code review before merging")

        if features.get("time_to_merge_hours", 0) and features["time_to_merge_hours"] > 48:
            key_factors.append("Long time to merge")
            review_focus.append("Check for unresolved design or logic issues")

        # AST-based reasoning 
        if ast_metrics.get("complexity_flag") == "HIGH":
            key_factors.append("High code complexity detected via AST analysis")
            review_focus.append("Refactor deeply nested or complex logic")

        elif ast_metrics.get("complexity_flag") == "MEDIUM":
            key_factors.append("Moderate code complexity")
            review_focus.append("Review function boundaries and branching logic")

        # Construct explanation text 
        summary = f"This pull request is classified as {predicted_risk} risk."

        complexity_insight = (
            f"The modified Python files contain "
            f"{ast_metrics.get('total_functions', 0)} functions, "
            f"{ast_metrics.get('total_classes', 0)} classes, and "
            f"a maximum nesting depth of {ast_metrics.get('max_nesting_depth', 0)}."
        )

        return {
            "summary": summary,
            "key_risk_factors": key_factors,
            "code_complexity_insight": complexity_insight,
            "review_focus_areas": list(set(review_focus)),
        }
