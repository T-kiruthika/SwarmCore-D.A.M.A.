import os
import time
import json  
import requests
import hashlib
import glob  
import re 
import logging
import sqlite3
from dotenv import load_dotenv

from core.brain import ResilientBrain
from core.bridge import LegacyBridge
from core.logger import BlackboardLogger
from core.reader import PolicyReader
from agents.discovery import DiscoveryAgent
from agents.actor import SandboxActuator
from agents.fixer import FixerAgent
from agents.transactional import TransactionalAgent 

load_dotenv()

class SharedBlackboard:
    def __init__(self):
        self.state = {
            "current_event": "idle",
            "event_type": "USER_REQUEST", 
            "user_goal": None,
            "target_file": None,
            "domain": "General",
            "required_columns": ["ALL"], 
            "focused_columns": ["ALL"], 
            "schema_context": None,
            "json_patch": None,          
            "execution_logs": [],
            "error_trace": None,
            "retry_count": 0,
            "max_retries": 3, 
            "compliance_report": None,
            "shrunk_policy": None,
            "status": "waiting",
            "extracted_transaction": None,
            "flow3_eval_result": None      
        }

    def update(self, key, value):
        self.state[key] = value

    def reset(self):
        self.__init__()

class UnifiedAgentCore:
    def __init__(self, blackboard):
        self.bb = blackboard
        
        self.brain = ResilientBrain()
        self.bridge = LegacyBridge()
        self.logger = BlackboardLogger()
        self.reader = PolicyReader()
        
        self.discovery = DiscoveryAgent(self.brain)
        self.transactional = TransactionalAgent(self.brain)
        self.actuator = SandboxActuator()
        self.fixer = FixerAgent(self.brain)

    def _get_dynamic_policy(self, target_file):
        base_name = os.path.basename(target_file)
        domain_prefix = base_name.split("_")[0] if "_" in base_name else "System"
        
        event_type = self.bb.state.get("event_type", "")
        target_flow = "Flow3" if event_type in ["USER_REQUEST", "HITL_RESOLUTION"] else "Flow1"

        policy_text = ""
        policies_dir = os.path.abspath("policies")
        if os.path.exists(policies_dir):
            for file in os.listdir(policies_dir):
                if file.startswith(domain_prefix) and target_flow in file and file.endswith(".pdf"):
                    policy_text += f"--- POLICY DOCUMENT: {file} ---\n"
                    policy_text += self.reader.get_prompt_ready_text(os.path.join(policies_dir, file)) + "\n\n"
                    
        return policy_text if policy_text else "No specific policy found. Infer rules from schema."

    def _get_dynamic_chat_id(self):
        user_req = str(self.bb.state.get('user_goal', ''))
        match = re.search(r'\[CHAT_ID:\s*(\d+)\]', user_req)
        if match:
            return match.group(1)
        return os.getenv("ADMIN_CHAT_ID")

    def _dispatch_enterprise_alert(self, alert_dict):
        admin_token = os.getenv("ADMIN_BOT_TOKEN")
        student_token = os.getenv("STUDENT_BOT_TOKEN", os.getenv("TELEGRAM_BOT_TOKEN"))
        default_chat_id = os.getenv("ADMIN_CHAT_ID")

        message_text = alert_dict.get("message", "")
        if not message_text or not str(message_text).strip(): return
        
        msg_clean = str(message_text).replace('\\n', '\n').replace('<br>', '\n').replace('</br>', '')
        msg_clean = re.sub(r'<(?!/?(b|strong|i|em|u|ins|s|strike|del|a|code|pre)\b)[^>]+>', '', msg_clean)

        needs_buttons = alert_dict.get("requires_hitl_buttons", False)
        target_id = alert_dict.get("target_entity_id", "UNKNOWN")
        alert_type = alert_dict.get("notification_category", "")

        if "MANAGER OVERRIDE REQUIRED" in msg_clean or alert_type == "HITL_Override":
            needs_buttons = True

        if needs_buttons:
            if not admin_token or not default_chat_id: return
            url = f"https://api.telegram.org/bot{admin_token}/sendMessage"
            payload = {
                "chat_id": default_chat_id,
                "text": msg_clean,
                "parse_mode": "HTML",
                "reply_markup": {
                    "inline_keyboard": [
                        [
                            {"text": "Approve", "callback_data": f"hitl_approve_{target_id}"},
                            {"text": "Decline", "callback_data": f"hitl_decline_{target_id}"}
                        ]
                    ]
                }
            }
            try:
                requests.post(url, json=payload, timeout=10)
                print(f"[Router] HITL Override sent to Admin Bot.")
            except Exception as e:
                print(f"[Router] Failed to reach Admin Bot: {e}")

        else:
            try:
                url = f"https://api.telegram.org/bot{student_token}/sendMessage"
                chat_id = self._get_dynamic_chat_id() or default_chat_id
                if chat_id:
                    payload = {"chat_id": chat_id, "text": msg_clean, "parse_mode": "HTML"}
                    response = requests.post(url, json=payload, timeout=10)
                    
                    if response.status_code == 200:
                        print(f"[Router] Alert delivered via Student Bot (HTML).")
                    else:
                        print(f"[Telegram HTML Error] Broken tags detected. Falling back to Plain Text...")
                        
                        plain_text_msg = re.sub(r'<[^>]+>', '', msg_clean)
                        
                        fallback_payload = {"chat_id": chat_id, "text": plain_text_msg} 
                        retry_resp = requests.post(url, json=fallback_payload, timeout=10)
                        
                        if retry_resp.status_code == 200:
                            print(f"[Router] Alert delivered via Student Bot (Plain Text Fallback).")
                        else:
                            print(f"[Telegram Fatal Error] Could not deliver: {retry_resp.text}")
                            
                else:
                    print(f"[Router] Alert dropped for {target_id}. No valid Chat ID found.")
            except Exception as e:
                print(f"[Router] Telegram Delivery Error: {e}")

    def agent_concierge(self):
        print("[Concierge] Analyzing trigger event and routing...")
        original_file = self.bb.state['target_file']
        user_request = self.bb.state['user_goal']

        req_lower = str(user_request).lower()
        
        domain_prefix = os.path.basename(original_file).split("_")[0] if "_" in os.path.basename(original_file) else "General"
        
        if "system boot" in req_lower or "predictive calculus" in req_lower and "manual" not in req_lower:
            self.bb.update("domain", domain_prefix)
            self.bb.update("event_type", "SYSTEM_BOOT")
            self.bb.update("current_event", "intent_extracted")
            return
        elif "manual update" in req_lower:
            self.bb.update("domain", domain_prefix)
            self.bb.update("event_type", "MANUAL_UPDATE")
            self.bb.update("current_event", "intent_extracted")
            return
            
        is_hitl = "hitl_resolution" in req_lower or "manager override" in req_lower or "hitl_approve" in req_lower or "hitl_decline" in req_lower
        
        if is_hitl:
            self.bb.update("event_type", "HITL_RESOLUTION")
            print("[Concierge] Manager HITL Override detected. Pulling exact context from Queue...")
        else:
            self.bb.update("event_type", "USER_REQUEST")
            print("[Concierge] User Request detected. Syncing with Queue...")
            
        target_id = "UNKNOWN"
        id_match = re.search(r'hitl_(?:approve|decline)_([A-Za-z0-9_-]+)', req_lower)
        if id_match:
            target_id = id_match.group(1).upper()
        else:
            exact_match = re.search(r"TARGET_ENTITY_ID\s*=\s*([a-zA-Z0-9_]+)", str(user_request), re.IGNORECASE)
            if exact_match:
                target_id = exact_match.group(1).strip().upper()
            else:
                fallback_match = re.search(r'\b(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9_-]{7,20}\b', str(user_request))
                if fallback_match: target_id = fallback_match.group(0).upper()

        domain_prefix = os.path.basename(original_file).split("_")[0] if "_" in os.path.basename(original_file) else "General"
        recovered_dept = domain_prefix
        recovered_dates = []
        recovered_reason = ""
        recovered_student_name = "Student"
        db_synced = False
        
        try:
            watch_dir = os.path.dirname(original_file) or '.'
            db_files = glob.glob(os.path.join(watch_dir, "*.db"))
            req_dbs = [f for f in db_files if 'request' in os.path.basename(f).lower()]
            db_path = req_dbs[0] if req_dbs else (db_files[0] if db_files else None)
            
            if db_path and target_id != "UNKNOWN":
                conn = sqlite3.connect(db_path, timeout=5)
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute("SELECT * FROM universal_requests WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1", (target_id,))
                row = c.fetchone()
                if row:
                    db_synced = True
                    keys = [k.lower() for k in row.keys()]
                    
                    if 'department' in keys and row['department']: recovered_dept = row['department']
                    if 'student_name' in keys and row['student_name']: recovered_student_name = str(row['student_name'])
                    
                    if 'dates_requested' in keys and row['dates_requested']:
                        raw_dates = str(row['dates_requested'])
                        clean_dates = raw_dates.replace('[', '').replace(']', '').replace("'", "").replace('"', '')
                        recovered_dates = [d.strip() for d in clean_dates.split(',') if d.strip()]
                        
                    if 'reason' in keys and row['reason']: 
                        recovered_reason = str(row['reason']).replace('[', '').replace(']', '')

                conn.close()
                print(f"[Concierge] Queue Memory Recovered for {target_id}: Dept {recovered_dept}")
        except Exception as e:
            print(f"[Concierge] Memory recovery failed: {e}")

        self.bb.update("domain", domain_prefix)
        self.bb.update("department", recovered_dept)
        
        if is_hitl:
            if original_file.endswith('.db'):
                watch_dir = os.path.dirname(original_file) or '.'
                excel_files = glob.glob(os.path.join(watch_dir, "*.xlsx"))
                for f in excel_files:
                    if recovered_dept.lower() in os.path.basename(f).lower():
                        self.bb.update("target_file", f)
                        print(f"[Concierge] HITL Target dynamically switched to Excel: {os.path.basename(f)}")
                        break

            self.bb.update("extracted_transaction", {
                "target_entity_id": target_id,
                "student_name": recovered_student_name,
                "department": recovered_dept,
                "dates_requested": recovered_dates,
                "reason": recovered_reason if recovered_reason else "Manager Override Command", 
                "manager_command": user_request
            })
            self.bb.update("current_event", "flow3_evaluate")
            return
            
        else:
            if db_synced and recovered_dates and recovered_reason:
                print("[Concierge] Clean Queue Payload detected. Bypassing AI Parse.")
                self.bb.update("extracted_transaction", {
                    "target_entity_id": target_id,
                    "student_name": recovered_student_name,
                    "department": recovered_dept,
                    "dates_requested": recovered_dates,
                    "reason": recovered_reason, 
                    "document_provided": "DOCUMENT ATTACHED: YES" in str(user_request).upper(),
                    "raw_system_payload": str(user_request)
                })
                self.bb.update("current_event", "flow3_evaluate")
                return
            else:
                print("[Concierge] Fallback: Engaging AI Parsing Agent...")
                parsed_data = self.transactional.parse_unstructured_request(user_request, recovered_dept)
                
                if not parsed_data.get("is_complete", False):
                    msg = parsed_data.get("missing_info_message", "Please provide more details.")
                    self._dispatch_enterprise_alert({"message": msg, "target_entity_id": target_id, "requires_hitl_buttons": False})
                    self.bb.update("current_event", "completed")
                    return
                    
                self.bb.update("extracted_transaction", parsed_data.get("extracted_data", {}))
                self.bb.update("current_event", "flow3_evaluate") 
                return

    def agent_data_engineer(self):
        print("[Data Engineer] Assembly Line Active...")
        target_file = self.bb.state['target_file']
        domain = self.bb.state['domain']
        event_type = self.bb.state['event_type']
        current_user_request = self.bb.state['user_goal'] 
        
        cache_dir = os.path.abspath("system_cache")
        os.makedirs(cache_dir, exist_ok=True)

        event_flow = "Flow3" if event_type in ["USER_REQUEST", "HITL_RESOLUTION"] else "Flow1_2"
        dynamic_cache_name = f"{domain}_{event_flow}_shrunk_policy.json"
        policy_cache_file = os.path.join(cache_dir, dynamic_cache_name)

        if os.path.exists(policy_cache_file):
            with open(policy_cache_file, 'r', encoding='utf-8') as f: shrunk_policy = f.read()
        else:
            raw_policy = self._get_dynamic_policy(target_file)
            if "No specific policy found" not in raw_policy:
                shrunk_policy = self.discovery.shrink_policy(raw_policy, domain)
                with open(policy_cache_file, 'w', encoding='utf-8') as f: f.write(shrunk_policy)
            else: shrunk_policy = raw_policy
            
        self.bb.update("shrunk_policy", shrunk_policy)
        time.sleep(1)

        schema_cache_file = os.path.join(cache_dir, f"{domain}_schema_cache.json")
        focused_columns = ["ALL"] 
        
        if os.path.exists(schema_cache_file):
            print("[Data Engineer] Loading Schema Map from local cache...")
            with open(schema_cache_file, 'r', encoding='utf-8') as f:
                focused_columns = json.load(f)
            self.bb.update("focused_columns", focused_columns)
        else:
            print("[Data Engineer] No schema cache found. Engaging Scout Agent...")
            schema_headers = self.bridge.get_schema_headers(target_file)
            scout_prompt = self.discovery.generate_scout_prompt(schema_headers, shrunk_policy, domain)
            raw_scout, _ = self.brain.think(scout_prompt, agent_role="scout")
            
            if raw_scout and raw_scout != "Offline":
                scout_json, _ = self.bridge.parse_architect_response(raw_scout)
                if scout_json and "focused_columns" in scout_json:
                    focused_columns = scout_json["focused_columns"]
                    self.bb.update("focused_columns", focused_columns)
                    
                    with open(schema_cache_file, 'w', encoding='utf-8') as f:
                        json.dump(focused_columns, f)

        schema_map = self.bridge.get_funneled_schema(target_file, focused_columns, ghost_mode=True, user_request=current_user_request)
        self.bb.update("schema_context", schema_map)

        prompt = self.discovery.generate_coder_prompt(schema_map, domain, shrunk_policy)
        raw_response, _ = self.brain.think(prompt, agent_role="coder")
        
        if not raw_response or raw_response == "Offline":
            self.bb.update("current_event", "fatal_error")
            return

        json_patch, error = self.bridge.parse_architect_response(raw_response)
        
        if error:
            self.bb.update("error_trace", error)
            self.bb.update("current_event", "execution_failed")
        else:
            self.bb.update("json_patch", json_patch)
            self.bb.update("current_event", "patch_generated")

    def agent_actuator(self):
        print("[Actuator] Running sandbox execution...")
        target_file = self.bb.state['target_file']
        json_patch = self.bb.state['json_patch']
        
        if not json_patch:
            self.bb.update("current_event", "execution_failed")
            return

        success = self.bridge.validate_and_route(json_patch, self.actuator, target_file)
        
        if success:
            self.bb.update("current_event", "execution_success")
        else:
            error_msg = "SYSTEM ALERT: Permission Denied. The Master Ledger file is currently open on a desktop. Please close it to allow AI synchronization."
            self._dispatch_enterprise_alert({"message": error_msg, "requires_hitl_buttons": False})
            self.bb.update("error_trace", "File Locked")
            self.bb.state['retry_count'] += 1
            self.bb.update("current_event", "execution_failed")

    def agent_fixer(self):
        if self.bb.state['retry_count'] > self.bb.state['max_retries']:
             self.bb.update("current_event", "fatal_error")
             return
        
        repair_response, _ = self.fixer.generate_repair_code(
            profile="Domain-Agnostic Cognitive Repair", 
            schema_context=self.bb.state['schema_context'], 
            error_feedback=self.bb.state['error_trace']
        )
        
        json_patch, error = self.bridge.parse_architect_response(repair_response)
        if error:
            self.bb.state['retry_count'] += 1
            self.bb.update("current_event", "execution_failed")
        else:
            self.bb.update("json_patch", json_patch)
            self.bb.update("current_event", "patch_generated")

    def agent_auditor(self):
        print("[Auditor] Finalizing compliance report...")
        target_file = self.bb.state['target_file']
        domain = self.bb.state.get('domain', 'General')
        event_type = self.bb.state.get('event_type')
        current_user_request = self.bb.state.get('user_goal')
        shrunk_policy = self.bb.state.get("shrunk_policy", "None")
        
        macro_columns = self.bb.state.get("focused_columns", ["ALL"])
        fresh_schema = self.bridge.get_funneled_schema(target_file, macro_columns, ghost_mode=False, user_request=current_user_request)

        prompt = self.discovery.generate_auditor_prompt(fresh_schema, shrunk_policy, domain)
        
        prompt += """
        \n[CRITICAL MACRO-AUDIT LOCK]
        You are evaluating multiple entities at once. You MUST strictly compare their metric against the exact threshold defined in the active policy. 
        - Do NOT hallucinate violation statuses for entities that pass the threshold.
        - You must output the exact status or category defined in the policy for every single row.
        - ALERT SELECTIVITY: You MUST generate an 'alert' ONLY for entities in a state of 'Violation', 'Breach', or 'Detention'. Do NOT generate alerts for 'Eligible', 'Healthy', or 'Compliant' entities during macro-scans.
        - HTML SAFETY: Never use naked angle brackets < > around IDs or values. Use <b>Bold</b> or <i>Italic</i> tags for emphasis.
        - NOISE REDUCTION: Treat 'Eligible' standing as a silent success. Only 'Detained' or 'Critical' standings require a Telegram transmission.
        """
        report, _ = self.brain.think(prompt, agent_role="auditor")
        
        self.bb.update("compliance_report", str(report))
        self.logger.archive_mission(self.bb.state)

        try:
            report_data, _ = self.bridge.parse_architect_response(report)
            if report_data:
                if "excel_updates" in report_data and report_data["excel_updates"]:
                    print("[Auditor] Committing final policy statuses to legacy ledger...")
                    self.bridge.validate_and_route(report_data, self.actuator, target_file)

                cache_dir = os.path.abspath("system_cache")
                os.makedirs(cache_dir, exist_ok=True)
                spam_cache_file = os.path.join(cache_dir, "alert_spam_cache.json")
                
                spam_cache = {}
                if os.path.exists(spam_cache_file):
                    try:
                        with open(spam_cache_file, "r") as f:
                            spam_cache = json.load(f)
                    except: pass

                for alert in report_data.get("alerts", []):
                    target_id = alert.get("target_entity_id", "UNKNOWN")
                    
                    cooldown_seconds = alert.get("cooldown_days", 1) * 86400
                    now = time.time()
                    
                    if target_id in spam_cache and (now - spam_cache.get(target_id, 0)) < cooldown_seconds:
                        print(f"[Spam Shield] Suppressing duplicate violation alert for {target_id}.")
                        continue
                        
                    self._dispatch_enterprise_alert(alert)
                    spam_cache[target_id] = now
                    
                with open(spam_cache_file, "w") as f:
                    json.dump(spam_cache, f)

        except Exception as e:
            print(f"[Auditor] Post-processing error: {e}")

        self.bb.update("current_event", "completed")

    def agent_flow3_evaluator(self):
        print("[Evaluator] Comparing Request against Triangle of Truth...")
        target_file = self.bb.state['target_file']
        request_data = self.bb.state.get("extracted_transaction", {})
        domain = self.bb.state.get('domain', 'General')
        event_type = self.bb.state.get('event_type')
        
        cache_dir = os.path.abspath("system_cache")
        event_flow = "Flow3" if event_type in ["USER_REQUEST", "HITL_RESOLUTION"] else "Flow1_2"
        dynamic_cache_name = f"{domain}_{event_flow}_shrunk_policy.json"
        policy_cache_file = os.path.join(cache_dir, dynamic_cache_name)
        
        if os.path.exists(policy_cache_file):
            with open(policy_cache_file, 'r', encoding='utf-8') as f:
                active_policy = f.read()
        else:
            print("[Evaluator] No Flow 3 cache found. Engaging Reader Agent...")
            raw_policy = self._get_dynamic_policy(target_file)
            if "No specific policy found" not in raw_policy:
                active_policy = self.discovery.shrink_policy(raw_policy, domain)
                with open(policy_cache_file, 'w', encoding='utf-8') as f:
                    f.write(active_policy)
            else:
                active_policy = raw_policy

        monthly_row = self.bridge.get_funneled_schema(target_file, ["ALL"], ghost_mode=False, user_request=json.dumps(request_data))
        
        summary_row = self.bridge.get_global_metric_summary(target_file, request_data.get("target_entity_id"))
        
        row_data = f"--- MONTHLY TRANSACTIONAL DATA ---\n{monthly_row}\n\n--- GLOBAL SUMMARY METRIC ---\n{summary_row}"
        
        eval_result = self.transactional.evaluate_transaction(request_data, row_data, active_policy, domain)
        
        if event_type == "HITL_RESOLUTION" or "MANAGER OVERRIDE" in str(request_data).upper():
            decision = "Approved" if "APPROVE" in str(request_data).upper() else "Declined"
            eval_result["decision"] = decision
            
        self.bb.update("flow3_eval_result", eval_result)
        self.bb.update("current_event", "flow3_execute")

    def agent_flow3_executor(self):
        print("[Executor] Generating Execution Plan for Flow 3...")
        eval_result = self.bb.state.get("flow3_eval_result", {})
        request_data = self.bb.state.get("extracted_transaction", {})
        target_file = self.bb.state['target_file']
        domain = self.bb.state.get('domain', 'General')
        event_type = self.bb.state.get('event_type')
        
        is_override = (event_type == "HITL_RESOLUTION")
        
        pristine_raw_policy = self._get_dynamic_policy(target_file)
        
        plan = self.transactional.generate_execution_plan(eval_result, request_data, pristine_raw_policy, is_override)
        
        self.bridge.validate_and_route(plan, self.actuator, target_file)

        for alert in plan.get("alerts", []):
            self._dispatch_enterprise_alert(alert)

        self.bb.update("compliance_report", json.dumps({"target_id": request_data.get("target_entity_id"), "decision": eval_result.get("decision")}))
        self.logger.archive_mission(self.bb.state)
        self.bb.update("current_event", "completed")
        
class MiddlewareEventLoop:
    def __init__(self):
        self.bb = SharedBlackboard()
        self.agents = UnifiedAgentCore(self.bb)
        self.cache_dir = os.path.abspath("system_cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.lock_file = os.path.join(self.cache_dir, ".global_mission_lock")

    def run_mission(self, user_request, file_path):
        try:
            with open(self.lock_file, 'w') as f: f.write("Locked")
            self.bb.reset()
            self.bb.update("user_goal", user_request)
            self.bb.update("target_file", file_path)
            self.bb.update("current_event", "user_request")

            while self.bb.state["current_event"] not in ["completed", "fatal_error"]:
                event = self.bb.state["current_event"]
                if event == "user_request": self.agents.agent_concierge()
                elif event == "intent_extracted": self.agents.agent_data_engineer()
                elif event == "patch_generated": self.agents.agent_actuator()
                elif event == "execution_failed": self.agents.agent_fixer()
                elif event == "execution_success": self.agents.agent_auditor()
                elif event == "flow3_evaluate": self.agents.agent_flow3_evaluator()
                elif event == "flow3_execute": self.agents.agent_flow3_executor()
                time.sleep(4.0)

        finally:
            if os.path.exists(self.lock_file): os.remove(self.lock_file)