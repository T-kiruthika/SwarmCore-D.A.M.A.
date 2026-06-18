import time
import os
from datetime import datetime
from dotenv import load_dotenv

from core.blackboard_orchestrator import MiddlewareEventLoop

load_dotenv()

WATCH_DIR = os.getenv("WATCH_DIRECTORY", "data")
CACHE_DIR = os.path.abspath("system_cache")

TRANSACTIONAL_KEYWORDS = ('request', 'transaction', 'log', 'queue')

class PredictiveHeartbeat:
    def __init__(self, watch_dir):
        self.watch_dir = watch_dir
        self.last_state = {}
        self.rest_period = 25 
        self.lock_file = os.path.join(CACHE_DIR, ".global_mission_lock")
        
        os.makedirs(self.watch_dir, exist_ok=True)
        os.makedirs(CACHE_DIR, exist_ok=True)

    def _infer_routing(self, filename):
        """Dynamically extracts Domain and Department from ANY file prefix."""
        if filename.startswith('~$') or '_' not in filename: 
            return None, None
            
        parts = filename.replace(".xlsx", "").replace(".db", "").split("_")
        
        domain = parts[0].upper()
        
        if len(parts) > 2:
            dept = "_".join(parts[2:]) 
        else:
            dept = "General"
            
        return domain, dept

    def _is_valid_macro_node(self, filename):
        """Checks if a file is a valid Flow 1/2 Macro Ledger."""
        if not filename.endswith(('.xlsx', '.db')) or filename.startswith('~$'):
            return False
        if any(keyword in filename.lower() for keyword in TRANSACTIONAL_KEYWORDS):
            return False
        return True

    def _update_all_baselines(self):
        """Records the current timestamp of all files so the monitor ignores them."""
        for filename in os.listdir(self.watch_dir):
            if self._is_valid_macro_node(filename):
                filepath = os.path.join(self.watch_dir, filename)
                try:
                    self.last_state[filename] = os.path.getmtime(filepath)
                except FileNotFoundError:
                    pass

    def run_full_system_scan(self):
        print(f"\n[System] Starting Sequential Boot Analysis: {datetime.now().strftime('%H:%M:%S')}")
        print("Strategy: One-by-One Synchronous Execution -> Rest -> Next (Zero Token Blast)")
        
        valid_nodes = [f for f in os.listdir(self.watch_dir) if self._is_valid_macro_node(f)]
        
        for filename in valid_nodes:
            filepath = os.path.join(self.watch_dir, filename)
            domain, dept = self._infer_routing(filename)
            
            if not domain:
                continue

            try:
                print(f"\n[Boot Scanner] Analyzing Node: {filename} ({domain} Domain)")
                message = "SYSTEM BOOT: Perform predictive calculus on the file. Ignore future dates and flag policy breaches."
                
                orchestrator = MiddlewareEventLoop()
                orchestrator.run_mission(message, filepath)
                
                print(f"[Boot Scanner] Mission complete. Taking a {self.rest_period}s rest to cool down AI tokens...")
                time.sleep(self.rest_period)
                
            except FileNotFoundError:
                continue 
        
        self._update_all_baselines()
        print(f"\n[System] Sequential Boot Analysis Complete. Entering Silent Observation Mode...")

    def monitor_loop(self):
        self.run_full_system_scan()
        
        was_locked = False

        while True:
            if os.path.exists(self.lock_file):
                if not was_locked:
                    print("[Observer] Orchestrator lock detected. Pausing manual observation...")
                was_locked = True
                time.sleep(2)
                continue
            
            if was_locked:
                print("[Observer] Orchestrator lock released. Resetting baselines to ignore AI modifications.")
                self._update_all_baselines()
                was_locked = False
                continue

            for filename in os.listdir(self.watch_dir):
                if not self._is_valid_macro_node(filename):
                    continue
                 
                filepath = os.path.join(self.watch_dir, filename)
                try:
                    current_mtime = os.path.getmtime(filepath)

                    if filename not in self.last_state or current_mtime > self.last_state[filename]:
                        domain, dept = self._infer_routing(filename)
                        
                        if domain:
                            print(f"\n[Observer] HUMAN update detected on {filename}. Triggering self-healing mission.")
                            message = f"MANUAL UPDATE: A human modified raw data in '{filename}'. Recalculate derived totals."
                            
                            orchestrator = MiddlewareEventLoop()
                            orchestrator.run_mission(message, filepath)
                             
                            self._update_all_baselines()
                             
                            print(f"[Observer] Self-healing complete. Resting for {self.rest_period}s...")
                            time.sleep(self.rest_period)

                except FileNotFoundError:
                    pass 
            
            time.sleep(5)

if __name__ == "__main__":
    heartbeat = PredictiveHeartbeat(WATCH_DIR)
    heartbeat.monitor_loop()