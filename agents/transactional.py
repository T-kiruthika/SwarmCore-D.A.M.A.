import json
import re
from datetime import datetime

class TransactionalAgent:
    """
    FLOW 3: The Transactional Micro-Agent Pipeline.
    100% Domain-Agnostic. Adapts to EDU, FIN, HR, etc.
    """
    def __init__(self, brain=None):
        self.brain = brain

    def parse_unstructured_request(self, user_message, domain):
        forced_id = None
        match = re.search(r"TARGET_ENTITY_ID\s*=\s*([a-zA-Z0-9_]+)", user_message)
        if match: forced_id = match.group(1).strip()

        is_bot_chat = "source: 'bot_chat'" in str(user_message).lower() or "[SOURCE: BOT_CHAT]" in str(user_message).upper()

        prompt = f"""
        ACT AS: Ingestion Gatekeeper.
        DOMAIN: {domain}
        INCOMING PAYLOAD: "{user_message}"
        
        EXPECTED OUTPUT FORMAT (STRICT JSON ONLY):
        {{
            "intent_type": "NEW_REQUEST" | "INQUIRY",
            "is_complete": true_or_false,
            "missing_info_message": "...",
            "extracted_data": {{
                "target_entity_id": "EXTRACT_ID_IF_FOUND",
                "entity_name": "Extract name, else 'Unknown'",
                "domain_group": "{domain}",
                "target_keys": ["Extract requested dates, months, or target items"],
                "reason_or_context": "Extract the EXACT raw reason word-for-word. DO NOT summarize.",
                "classification_tier": "Extract any mentioned Tier, Category, or Level (e.g., 'Tier 2', 'Category III'). If none, output 'Not specified'.",
                "document_provided": true_or_false
            }}
        }}
        """
        if self.brain:
            response, _ = self.brain.think(prompt, agent_role="concierge")
            try:
                parsed = json.loads(response.replace("```json", "").replace("```", "").strip())
                if forced_id:
                    if "extracted_data" not in parsed: parsed["extracted_data"] = {}
                    parsed["extracted_data"]["target_entity_id"] = forced_id
                    parsed["is_complete"] = True 
                if is_bot_chat:
                    parsed["intent_type"] = "INQUIRY"
                    parsed["is_complete"] = True
                return parsed
            except: pass
        return {"is_complete": False, "missing_info_message": "System error."}

    def evaluate_transaction(self, request_data, excel_row_data, policy_text, domain):
        current_time = datetime.now()
        is_retroactive_python = False
        doc_provided = request_data.get("document_provided", False)
        
        target_keys = request_data.get('target_keys', request_data.get('dates_requested', []))
        if isinstance(target_keys, str): target_keys = [target_keys]
        
        for key in target_keys:
            try:
                clean_date = str(key).strip().replace("'", "").replace('"', '')
                parsed_date = None
                for fmt in ("%d-%b", "%d %B", "%d-%B", "%d %b", "%d %B %Y", "%d-%m-%Y"):
                    try:
                        parsed_date = datetime.strptime(clean_date, fmt)
                        if parsed_date.year == 1900: 
                            parsed_date = parsed_date.replace(year=current_time.year)
                        break
                    except ValueError: pass
                
                if parsed_date and parsed_date.date() < current_time.date():
                    is_retroactive_python = True
                    break
            except Exception: pass
        
        real_metric = "Unknown"
        try:
            if excel_row_data:
                nums = re.findall(r'\b\d+\.\d+\b|\b\d+\b', str(excel_row_data))
                if nums: real_metric = nums[-1]
        except: pass
        
        prompt = f"""
        ACT AS: Strict Policy Adjudicator.
        DOMAIN: {domain}
        
        [SYSTEM OVERRIDES & EXTRACTED FACTS]
        - RETROACTIVE/PAST DATE: {is_retroactive_python}
        - DOCUMENT PROVIDED: {doc_provided}
        - TARGET METRIC (EVALUATE THIS NUMBER): {real_metric}
        
        --- REQUEST DATA (USER INPUT) ---
        {json.dumps(request_data, indent=2)}
        
        --- LIVE DATA (EXCEL ROW) ---
        {excel_row_data}
        
        --- POLICY LOGIC GATES ---
        {policy_text}
        
        CRITICAL ADJUDICATION RULES (OBEY OR FAIL):
        1. THE MATH LOCK (CRITICAL): Explicitly compare the TARGET METRIC against the policy's numerical threshold. If the TARGET METRIC is mathematically less than the threshold (or is 'Unknown'/'N/A'), you MUST set "boolean_is_math_failing" to true. If true, you are FORBIDDEN from matching a 'Benign' gate and MUST trigger the violation consequence.
        2. Evaluate BOTH the [REQUEST DATA] and [LIVE DATA] against the [POLICY LOGIC GATES] IN ORDER from top to bottom.
        3. CLASSIFICATION MATCHING: Scan the [REQUEST DATA] to identify which specific classification, tier, or category it belongs to, based STRICTLY on the definitions in the policy.
        4. KEYWORD TRAPS: If a policy logic gate specifies restricted keywords, you MUST aggressively scan the 'reason' inside the [REQUEST DATA] for those exact words. If a restricted word is found, trigger that specific gate immediately.
        5. FIRST MATCH WINS: Stop at the very first logic gate condition that is completely true.
        6. You MUST extract the EXACT 'consequence' and 'database_patch_string' defined in the matched logic gate.
        7. IF RETROACTIVE/PAST DATE is True, YOU MUST output "boolean_is_past_date": true.
        
        EXPECTED JSON:
        {{
            "thought_process": "State: [TARGET METRIC] vs [Policy Threshold]. Does it fail the math?",
            "boolean_is_past_date": true_or_false,
            "boolean_is_math_failing": true_or_false,
            "decision": "<Extract the 'consequence' string exactly as written in the gate>",
            "database_patch_string": "<Extract the 'database_patch_string' exactly as written in the gate>",
            "extracted_context": {{"escalation_action": "<Exact Action>"}}
        }}
        """
        if self.brain:
            response, _ = self.brain.think(prompt, agent_role="auditor")
            try:
                parsed = json.loads(response.replace("```json", "").replace("```", "").strip())
                
                is_past = parsed.get("boolean_is_past_date", False)
                if is_retroactive_python: is_past = True 
                
                is_failing = parsed.get("boolean_is_math_failing", False)
                
                if is_past or is_failing:
                    if parsed.get("decision") == "Approved":
                        parsed["decision"] = "Pending Audit"
                        
                if "extracted_context" not in parsed: parsed["extracted_context"] = {}
                
                parsed["extracted_context"]["actual_metric"] = parsed["extracted_context"].get("actual_metric", real_metric)
                
                parsed["extracted_context"]["is_retroactive"] = is_past
                return parsed
            except: pass
        return {"decision": "Pending Audit", "extracted_context": {"actual_metric": real_metric, "is_retroactive": is_retroactive_python}}

    def generate_execution_plan(self, evaluation_result, request_data, policy_text, is_manual_override=False):
        decision_clean = evaluation_result.get('decision', 'Pending Audit').strip()
        target_id = request_data.get('target_entity_id', 'UNKNOWN')
        is_retro = evaluation_result.get('extracted_context', {}).get('is_retroactive', False)
        
        target_keys = request_data.get('target_keys', request_data.get('dates_requested', []))
        if isinstance(target_keys, list):
            keys_str = ", ".join(str(d).replace("'", "").replace('"', '').strip() for d in target_keys)
        else:
            keys_str = str(target_keys).replace('[', '').replace(']', '').replace("'", "").strip()
            
        entity_name = request_data.get('entity_name', request_data.get('student_name', 'User'))
        domain_group = request_data.get('domain_group', request_data.get('department', 'General'))
        request_reason = request_data.get('reason_or_context', request_data.get('reason', 'Not provided'))
        real_metric = evaluation_result.get('extracted_context', {}).get('actual_metric', 'Unknown')
        
        db_patch_string = evaluation_result.get('database_patch_string', 'null').strip()
        
        prompt = f"""
        ACT AS: Autonomous Transaction Executor.
        OFFICIAL DECISION: {decision_clean}
        REQUIRED DB PATCH: {db_patch_string}
        IS MANUAL OVERRIDE BY HUMAN: {is_manual_override}
        IS RETROACTIVE REQUEST: {is_retro}
        
        --- RAW CONTEXT ---
        Entity ID: {target_id}
        Name: {entity_name}
        Domain/Group: {domain_group}
        Target Keys/Dates: {keys_str}
        Metric/Score: {real_metric}
        Reason: {request_reason}
        
        --- PRISTINE RAW POLICY & TEMPLATES ---
        {policy_text}
        
        CRITICAL RULES (OBEY OR FAIL):
        1. THE EXCEL PATCH DIRECTIVE (USE "excel_micro_patches" KEY ONLY): 
           - IF [OFFICIAL DECISION] contains "PENDING", "TRIGGER", or "AUDIT": You MUST output an empty list: []. DO NOT PATCH EARLY.
           - IF [IS MANUAL OVERRIDE BY HUMAN] is True AND [OFFICIAL DECISION] is "Declined": Output an empty list: [].
           - IF [IS MANUAL OVERRIDE BY HUMAN] is True AND [OFFICIAL DECISION] is "Approved": IGNORE the [REQUIRED DB PATCH] variable. You MUST scan the [PRISTINE RAW POLICY] text for the Manager/CIO Override rule, extract the exact database patch string required by the policy text, and create a separate key-value pair for EVERY single date listed in [Target Keys/Dates] using that extracted string.
           - OTHERWISE: IF the [REQUIRED DB PATCH] contains a valid string (e.g., "OK"), you MUST create a separate key-value pair for EVERY single date listed in [Target Keys/Dates]. If "null", output [].
        2. TEMPLATE SELECTION: 
           - IF [OFFICIAL DECISION] contains "PENDING", "TRIGGER", or "AUDIT": DO NOT scan the policy for a template. Use EXACTLY this text: "<b>⏳ STATUS: PENDING MANAGER REVIEW</b>\\n<b>Entity ID:</b> {target_id}\\n<b>Dates:</b> {keys_str}\\n<b>Reason:</b> {request_reason}\\nAwaiting Executive Authorization."
           - IF [IS MANUAL OVERRIDE BY HUMAN] is True AND [OFFICIAL DECISION] is "Approved": Scan the [PRISTINE RAW POLICY] and use the explicit Manager/CIO Overrides template (e.g., [TEMPLATE: CIO_APPROVED] or [TEMPLATE 4: MANAGER APPROVED]).
           - IF [IS MANUAL OVERRIDE BY HUMAN] is True AND [OFFICIAL DECISION] is "Declined": Scan the [PRISTINE RAW POLICY] and use the explicit Manager/CIO Denials template (e.g., [TEMPLATE: CIO_DECLINED] or standard decline text).
           - OTHERWISE: Scan the [PRISTINE RAW POLICY] for the exact notification template matching the [OFFICIAL DECISION].
        3. EMOJI & HTML PRESERVATION: Copy the text of the chosen template into the "message" field. YOU MUST KEEP ALL EMOJIS (☑, ❌, 👑, ⚠️, ⏳) AND ALL HTML TAGS (<b>, <i>). ESCAPE NEWLINES AS \\n. DO NOT STRIP EMOJIS!
        4. VARIABLES MAP: Create a JSON dictionary mapping the EXACT bracket names found in the template to the raw context provided above.
        
        EXPECTED OUTPUT FORMAT (STRICT JSON ONLY):
        {{
            "db_updates": [ {{"table": "universal_requests", "target_entity_id": "{target_id}", "update_data": {{"status": "{decision_clean}"}} }} ],
            "excel_micro_patches": [ {{"target_entity_id": "{target_id}", "updates": {{"<DATE_HERE>": "<EXTRACTED_PATCH_STRING_HERE>"}} }} ], 
            "alerts": [ 
                {{
                    "target_entity_id": "{target_id}", 
                    "role": "Requester", 
                    "message": "Template text with emojis goes here...", 
                    "requires_hitl_buttons": false,
                    "template_variables": {{
                        "Bracket_Name": "Mapped Value"
                    }}
                }} 
            ]
        }}
        NOTE: "excel_micro_patches" MUST BE [] IF PENDING OR DECLINED.
        """
        if self.brain:
            response, _ = self.brain.think(prompt, agent_role="coder")
            try:
                clean_json = response.replace("```json", "").replace("```", "").strip()
                plan = json.loads(clean_json)
                
                for alert in plan.get('alerts', []):
                    decision_upper = decision_clean.upper()
                    needs_hitl = any(keyword in decision_upper for keyword in ["PENDING", "OVERRIDE", "MANAGER", "HALT", "AUDIT", "TRIGGER"])
                    
                    if is_manual_override:
                        alert['requires_hitl_buttons'] = False 
                    else:
                        alert['requires_hitl_buttons'] = needs_hitl
                        
                    msg = alert.get('message', '')
                    variables_map = alert.get('template_variables', {})
                    
                    for bracket_key, mapped_value in variables_map.items():
                        clean_key = bracket_key.replace('{', '').replace('}', '').strip()
                        pattern = r'\{[^}]*' + re.escape(clean_key) + r'[^}]*\}'
                        msg = re.sub(pattern, str(mapped_value), msg, flags=re.IGNORECASE)
                    
                    msg = re.sub(r'\{[^}]*(Name)[^}]*\}', str(entity_name), msg, flags=re.IGNORECASE)
                    msg = re.sub(r'\{[^}]*(ID)[^}]*\}', str(target_id), msg, flags=re.IGNORECASE)
                    msg = re.sub(r'\{[^}]*(Reason)[^}]*\}', str(request_reason), msg, flags=re.IGNORECASE)
                    msg = re.sub(r'\{[^}]*(Percentage|Score|Metric)[^}]*\}', str(real_metric), msg, flags=re.IGNORECASE)
                    
                    if str(target_id) not in msg and target_id != "UNKNOWN":
                        msg = f"<b>TRANSACTION STATUS: {decision_clean.upper()}</b>\n<b>ID:</b> {target_id}\n\n" + msg
                        
                    alert['message'] = msg
                return plan
            except Exception as e: 
                print(f"[Executor] AI JSON Parsing Failed. Reason: {e}\nRaw Response: {response}")
                pass
        return {"db_updates": [], "excel_micro_patches": [], "alerts": []}