import os
import time
import requests
import datetime
import threading
import re
import json
import sqlite3
import glob
from dotenv import load_dotenv

from core.blackboard_orchestrator import MiddlewareEventLoop
from core.brain import ResilientBrain

load_dotenv()

class TelegramBlackboardService:
    def __init__(self, role="student"):
        self.role = role
        
        if self.role == "admin":
            self.token = os.getenv("ADMIN_BOT_TOKEN")
        else:
            self.token = os.getenv("STUDENT_BOT_TOKEN", os.getenv("TELEGRAM_BOT_TOKEN"))
            
        self.url = f"https://api.telegram.org/bot{self.token}/" if self.token else None
        self.offset = None
        self.startup_time = int(time.time())
        self.proof_dir = os.path.abspath("proof_uploads")
        os.makedirs(self.proof_dir, exist_ok=True)
        self.brain = ResilientBrain()

    def _get_updates(self):
        try:
            res = requests.get(self.url + "getUpdates", params={"timeout": 30, "offset": self.offset})
            return res.json().get("result", [])
        except Exception:
            return []

    def _send_message(self, chat_id, text, needs_buttons=False, target_id=None):
        if not self.token: return
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        
        is_rejection = "DECLINED" in text.upper() or "❌" in text
        
        if not is_rejection:
            if needs_buttons or "MANAGER OVERRIDE REQUIRED" in text.upper() or "hitl" in text.lower():
                if not target_id or target_id == "UNKNOWN":
                    id_match = re.findall(r'\b[A-Za-z0-9_-]{7,20}\b', text)
                    target_id = "UNKNOWN"
                    for match in id_match:
                        if any(c.isalpha() for c in match) and any(c.isdigit() for c in match):
                            target_id = match
                            break
                
                if target_id != "UNKNOWN":
                    payload["reply_markup"] = {
                        "inline_keyboard": [[
                            {"text": "Approve Request", "callback_data": f"hitl_approve_{target_id}"},
                            {"text": "Decline Request", "callback_data": f"hitl_decline_{target_id}"}
                        ]]
                    }

        try:
            requests.post(self.url + "sendMessage", json=payload, timeout=20)
        except Exception as e:
            print(f"Telegram Send Error ({self.role}): {e}")

    def _answer_callback(self, callback_id, text):
        if not self.token: return
        try:
            requests.post(self.url + "answerCallbackQuery", json={"callback_query_id": callback_id, "text": text}, timeout=15)
        except: pass

    def _download_file(self, file_id, user_id):
        if not self.token: return None
        try:
            res = requests.get(self.url + "getFile", params={"file_id": file_id}).json()
            if not res.get("ok"): return None
            file_path = res["result"]["file_path"]
            ext = file_path.split(".")[-1]
            file_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
            file_data = requests.get(file_url).content
            timestamp = datetime.datetime.now().strftime("%Y%m%d")
            filename = f"{timestamp}_{user_id}_proof.{ext}"
            full_path = os.path.join(self.proof_dir, filename)
            with open(full_path, "wb") as f:
                f.write(file_data)
            return full_path
        except Exception as e:
            print(f"Telegram Download Error: {e}")
            return None

    def _process_mission_thread(self, chat_id, wrapped_text, target_file):
        print(f"[{self.role.upper()} BOT] Starting Blackboard Mission for Chat: {chat_id}")
        try:
            orchestrator = MiddlewareEventLoop()
            orchestrator.run_mission(wrapped_text, target_file)
            print(f"[{self.role.upper()} BOT] Mission completed successfully.")
        except Exception as e:
            print(f"Telegram Thread Error: {e}")
            self._send_message(chat_id, "System Error: Could not complete the request.")

    def handle_incoming(self, chat_id, user_text, file_id=None):
        chat_id_str = str(chat_id)
        is_manager_override = "MANAGER OVERRIDE DECISION" in user_text

        casual_greetings = ['hi', 'hello', 'hey', '/start', 'start']
        if user_text.lower().strip() in casual_greetings:
            msg = "Hello! I am the Executive Admin Terminal." if self.role == "admin" else "Hello! I am the System Notification Node."
            self._send_message(chat_id, f"{msg} How can I assist you today?")
            return 

        if file_id:
            target_id = "UNKNOWN"
            id_match = re.findall(r'\b[A-Za-z0-9_-]{7,20}\b', user_text)
            for match in id_match:
                if any(c.isalpha() for c in match) and any(c.isdigit() for c in match):
                    target_id = match
                    break
            
            if target_id == "UNKNOWN":
                self._send_message(chat_id, "Please include your Official ID (e.g., 2026EDU0031 or CORP-8801) in your message so I can securely authenticate your records.")
                return

            self._send_message(chat_id, f"Downloading document for {target_id}...")
            file_path = self._download_file(file_id, target_id)
            
            if file_path:
                user_text += f" | LATE UPLOAD RECEIVED: DOCUMENT ATTACHED: YES"
                self._send_message(chat_id, "Document secured. Resuming audit...")
            else:
                self._send_message(chat_id, "Failed to download document. Please try again.")
                return

        if self.role == "student" and not file_id:
            target_id = "UNKNOWN"
            id_match = re.findall(r'\b[A-Za-z0-9_-]{7,20}\b', user_text)
            for match in id_match:
                if any(c.isalpha() for c in match) and any(c.isdigit() for c in match):
                    target_id = match
                    break
            
            if target_id == "UNKNOWN":
                self._send_message(chat_id, "Please include your Official ID (e.g., 2026EDU0031 or CORP-8801) in your message so I can securely authenticate and locate your specific records.")
                return
                
            self._send_message(chat_id, "Checking your records...")
            try:
                payload = {"user_id": target_id, "message": user_text}
                res = requests.post("http://127.0.0.1:8000/api/v1/chat", json=payload, timeout=10)
                if res.status_code == 200:
                    self._send_message(chat_id, res.json().get("message", "I couldn't process that."))
                else:
                    self._send_message(chat_id, "System Error: Could not reach the Chat Node.")
            except Exception as e:
                self._send_message(chat_id, "System Error: Connection refused.")
            
            return 

        if self.role == "admin":
            if not is_manager_override:
                wrapped_text = f"[SYSTEM WRAPPER]\n[CHAT_ID: {chat_id}]\n[SOURCE: TELEGRAM]\nUSER MESSAGE: \"{user_text}\"\nCRITICAL RULES: You are speaking to the Admin. Full Read/Write access granted."
            else:
                wrapped_text = f"[CHAT_ID: {chat_id}]\n[SOURCE: TELEGRAM]\n{user_text}"
        else:
            wrapped_text = f"[SYSTEM WRAPPER]\n[CHAT_ID: {chat_id}]\n[SOURCE: TELEGRAM]\nUSER MESSAGE: \"{user_text}\"\nCRITICAL RULES: Processing late document upload."

        watch_dir = os.getenv("WATCH_DIRECTORY", "data")
        available_files = [f for f in os.listdir(watch_dir) if f.endswith(('.xlsx', '.db')) and not f.startswith('~$')]
        
        if not available_files:
            self._send_message(chat_id, "System Error: No legacy data nodes connected.")
            return

        prompt = f"ACT AS: AI Concierge. USER REQUEST: \"{wrapped_text}\" AVAILABLE FILES: {available_files}. MISSION: Identify target file and domain. Output ONLY valid JSON: {{\"target_file\": \"filename\", \"domain\": \"Domain\"}}"
        
        route_data = {}
        response, _ = self.brain.think(prompt, agent_role="concierge")
        if response:
            try:
                route_data = json.loads(response.replace("```json", "").replace("```", "").strip())
            except: pass

        target_filename = route_data.get("target_file", available_files[0])
        target_file = os.path.join(watch_dir, target_filename)

        mission_thread = threading.Thread(target=self._process_mission_thread, args=(chat_id, wrapped_text, target_file), daemon=True)
        mission_thread.start()

    def run_polling(self):
        if not self.token: return
        print(f"[{self.role.upper()} BOT] Online and awaiting requests...")
        try:
            initial_updates = requests.get(self.url + "getUpdates", params={"timeout": 5}).json().get("result", [])
            if initial_updates: self.offset = initial_updates[-1]['update_id'] + 1
        except: pass

        while True:
            updates = self._get_updates()
            for update in updates:
                self.offset = update['update_id'] + 1
                if 'callback_query' in update:
                    cb = update['callback_query']
                    data = cb['data'] 
                    
                    if data.startswith("hitl_approve_"):
                        self._answer_callback(cb['id'], "Approved!")
                        decision_text = f"MANAGER OVERRIDE DECISION: {data}"
                        self.handle_incoming(cb['message']['chat']['id'], decision_text)
                    elif data.startswith("hitl_decline_"):
                        self._answer_callback(cb['id'], "Declined.")
                        decision_text = f"MANAGER OVERRIDE DECISION: {data}"
                        self.handle_incoming(cb['message']['chat']['id'], decision_text)

                elif 'message' in update:
                    msg = update['message']
                    if msg.get('date', 0) < self.startup_time: continue
                    
                    user_text = msg.get('text', msg.get('caption', ''))
                    
                    file_id = None
                    if 'document' in msg:
                        file_id = msg['document']['file_id']
                    elif 'photo' in msg:
                        file_id = msg['photo'][-1]['file_id']
                        
                    if user_text.strip() or file_id: 
                        self.handle_incoming(msg['chat']['id'], user_text, file_id)
            time.sleep(2)

def start_student_bot(): TelegramBlackboardService(role="student").run_polling()
def start_admin_bot(): TelegramBlackboardService(role="admin").run_polling()

if __name__ == "__main__":
    t1 = threading.Thread(target=start_student_bot, daemon=True)
    t2 = threading.Thread(target=start_admin_bot, daemon=False)
    t1.start()
    t2.start()