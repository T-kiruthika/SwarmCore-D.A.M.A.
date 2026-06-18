import json

class DiscoveryAgent:
    def __init__(self, brain=None):
        self.brain = brain

    # Phase 0: Policy Context Compression and Threshold Extraction
    def shrink_policy(self, raw_pdf_text, domain):
        prompt = f"""
        ACT AS: Senior Compliance Architect.
        DOMAIN: {domain}
        
        --- RAW PDF POLICY TEXT ---
        {raw_pdf_text}
        --- END RAW PDF POLICY ---
        
        MISSION: 
        Read the massive policy above.
        Extract ONLY the exact mathematical rules, thresholds, and success metrics required to evaluate an entity's status.
        Ignore all introductions, legal jargon, and formatting noise.
        
        CRITICAL RULE 1: Output ONLY valid JSON. No markdown blocks.
        CRITICAL RULE 2: You MUST extract the EXACT numerical thresholds (e.g., 65%, $5000). Do NOT summarize, invent, or round numbers.
        CRITICAL RULE 3: VERBATIM TEMPLATE EXTRACTION. If the policy text provides notification/alert templates, you MUST copy them WORD-FOR-WORD.
        Do NOT summarize them. Preserve every single bracketed {{Variable}} and <b> HTML tag exactly as they appear in the raw text.
        
        EXPECTED OUTPUT FORMAT (STRICT JSON ONLY):
        {{
            "success_metric": "Extract the exact string that means success (e.g., 'Approved', 'Cleared', 'P')",
            "penalty_metrics": ["List strings that mean failure/absence (e.g., 'Rejected', 'Default', 'A')"],
            "thresholds": [
                {{"status": "Tier_1_Status", "condition": ">= X"}},
                {{"status": "Tier_2_Status", "condition": "< Y"}}
            ],
            "telegram_templates": ["Extract EXACT, WORD-FOR-WORD template strings here. Do not summarize!"],
            "special_rules": "Brief 1-sentence summary of any edge cases."
        }}
        """
        if self.brain:
            response, provider = self.brain.think(prompt, agent_role="reader") 
            try:
                clean_json = response.replace("```json", "").replace("```", "").strip()
                return json.dumps(json.loads(clean_json), indent=2) 
            except:
                return "POLICY CONTEXT: Fallback active. Read strict threshold rules."
        return "POLICY CONTEXT: No rules found."

    # Phase 1: Schema Metadata and Attention Routing
    def generate_scout_prompt(self, schema_headers, policy, domain):
        policy_context = f"POLICY CONTEXT:\n{policy}\n" if policy else "POLICY CONTEXT: None."
        
        return f"""
        ACT AS: Senior Data Architect (Schema Scout)
        DOMAIN: {domain}
        
        --- AVAILABLE DATA COLUMNS ---
        {schema_headers}
        --- END AVAILABLE COLUMNS ---
        
        --- POLICY CONTEXT ---
        {policy_context}
        --- END POLICY CONTEXT ---
        
        MISSION: 
        You are the first pass of an Agentic Filter.
        Identify ONLY the columns required to evaluate this policy.
        
        CRITICAL EDGE-CASE DIRECTIVE:
        1. Identify the exact summary/status column names for EVERY sheet.
        2. FILTER GHOST SHEETS: You MUST completely ignore sheets that represent future periods or are entirely blank.
        
        DEMOGRAPHIC PRESERVATION RULE:
        You MUST extract organizational identifiers (e.g., Names, Departments, Cohorts, Roles).
        DO NOT drop the organizational grouping column.
        
        CRITICAL ANTI-FATIGUE RULE:
        DO NOT type out individual date or dynamic series columns.
        You MUST use the exact string "ALL_TIME_SERIES" in your focused_columns list.
        
        EXPECTED OUTPUT FORMAT (STRICT JSON ONLY):
        {{
            "thought_process": "Skipping future ghost sheets. Preserving organizational IDs. Identifying summary columns...",
            "focused_columns": ["Primary_Key_Col", "Organizational_Grouping_Col", "Intermediate_Summary_Col", "Intermediate_Percentage_Col", "Master_Percentage_Col", "Status_Col", "ALL_TIME_SERIES"]
        }}
        """

    # Phase 2: Macro-Update Execution and Verification
    def generate_coder_prompt(self, funneled_payload, domain, policy=None):
        policy_context = f"POLICY CONTEXT:\n{policy}\n" if policy else "POLICY CONTEXT: None explicitly provided."
        
        return f"""
        ACT AS: Senior Data Architect (MACRO-UPDATE MODE).
        DOMAIN: {domain}
        
        --- GHOST DATA PAYLOAD ---
        {funneled_payload}
        --- POLICY CONTEXT ---
        {policy_context}
        
        MISSION: Trigger the MACRO_RECALCULATE_ALL operation for all Excel sheets.
        
        CRITICAL RULES:
        1. THE STRICT SEMANTIC FILTER: Identify the strictly POSITIVE success metric (e.g., "P", "Approved") for `target_values`.
        2. MACRO-DELEGATION: If the domain requires summing daily time-series data (like Attendance), use "MACRO_RECALCULATE_ALL". 
        3. SKIP MATH IF STATIC: If the domain (like Finance) relies on static numbers (e.g., Credit Score) and requires no recalculation, you MUST leave the `excel_updates` array completely empty [].
        4. NO DATABASE UPDATES: `db_updates` MUST be empty [].

        EXPECTED OUTPUT FORMAT (STRICT JSON ONLY):
        {{
            "thought_process": "Triggering Macro-Update or Skipping based on domain...",
            "excluded_penalties": ["Penalty_1"],
            "excel_updates": [
                {{
                    "sheet": "ALL_SHEETS",
                    "match_column": "ALL_ROWS",
                    "match_value": "ALL_ROWS",
                    "update_column": "MACRO_UPDATE",
                    "new_value": "MACRO_UPDATE",
                    "compute_logic": {{
                        "operation": "MACRO_RECALCULATE_ALL",
                        "target_values": ["STRICTLY_POSITIVE_STRING_ONLY"]
                    }}
                }}
            ],
            "db_updates": []
        }}
        """

    # Phase 3: Policy Evaluation and Alert Generation
    def generate_auditor_prompt(self, fresh_schema_sample, policy, domain):
        return f"""
        ACT AS: Strict Compliance Auditor.
        DOMAIN: {domain}
        NEW DATA STATE: {fresh_schema_sample}
        POLICY RULES: {policy}
        
        MISSION: Audit the Master/Summary rows and assign final policy statuses and alerts.
        
        CRITICAL RULES:
        1. MASTER SHEET ONLY: You MUST ONLY generate `excel_updates` for the final Master/Summary sheet (e.g., "Semester_Summary"). NEVER update intermediate monthly or daily sheets.
        2. EXHAUSTIVE UPDATES (NO ORPHANS): You MUST generate an `excel_updates` object for EVERY SINGLE ENTITY in the dataset. If a user is fully compliant, you MUST explicitly assign them the policy's positive success status (e.g., "Category I (Safe)", "Compliant"). Do not skip compliant users. You are forbidden from leaving anyone as "Pending Audit".
        3. STRICT COLUMN TARGETING: You MUST ONLY update the dedicated text status column (e.g., "Academic_Standing", "Status"). You are STRICTLY FORBIDDEN from overwriting numerical columns (like percentages, totals, or counts) with text statuses.
        4. ALERTS ARE MANDATORY: If an entity violates a policy (e.g., Detained, Defaulted, At-Risk), you MUST write a separate alert object for them in the `alerts` array. DO NOT generate alerts for compliant/safe users.
        5. EXACT TEMPLATES: You MUST map real data into the exact `telegram_templates` provided in the POLICY RULES.
        6. DYNAMIC NOTIFICATION CATEGORY: Assign a dynamic category based on the context (e.g., "policy_alert", "financial_warning", "academic_violation"). Do NOT use hardcoded words unless specified by the policy.
        7. ROOT STATUS: If violations exist, set the root "status" to "violation". If the dataset is perfectly compliant, set "status" to "completed".
        8. ANTI-HALLUCINATION RULE: The "new_value" MUST NEVER be the same as the "update_column" name. It MUST be the exact policy string (e.g., "OK" or "CRITICAL - SLA Breach").
        9. EXHAUSTIVE OUTPUT MANDATE: ... explicitly output {{"new_value": "OK"}}. Do not leave any row behind.

        EXPECTED OUTPUT FORMAT (STRICT JSON ONLY):
        {{
            "thought_process": "Found violators on the Master sheet. Updating ONLY the status column and generating alerts...",
            "status": "violation",
            "excel_updates": [
                {{
                    "sheet": "MASTER_SUMMARY_SHEET_NAME_ONLY",
                    "match_column": "PRIMARY_KEY_COLUMN",
                    "match_value": "SPECIFIC_ID",
                    "update_column": "EXACT_STATUS_COLUMN_NAME_ONLY",
                    "new_value": "Exact Policy Status String"
                }}
            ],
            "alerts": [
                {{
                    "notification_category": "policy_alert",
                    "target_entity_id": "SPECIFIC_INDIVIDUAL_ID_ONLY",
                    "cooldown_days": 30,
                    "message": "EXACT TEMPLATE FROM POLICY RULES FILLED WITH REAL DATA"
                }}
            ]
        }}
        """