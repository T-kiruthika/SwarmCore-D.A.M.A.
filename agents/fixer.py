import re
import os

class FixerAgent:
    def __init__(self, brain=None):
        self.brain = brain
        self.max_retries = 3

    def generate_repair_code(self, profile, schema_context, error_feedback):
        """Domain-Agnostic Cognitive Repair for JSON Formatters."""
        prompt = f"""
        ACT AS: Senior JSON Architect & Error Recovery Specialist.
        ERROR FEEDBACK: {error_feedback}
        FUNNELED SCHEMA: {schema_context}
        
        MISSION:
        The previous JSON patch failed to apply to the legacy system. 
        Analyze the error and generate a REPAIRED JSON Diff Patch.
        
        CRITICAL RULES:
        1. NO PYTHON: Do not write execution scripts.
        2. STRICT JSON: You MUST use double quotes for keys (e.g., "sheet" not 'sheet').
        3. EXACT MATCHING: Ensure `match_column` exactly matches the schema.
        
        EXPECTED OUTPUT FORMAT:
        ```json
        {{
            "excel_updates": [
                {{
                    "sheet": "Sheet_Name",
                    "match_column": "Col_Name",
                    "match_value": "Value",
                    "update_column": "Col_Name",
                    "new_value": 100
                }}
            ]
        }}
        ```
        """
        if self.brain:
            response, provider = self.brain.think(prompt, agent_role="fixer")
            return response, provider
        return None, "Offline"