import os
import json
import logging
from datetime import datetime

class BlackboardLogger:
    def __init__(self):
        self.archive_dir = os.path.abspath("memory_archive")
        self.logs_dir = os.path.abspath("logs")
        os.makedirs(self.archive_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)

        log_filename = datetime.now().strftime("middleware_%Y-%m-%d.log")
        self.log_filepath = os.path.join(self.logs_dir, log_filename)
        
        logging.basicConfig(
            filename=self.log_filepath,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.human_logger = logging.getLogger("Middleware_Orchestrator")

    def archive_mission(self, state):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_file = str(state.get("target_file", "unknown"))
        
        base_name = os.path.basename(target_file)
        domain = base_name.split("_")[0] if "_" in base_name else "system"
        
        archive_path = os.path.join(self.archive_dir, f"{timestamp}_{domain}_mission.json")
        safe_state = {k: v for k, v in state.items() if k not in ["schema_context"]}
        
        try:
            with open(archive_path, "w", encoding="utf-8") as f:
                json.dump(safe_state, f, indent=4)
        except Exception as e:
            print(f"⚠️ [Logger] Failed to save JSON archive: {e}")
            
        event = state.get("current_event", "unknown")
        report = state.get("compliance_report", "No compliance report generated.")
        
        self.human_logger.info(f"MISSION COMPLETE: Target Node = {base_name} | Final State = {event}")
        
        try:
            clean_json = report.replace("```json", "").replace("```", "").strip()
            clean_json = clean_json[clean_json.find("{"):clean_json.rfind("}")+1]
            report_data = json.loads(clean_json)
            if report_data.get("status") == "violation":
                for alert in report_data.get("alerts", []):
                    self.human_logger.warning(f"POLICY VIOLATION DETECTED: {alert.get('message')}")
            else:
                self.human_logger.info("AUDIT PASS: System completely compliant.")
        except:
            self.human_logger.info(f"RAW REPORT OUTPUT:\n{report}")
            
        self.human_logger.info("=" * 60)
        print(f"💾 [Memory] Persistent decision archived: {os.path.basename(archive_path)}")
        print(f"📝 [Logger] Human-readable trace appended to: {os.path.basename(self.log_filepath)}")