from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import os, sqlite3, json, glob
import logging, re
from dotenv import load_dotenv
from core.blackboard_orchestrator import MiddlewareEventLoop

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

WATCH_DIR = os.getenv("WATCH_DIRECTORY", "data")
MEMORY_ARCHIVE_DIR = os.path.abspath("memory_archive")

@app.get("/api/status")
async def get_system_status():
    """Reads the data folder to show monitored nodes for the Admin Dashboard."""
    watchers = []
    if os.path.exists(WATCH_DIR):
        for file in os.listdir(WATCH_DIR):
            if file.endswith(".db") or file.endswith(".xlsx") and not file.startswith('~$'):
                prefix = file.split("_")[0] if "_" in file else "System"
                watchers.append({"domain": prefix, "file": file})
    return {"watchers": watchers}

@app.get("/api/logs")
async def get_persistent_logs():
    """Streams the AI reasoning JSONs from memory archive to the Admin Dashboard."""
    logs = []
    if os.path.exists(MEMORY_ARCHIVE_DIR):
        files = sorted(glob.glob(os.path.join(MEMORY_ARCHIVE_DIR, "*.json")), reverse=True)[:50]
        for f in files:
            try:
                with open(f, 'r', encoding="utf-8") as jf:
                    logs.append(json.load(jf))
            except Exception:
                pass
    return logs

@app.get("/api/v1/resource/status")
async def get_request_status(user_id: str, domain: str = "System"):
    """Reads the latest status for a specific user to update the portal live."""
    domain_prefix = domain[:3].upper() if domain else "System"
    db_files = glob.glob(os.path.join(WATCH_DIR, f"{domain_prefix}_*.db"))
    request_dbs = [f for f in db_files if 'request' in os.path.basename(f).lower()]
    target_db = request_dbs[0] if request_dbs else (db_files[0] if db_files else None)

    if target_db and os.path.exists(target_db):
        try:
            conn = sqlite3.connect(target_db, timeout=10)
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM universal_requests WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1", (user_id,))
            row = cursor.fetchone()
            conn.close()
            if row:
                return {"status": row[0]}
        except Exception as e:
            print(f"[Gateway] Error reading user status: {e}")
            
    return {"status": "Processing"} 

@app.get("/api/v1/resource/queue")
async def get_hitl_queue(domain: str = "ALL"):
    """Pulls recent requests for the Admin Dashboard to populate the Manager Queue."""
    queue = []
    
    if domain == "ALL" or domain == "System":
        db_files = glob.glob(os.path.join(WATCH_DIR, "*.db"))
    else:
        domain_prefix = domain[:3].upper()
        db_files = glob.glob(os.path.join(WATCH_DIR, f"{domain_prefix}_*.db"))
        
    request_dbs = [f for f in db_files if 'request' in os.path.basename(f).lower()]
    
    for target_db in request_dbs:
        if os.path.exists(target_db):
            try:
                conn = sqlite3.connect(target_db, timeout=10)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("SELECT * FROM universal_requests ORDER BY timestamp DESC LIMIT 50")
                rows = cursor.fetchall()
                conn.close()
                
                for row in rows:
                    row_dict = dict(row)
                    
                    if 'student_name' not in row_dict:
                        row_dict['student_name'] = row_dict.get('user_id', 'Unknown ID')
                    if 'dates_requested' not in row_dict:
                        row_dict['dates_requested'] = 'See Details'
                    if 'reason' not in row_dict:
                        row_dict['reason'] = row_dict.get('request_reason', 'No specific reason provided')
                        
                    queue.append(row_dict)
                    
            except Exception as e:
                print(f"[Gateway] Error reading HITL queue from {target_db}: {e}")
    queue.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    return queue[:50]

def run_agentic_mission(user_msg, target_file):
    """Background worker function."""
    try:
        orchestrator = MiddlewareEventLoop()
        orchestrator.run_mission(user_msg, target_file)
    except Exception as e:
        print(f"[Background Mission Error]: {str(e)}")

@app.post("/api/v1/resource/sync")
async def universal_sync(request: Request, background_tasks: BackgroundTasks):
    """
    The Entry Point: Acts as a Kafka-style ingestion queue.
    Instantly extracts core data and writes it safely to SQLite before processing.
    """
    try:
        data = await request.json()
        
        domain = data.get("domain", "General")
        user_id = data.get("user_id", data.get("studentId", data.get("id", "unknown")))
        dept = data.get("department", "")
        raw_msg = data.get("message", "")
        
        target_id = user_id
        id_match = re.search(r"TARGET_ENTITY_ID = (.*?)]", raw_msg)
        if id_match: 
            target_id = id_match.group(1).strip()
        
        dates_requested = data.get("dates_requested", "TBD")
        d_match = re.search(r"requests? (?:leave |loan |approval )?for (.*?)(?:\.|$)", raw_msg, re.IGNORECASE)
        if d_match: dates_requested = d_match.group(1).strip()
        
        reason = data.get("reason", "")
        r_match = re.search(r"REASON: (.*?)(?:\.|$)", raw_msg, re.IGNORECASE)
        if r_match: reason = r_match.group(1).strip()
        
        student_name = target_id 
        s_match = re.search(r"\[(?:STUDENT|CORP|PATIENT|USER):\s*(.*?)\s*\|", raw_msg, re.IGNORECASE)
        if s_match: student_name = s_match.group(1).strip()

        user_id = target_id
        data["user_id"] = target_id
        data["student_id"] = target_id  
        data["entity_name"] = student_name
        data["dates_requested"] = dates_requested
        data["reason"] = reason
        
        metadata_dict = {k: v for k, v in data.items() if k not in ["domain", "user_id", "studentId", "department", "source", "message", "file_data", "file_name"]}
        
        import base64
        file_name = data.get("file_name")
        file_data = data.get("file_data")
        
        if file_name and file_data:
            proof_dir = os.path.abspath("proof_uploads")
            os.makedirs(proof_dir, exist_ok=True)
            
            if "," in file_data:
                file_data = file_data.split(",")[1]
                
            safe_filename = f"{user_id}_{file_name.replace(' ', '_')}"
            file_path = os.path.join(proof_dir, safe_filename)
            
            try:
                with open(file_path, "wb") as fh:
                    fh.write(base64.b64decode(file_data))
                print(f"[Gateway] Saved Web Document for {user_id}: {safe_filename}")
            except Exception as e:
                print(f"[Gateway] Failed to save web file: {e}")
        
        os.makedirs(WATCH_DIR, exist_ok=True)
        domain_prefix = domain[:3].upper() 
        raw_files = glob.glob(os.path.join(WATCH_DIR, f"{domain_prefix}_*.xlsx"))
        available_files = [f for f in raw_files if not os.path.basename(f).startswith('~$')]
        
        target_file = None
        if available_files:
            if dept:
                dept_matches = [f for f in available_files if dept.lower() in f.lower()]
                target_file = dept_matches[0] if dept_matches else available_files[0]
            else:
                target_file = available_files[0]
        else:
            target_file = os.path.join(WATCH_DIR, f"{domain_prefix}_Default.xlsx")

        if user_id != "SYSTEM_OBSERVER":
            db_files = glob.glob(os.path.join(WATCH_DIR, f"{domain_prefix}_*.db"))
            if db_files:
                request_dbs = [f for f in db_files if 'request' in os.path.basename(f).lower()]
                db_path = request_dbs[0] if request_dbs else db_files[0]
            else:
                db_path = os.path.join(WATCH_DIR, f"{domain_prefix}_requests.db")

            print(f"[Gateway] Queuing request safely into: {os.path.basename(db_path)}")

            conn = sqlite3.connect(db_path, timeout=10)
            cursor = conn.cursor()
            
            cursor.execute('''CREATE TABLE IF NOT EXISTS universal_requests (
                    request_id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    user_id VARCHAR(50), 
                    student_name VARCHAR(100),
                    domain VARCHAR(50),
                    department VARCHAR(50),
                    dates_requested VARCHAR(100),
                    reason TEXT,
                    request_reason TEXT,
                    metadata TEXT,
                    status VARCHAR(20) DEFAULT 'Processing',
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )''')
            
            for new_col in ["student_name VARCHAR(100)", "dates_requested VARCHAR(100)", "reason TEXT"]:
                try:
                    cursor.execute(f"ALTER TABLE universal_requests ADD COLUMN {new_col}")
                except sqlite3.OperationalError:
                    pass 
            
            cursor.execute("""
                INSERT INTO universal_requests 
                (user_id, student_name, domain, department, dates_requested, reason, request_reason, metadata, status) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Processing')
            """, (user_id, student_name, domain, dept, dates_requested, reason, raw_msg, json.dumps(metadata_dict)))
            
            conn.commit()
            conn.close()

        print(f"[Gateway] Mission triggered for {user_id}...")
        
        handoff_msg = f"[SYSTEM QUEUE TRIGGER] TARGET_ENTITY_ID = {user_id} | DOMAIN = {domain}\n{raw_msg}"
        background_tasks.add_task(run_agentic_mission, handoff_msg, target_file)
            
        return {
            "status": "Success", 
            "message": "Autonomous Audit initialized in background."
        }
        
    except Exception as e:
        print(f"[Gateway Error]: {str(e)}")
        return {"status": "Error", "message": f"Ingestion Failed: {str(e)}"}

@app.post("/api/v1/chat")
async def secure_chat_endpoint(request: Request):
    try:
        import pandas as pd
        import glob, os, json
        from core.brain import ResilientBrain
        
        payload = await request.json()
        user_id = payload.get("user_id", "").strip().upper()
        msg = payload.get("message", "").lower()
        domain = payload.get("domain", "General").strip() 
        
        domain_prefix = domain[:3].upper()
        search_pattern = os.path.join(WATCH_DIR, f"{domain_prefix}_*.xlsx")
        files = glob.glob(search_pattern)
        
        target_row_data = None
        brain = ResilientBrain()

        merged_profile = {}
        for file in files:
            try:
                xls = pd.ExcelFile(file)
                for sheet in xls.sheet_names:
                    df = pd.read_excel(file, sheet_name=sheet)
                    
                    for col in df.columns:
                        clean_col = df[col].astype(str).str.strip().str.upper()
                        match = df[clean_col == user_id]
                        
                        if not match.empty:
                            sheet_data = match.iloc[0].to_dict()
                            merged_profile.update(sheet_data)
                            break 
                
                if merged_profile:
                    target_row_data = merged_profile
                    break
                    
            except Exception as e: 
                print(f"[Gateway] Sheet scan skip: {e}")
                continue

        if not target_row_data:
            return {"message": f"I couldn't find any records for ID {user_id} in the {domain} domain."}

        context_msg = (
            f"MERGED DATASET: {json.dumps(target_row_data)}\n"
            f"USER_ASK: {msg}"
        )
        
        instruction = (
            "You are a Universal Support Assistant handling multiple domains. "
            "1. Answer the user based ONLY on the provided MERGED DATASET. "
            "2. CRITICAL: If the user asks for a specific metric (e.g., February, Savings, Loan) and it is NOT explicitly in the data, do NOT guess or substitute a 'Total' value. "
            "3. Instead, politely say: 'I have your overall data, but I don't see a specific record for that yet.' "
            "4. Speak in warm, full sentences. DO NOT use JSON, underscores _, or brackets."
        )
        
        reply, provider = brain.think(context_msg, agent_role="assistant")
        
        clean_reply = str(reply).replace("_", " ").replace(":", " is").strip("` ")
        
        return {"message": clean_reply}
        
    except Exception as e:
        print(f"[Chat Error]: {str(e)}")
        return {"message": "I am currently offline for maintenance. Please try again later."}

if __name__ == "__main__":
    import uvicorn
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    uvicorn.run(app, host="127.0.0.1", port=8000, access_log=False, log_level="warning")