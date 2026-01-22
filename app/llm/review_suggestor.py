import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

class LLMReviewSuggester:
    """
    Generates human-like code review suggestions
    using an LLM grounded on explainability outputs.
    """

    def __init__(self):
        self.client = Groq(
            api_key=os.getenv("GROQ_API_KEY")
        )
        self.model = "llama-3.1-8b-instant"

    def generate_suggestions(self, explanation: dict) -> str:
        
        if not explanation or not explanation.get("key_risk_factors"):
            return "No sufficient risk signals detected to generate review suggestions."

        prompt = self._build_prompt(explanation)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a senior software engineer performing a code review."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=300,
        )

        return response.choices[0].message.content


    def _build_prompt(self, explanation: dict) -> str:
        return f"""
Pull Request Risk Summary:
{explanation['summary']}

Key Risk Factors:
- {chr(10).join(explanation['key_risk_factors'])}

Code Complexity Insight:
{explanation['code_complexity_insight']}

Reviewer Focus Areas:
- {chr(10).join(explanation['review_focus_areas'])}

Task:
Based on the above information, generate concise and actionable
code review suggestions. Focus on maintainability, correctness,
and risk mitigation. Avoid speculation.
"""
