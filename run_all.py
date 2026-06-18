import subprocess
import sys
import time
import os

def bootstrap_environment():
    """Checks if the legacy data environment exists. Runs seeder if missing."""
    watch_dir = os.getenv("WATCH_DIRECTORY", "data")
    if not os.path.exists(watch_dir) or not os.listdir(watch_dir):
        print("[System] Legacy data environment missing or empty.")
        print("[System] Auto-running Enterprise Seeder to generate test data...")
        try:
            subprocess.run([sys.executable, "edu_enterprise_seeder.py"], check=True)
            print("[System] Enterprise data seeded successfully.")
        except subprocess.CalledProcessError as e:
            print(f"[System] Failed to seed data: {e}")
            sys.exit(1)

def start_services():
    print("===================================================")
    print("BOOTING AGENT-AWARE MIDDLEWARE ECOSYSTEM")
    print("===================================================")
    print("Architecture: Event-Driven Shared Blackboard")
    print("Features: Self-Healing, Predictive Autonomous Scanning")
    print("Status: PRODUCTION READY")
    print("===================================================")
    
    bootstrap_environment()
    python_exec = sys.executable
    processes = []

    try:
        print("[System] Booting API Gateway (Port 8000)...")
        p1 = subprocess.Popen([python_exec, "api_gateway.py"])
        processes.append(p1)
        
        print("[System] Waiting for API Gateway to stabilize network ports...")
        time.sleep(8) 
        
        print("[System] Booting Telegram Listener Node...")
        p2 = subprocess.Popen([python_exec, "telegram_service.py"])
        processes.append(p2)
        time.sleep(2)

        print("[System] Booting Autonomous Monitor (30-Day Cycle Engine)...")
        p3 = subprocess.Popen([python_exec, "autonomous_monitor.py"])
        processes.append(p3)

        print("\n[System] All systems online. Autonomous Scanning is active.")
        print("Press Ctrl+C in this terminal to safely shut down.\n")
        
        for p in processes:
            p.wait()

    except KeyboardInterrupt:
        print("\n[System] Interruption received. Shutting down middleware ecosystem safely...")
        for p in processes:
            p.terminate()
            p.wait() 
        print("[System] Graceful shutdown complete.")

if __name__ == "__main__":
    start_services()