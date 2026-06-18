import os
import glob
from core.blackboard_orchestrator import MiddlewareEventLoop
from dotenv import load_dotenv

load_dotenv()

def run_cli_mode():
    """
    Direct Terminal Interface for the Blackboard Orchestrator.
    UPGRADED: 3-Flow Event-Driven Architecture Tester.
    """
    print("===================================================")
    print("BLACKBOARD ORCHESTRATOR - 3-FLOW CLI TESTER")
    print("===================================================")

    watch_dir = os.getenv("WATCH_DIRECTORY", "data")
    os.makedirs(watch_dir, exist_ok=True)
    
    valid_files = []
    for ext in ('*.xlsx', '*.db', '*.csv'):
        valid_files.extend(glob.glob(os.path.join(watch_dir, ext)))
    
    if not valid_files:
        print(f"No legacy data files found in '{watch_dir}'.")
        print("Ensure you have run your seeder first to generate test data.")
        return

    print("\nDiscovered Legacy Nodes:")
    for idx, file_path in enumerate(valid_files):
        print(f"[{idx + 1}] {os.path.basename(file_path)}")
    
    exit_idx = len(valid_files) + 1
    print(f"[{exit_idx}] Exit")
    
    choice = input(f"\nSelect target node to audit (1-{exit_idx}): ").strip()

    try:
        choice_idx = int(choice) - 1
        if choice_idx + 1 == exit_idx:
            print("Exiting Sandbox...")
            return
        target_file = valid_files[choice_idx]
    except (ValueError, IndexError):
        print("Invalid choice. Exiting Sandbox...")
        return

    print("\nSELECT EVENT FLOW TO TEST:")
    print("[1] Flow 1: System Boot (Predictive Scan & Pending Audit Cleanup)")
    print("[2] Flow 2: Manual Update (Self-Heal a modified file)")
    print("[3] Flow 3: User Request (Web Portal / Telegram Intent)")
    
    flow_choice = input("\nSelect flow trigger (1-3): ").strip()

    if flow_choice == '1':
        user_msg = "SYSTEM BOOT: Perform predictive calculus on the file. Ignore future dates and flag policy breaches."
        print(f"\nInitiating SYSTEM_BOOT Mission for {os.path.basename(target_file)}...")
    
    elif flow_choice == '2':
        user_msg = "MANUAL UPDATE: A human modified the raw data. Perform predictive calculus to self-heal derived totals."
        print(f"\nInitiating MANUAL_UPDATE Mission for {os.path.basename(target_file)}...")
    
    else:
        filename = os.path.basename(target_file).upper()
        if filename.startswith("EDU_"):
            default_msg = "I need 3 days of medical leave starting tomorrow."
        elif filename.startswith("FIN_"):
            default_msg = "I want to apply for a $50,000 commercial loan."
        else:
            default_msg = "Update my status in the system."

        user_msg = input(f"\nEnter user request (Press Enter for default: '{default_msg}'): ").strip()
        if not user_msg:
            user_msg = default_msg
        print(f"\nInitiating USER_REQUEST Mission for {os.path.basename(target_file)}...")

    orchestrator = MiddlewareEventLoop()
    
    orchestrator.run_mission(
        user_request=user_msg, 
        file_path=target_file
    )

if __name__ == "__main__":
    try:
        run_cli_mode()
    except KeyboardInterrupt:
        print("\nCLI Terminated.")