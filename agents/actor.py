import os
import json
import glob
import time
import requests
import pandas as pd
import sqlite3
import re

class SandboxActuator:
    """The Deterministic Execution Engine. Safely updates Excel and SQLite DBs."""
    def __init__(self):
        pass

    def _send_system_alert(self, message):
        """Silently pings the Admin via Telegram without crashing the local thread."""
        bot_token = os.getenv("ADMIN_BOT_TOKEN")
        chat_id = os.getenv("ADMIN_CHAT_ID")
        if bot_token and chat_id:
            try:
                tg_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                requests.post(tg_url, json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"}, timeout=10)
            except Exception as e:
                print(f" [Actuator] Could not send Telegram alert: {e}")

    def apply_json_patch(self, file_path, json_patch_str):
        safe_name = os.path.basename(file_path)
        print(f" [Actuator] Analyzing JSON instructions for {safe_name}...")

        # Enforce type-safety to prevent NAType and null value exceptions during processing
        def safe_float(val):
            """Sanitizes dirty, empty, or pd.NA Excel cells into safe floats for math."""
            if pd.isna(val) or str(val).strip() == "":
                return 0.0
            try:
                return float(val)
            except (ValueError, TypeError):
                return 0.0

        try:
            if isinstance(json_patch_str, str):
                clean_json = json_patch_str.replace("```json", "").replace("```", "").strip()
                patch_data = json.loads(clean_json)
            else:
                patch_data = json_patch_str

            # Process asynchronous SQL database updates
            if "db_updates" in patch_data and isinstance(patch_data["db_updates"], list) and len(patch_data["db_updates"]) > 0:
                print(f" [Actuator] Database update requested. Syncing external ledger...")
                domain_prefix = safe_name.split('_')[0] if '_' in safe_name else 'System'
                watch_dir = os.path.dirname(file_path)
            
                db_files = glob.glob(os.path.join(watch_dir, f"{domain_prefix}_*.db"))
                request_dbs = [f for f in db_files if 'request' in os.path.basename(f).lower()]
                target_db = request_dbs[0] if request_dbs else (db_files[0] if db_files else None)

                if target_db and os.path.exists(target_db):
                    try:
                        conn = sqlite3.connect(target_db, timeout=10)
                        cursor = conn.cursor()
                        for update in patch_data["db_updates"]:
                            table = update.get("table", "universal_requests")
                            target_id = update.get("target_entity_id")
                            update_data = update.get("update_data", {})
                            
                            if target_id and "status" in update_data:
                                new_status = update_data["status"]
                                cursor.execute(f"SELECT request_id FROM {table} WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1", (target_id,))
                                row = cursor.fetchone()
                                if row:
                                    cursor.execute(f"UPDATE {table} SET status = ? WHERE request_id = ?", (new_status, row[0]))
                                else:
                                    cursor.execute(f"INSERT INTO {table} (user_id, status) VALUES (?, ?)", (target_id, new_status))
                                print(f" [Actuator] DB Ledger: Synchronized request status for {target_id}.")
                            
                            elif "data" in update:
                                data = update["data"]
                                e_id = data.get("Entity_ID")
                                status = data.get("Status")
                                reason = data.get("Reason", "")
                                
                                if e_id and status:
                                    cursor.execute(f"SELECT request_id FROM {table} WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1", (e_id,))
                                    row = cursor.fetchone()
                                    if row:
                                        cursor.execute(f"UPDATE {table} SET status = ? WHERE request_id = ?", (status, row[0]))
                                    else:
                                        cursor.execute(f"INSERT INTO {table} (user_id, request_reason, status) VALUES (?, ?, ?)", (e_id, reason, status))
                            else:
                                m_col = update.get("match_column")
                                m_val = update.get("match_value")
                                u_col = update.get("update_column")
                                n_val = update.get("new_value")
                                
                                if all([table, m_col, m_val, u_col, n_val]):
                                    query = f"UPDATE {table} SET {u_col} = ? WHERE {m_col} = ?"
                                    cursor.execute(query, (str(n_val), str(m_val)))
                        
                        conn.commit()
                        conn.close()
                    except Exception as e:
                        print(f" [Actuator] SQL Update Failed: {e}")
                else:
                    print(f" [Actuator] No matching database found for domain {domain_prefix}.")

            # Process synchronous Excel ledger updates
            updates_made = 0
            has_macro = False
            has_micro = False
            
            if file_path.endswith('.xlsx'):
                has_macro = "excel_updates" in patch_data and isinstance(patch_data["excel_updates"], list) and len(patch_data["excel_updates"]) > 0
                has_micro = "excel_micro_patches" in patch_data and isinstance(patch_data["excel_micro_patches"], list) and len(patch_data["excel_micro_patches"]) > 0

                if has_macro or has_micro:
                    sheets = pd.read_excel(file_path, sheet_name=None)
                    
                    # Process asynchronous micro-patches for individual ledger rows
                    if has_micro:
                        for patch in patch_data["excel_micro_patches"]:
                            # Extract and format the targeted dictionary payload
                            target_id = str(patch.get("target_entity_id", "")).replace('.0', '')
                            updates = patch.get("updates", {})
                            
                            if not target_id or not isinstance(updates, dict):
                                continue
                                
                            for update_col, new_val in updates.items():
                                target_sheet = None
                                for s_name, s_df in sheets.items():
                                    if update_col in s_df.columns:
                                        target_sheet = s_name
                                        break
                                
                                if target_sheet:
                                    df = sheets[target_sheet]
                                    actual_cols = df.columns.tolist()
                                    possible_id_cols = [c for c in actual_cols if any(x in str(c).lower() for x in ['id', 'roll', 'number', 'key', 'code'])]
                                    m_col = possible_id_cols[0] if possible_id_cols else actual_cols[0]
                                    
                                    df[m_col] = df[m_col].astype(str).str.replace('.0', '', regex=False)
                                    mask = df[m_col] == target_id
                                    
                                    if mask.any():
                                        df[update_col] = df[update_col].astype(object)
                                        df.loc[mask, update_col] = new_val
                                        updates_made += mask.sum()
                                        print(f" [Actuator|Flow 3] Micro-Patch Success: Assigned '{new_val}' to '{update_col}' for '{target_id}' in {target_sheet}.")

                    # Process synchronous macro-computations across entire network sheets
                    if has_macro:
                        for update in patch_data["excel_updates"]:
                            compute = update.get("compute_logic", {})
                            operation = compute.get("operation", "")
                            
                            if operation == "MACRO_RECALCULATE_ALL":
                                targets = compute.get("target_values", [])
                                
                                # Universal Domain-Agnostic Safe States
                                # Enables the middleware to bypass healthy ledger entries dynamically
                                universal_safe_states = [
                                    # General / Web
                                    'Approved', 'Resolved', 'Active', 'Clear', 'Success', 'OK',
                                    # Education (EDU)
                                    'Eligible', 'Passed', 'Excused', 'Verified', 'P', 'Present', "L", 'Leave',
                                    # Finance & Legal (FIN)
                                    'Compliant', 'Settled', 'Authorized', 'Current', 'Good Standing',
                                    # Healthcare (For future scaling)
                                    'Discharged', 'Healthy', 'Negative', 'Cleared',
                                    # Logistics (For future scaling)
                                    'Delivered', 'In Transit', 'Received'
                                ]
                                
                                targets.extend(universal_safe_states)
                                
                                print(f" [Compute Engine] MACRO_RECALCULATE_ALL initiated. Success targets: {targets}")
                                
                                def get_col(cols, keywords):
                                    return next((c for c in cols if any(k in str(c).lower() for k in keywords)), None)
                                
                                id_kw = ['id', 'roll', 'number', 'key', 'code', 'identifier']
                                wd_kw = ['working', 'total_days', 'expected', 'due', 'capacity', 'required']
                                att_kw = ['attended', 'count', 'paid', 'completed', 'score', 'actual']
                                perc_kw = ['percentage', 'rate', 'ratio', 'percent']
                                stat_kw = ['standing', 'status', 'grade', 'category', 'state', 'condition', 'tier']
                                
                                intermediate_sheets = []
                                master_sheet = None
                                
                                for s_name, s_df in sheets.items():
                                    date_cols = [c for c in s_df.columns if re.match(r'^\d{2}-[A-Za-z]{3}$', str(c))]
                                    if date_cols:
                                        intermediate_sheets.append((s_name, date_cols))
                                    else:
                                        master_sheet = s_name
                                
                                if not master_sheet:
                                    master_sheet = list(sheets.keys())[-1]
                                
                                if not intermediate_sheets:
                                    print(" [Compute Engine] No time-series sheets detected. Skipping math to protect static domain data.")
                                    break
                                    
                                for s_name, date_cols in intermediate_sheets:
                                    i_df = sheets[s_name]
                                    wd_col = get_col(i_df.columns, wd_kw)
                                    att_col = get_col(i_df.columns, att_kw)
                                    perc_col = get_col(i_df.columns, perc_kw)
                                    
                                    valid_entries = i_df[date_cols].fillna("")
                                    
                                    def is_working(val):
                                        v = str(val).strip().lower()
                                        
                                        # 1. Ignore empty/future cells (Denominator shrinks dynamically)
                                        if not v or v in ["", "nan", "null", "none"]: 
                                            return False
                                            
                                        # 2. Enforce strict string matching
                                        # Prevents substring conflicts (e.g., 'off' triggering on 'offline').
                                        universal_skip_days = ['holiday', 'off', 'sunday', 'leave', 'exempt', 'n/a']
                                        if v in universal_skip_days: 
                                            return False
                                            
                                        return True
                            
                                    if hasattr(valid_entries, 'map'):
                                        working_days = valid_entries.map(is_working).sum(axis=1)
                                        target_counts = valid_entries.map(lambda x: str(x).strip() in targets).sum(axis=1)
                                    else:
                                        working_days = valid_entries.applymap(is_working).sum(axis=1)
                                        target_counts = valid_entries.applymap(lambda x: str(x).strip() in targets).sum(axis=1)
                                    
                                    if wd_col: i_df[wd_col] = working_days
                                    if att_col: i_df[att_col] = target_counts
                                    if perc_col and wd_col and att_col:
                                        perc = (i_df[att_col] / i_df[wd_col].replace(0, pd.NA)) * 100
                                        i_df[perc_col] = pd.to_numeric(perc, errors='coerce').fillna(0.0).round(2)
                                    
                                    sheets[s_name] = i_df
                                    updates_made += len(i_df)
                                    
                                m_df = sheets[master_sheet]
                                m_id_col = get_col(m_df.columns, id_kw) or m_df.columns[0]
                                m_wd_col = get_col(m_df.columns, wd_kw)
                                m_att_col = get_col(m_df.columns, att_kw)
                                m_perc_col = get_col(m_df.columns, perc_kw)
                                m_stat_col = get_col(m_df.columns, stat_kw)
                                
                                for idx in m_df.index:
                                    row_id = str(m_df.loc[idx, m_id_col])
                                    total_wd, total_att = 0.0, 0.0
                                    
                                    for s_name, _ in intermediate_sheets:
                                        i_df = sheets[s_name]
                                        i_id_col = get_col(i_df.columns, id_kw) or i_df.columns[0]
                                        i_wd_col = get_col(i_df.columns, wd_kw)
                                        i_att_col = get_col(i_df.columns, att_kw)
                                        
                                        match_row = i_df[i_df[i_id_col].astype(str) == row_id]
                                        if not match_row.empty:
                                            if i_wd_col: total_wd += safe_float(match_row[i_wd_col].values[0])
                                            if i_att_col: total_att += safe_float(match_row[i_att_col].values[0])
                                             
                                    if m_wd_col: m_df.loc[idx, m_wd_col] = total_wd
                                    if m_att_col: m_df.loc[idx, m_att_col] = total_att
                                    if m_perc_col and m_wd_col and m_att_col:
                                        if total_wd > 0:
                                            m_df.loc[idx, m_perc_col] = round((total_att / total_wd) * 100, 2)
                                        else:
                                            m_df.loc[idx, m_perc_col] = 0.0
                                            
                                    
                                    if m_stat_col:
                                        m_df.loc[idx, m_stat_col] = "Pending Audit"
                                        
                                sheets[master_sheet] = m_df
                                updates_made += len(m_df)
                                print(" [Compute Engine] MACRO_RECALCULATE_ALL completed. Worksheets fully synchronized.")
                                break 

                            
                            sheet_name = update.get("sheet", "")
                            match_col = update.get("match_column", "")
                            match_val = update.get("match_value", "")
                            update_col = update.get("update_column", "")
                            new_val = update.get("new_value", "")
                            
                            # Mathematical Validation Layer (Interceptor)
                            pass_condition = update.get("pass_condition")
                            if pass_condition:
                                try:
                                    safe_math_string = re.sub(r'[^0-9\.\>\<\=\! ]', '', str(pass_condition))
                                    if safe_math_string.strip():
                                        is_passing = eval(safe_math_string)
                                        
                                        status_if_pass = update.get("status_if_pass", new_val)
                                        status_if_fail = update.get("status_if_fail", new_val)
                                        
                                        corrected_val = status_if_pass if is_passing else status_if_fail
                                        
                                        if corrected_val != new_val:
                                            print(f" [Math Shield] Caught LLM Hallucination! '{safe_math_string}' evaluated to {is_passing}. Auto-correcting '{new_val}' to '{corrected_val}'.")
                                            new_val = corrected_val
                                            
                                            # Route asynchronous notification payload
                                            if not is_passing: 
                                                safe_id = str(match_val).replace('.0', '')
                                                llm_alert = update.get("llm_native_alert")
                                                if llm_alert:
                                                    print(f" [Router] Recovered LLM-generated alert for {safe_id}. Routing to Telegram...")
                                                    self._send_system_alert(llm_alert)
                                except Exception as e:
                                    print(f" [Math Shield] Could not evaluate dynamic string '{pass_condition}': {e}")
                           

                            if not sheet_name or sheet_name not in sheets: 
                                master_candidate = None
                                for s_name, s_df in sheets.items():
                                    if not any(re.match(r'^\d{2}-[A-Za-z]{3}$', str(c)) for c in s_df.columns):
                                        master_candidate = s_name
                                        break
                                sheet_name = master_candidate if master_candidate else list(sheets.keys())[-1]
                             
                            df = sheets[sheet_name]
                            actual_cols = df.columns.tolist()
                           
                            if match_col not in actual_cols:
                                possible_id_cols = [c for c in actual_cols if any(x in c.lower() for x in ['id', 'roll', 'number', 'key', 'code'])]
                                match_col = possible_id_cols[0] if possible_id_cols else actual_cols[0]
                                    
                            if update_col not in actual_cols:
                                fallback_cols = [c for c in actual_cols if any(x in c.lower() for x in ['status', 'total', 'percentage', 'standing', 'state', 'condition'])]
                                update_col = fallback_cols[0] if fallback_cols else actual_cols[-1]

                            if match_val == "ALL_ROWS":
                                mask = pd.Series(True, index=df.index)
                            else:
                                df[match_col] = df[match_col].astype(str).str.replace('.0', '', regex=False)
                                safe_match_val = str(match_val).replace('.0', '')
                                mask = df[match_col] == safe_match_val

                            if not mask.any(): 
                                continue

                            if "compute_logic" in update:
                                df[update_col] = df[update_col].astype(object)

                                if operation == "COUNT_SPECIFIC_VALUES":
                                    cols_to_scan = compute.get("columns_to_scan", [])
                                    targets = compute.get("target_values", [])
                                    
                                    if "ALL_TIME_SERIES" in cols_to_scan:
                                        valid_cols = [c for c in actual_cols if re.match(r'^\d{2}-[A-Za-z]{3}$', str(c))]
                                    else:
                                        valid_cols = [c for c in cols_to_scan if c in actual_cols]
                                    
                                    computed_series = df[valid_cols].isin(targets).sum(axis=1)
                                    df.loc[mask, update_col] = computed_series[mask]
                                    print(f" [Compute Engine] Batch-Counted '{targets}' for {mask.sum()} rows in {sheet_name}.")
                                    updates_made += mask.sum()

                                elif operation == "CALCULATE_PERCENTAGE":
                                    num_col = compute.get("numerator_column")
                                    den_col = compute.get("denominator_column")
                                    
                                    if num_col in actual_cols and den_col in actual_cols:
                                        num = pd.to_numeric(df.loc[mask, num_col], errors='coerce').fillna(0)
                                        den = pd.to_numeric(df.loc[mask, den_col], errors='coerce').fillna(0)
                                        
                                        perc = (num / den.replace(0, pd.NA)) * 100
                                        df.loc[mask, update_col] = pd.to_numeric(perc, errors='coerce').fillna(0.0).round(2)
                                        print(f" [Compute Engine] Calculated Percentages for {mask.sum()} rows in {sheet_name}.")
                                        updates_made += mask.sum()

                                elif operation == "SUM_ACROSS_SHEETS":
                                    target_sheets = compute.get("sheets_to_scan", [])
                                    col_to_sum = compute.get("column_to_sum")
                                    
                                    for idx in df[mask].index:
                                        row_id = str(df.loc[idx, match_col])
                                        total_sum = 0.0
                                        
                                        for t_sheet in target_sheets:
                                            if t_sheet in sheets and col_to_sum in sheets[t_sheet].columns:
                                                t_df = sheets[t_sheet]
                                                t_mask = t_df[match_col].astype(str) == row_id
                                                if t_mask.any():
                                                    val = t_df.loc[t_mask, col_to_sum].values[0]
                                                    total_sum += safe_float(val)
                                                    
                                        df.loc[idx, update_col] = total_sum
                                     
                                    print(f" [Compute Engine] Cross-sheet summation complete for '{update_col}'.")
                                    updates_made += mask.sum()

                            else:
                                df[update_col] = df[update_col].astype(object)
                                df.loc[mask, update_col] = new_val
                                updates_made += mask.sum()
                                if match_val != "ALL_ROWS":
                                    print(f" [Actuator] Surgery successful: Updated '{update_col}' for '{safe_match_val}' to '{new_val}'.")

                            sheets[sheet_name] = df

                # System Failsafe and Temporal State Persistence
                if updates_made > 0:
                    print(f" [Actuator] Attempting to commit {updates_made} updates to {safe_name}...")
                    
                    # Capture the original timestamps before saving
                    try:
                        original_atime = os.path.getatime(file_path)
                        original_mtime = os.path.getmtime(file_path)
                    except:
                        original_atime, original_mtime = None, None
                    
                    saved_successfully = False
                    try:
                        # Attempt 1: The standard save
                        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                            for s_name, df_out in sheets.items():
                                df_out.to_excel(writer, sheet_name=s_name, index=False)
                        saved_successfully = True
                    except PermissionError:
                        print(f" [Actuator] Excel file locked. Pinging admin via Telegram to close it...")
                        alert_msg = f" <b>System Paused</b>\n\nMathematical updates calculated, but the file <b>{safe_name}</b> is currently locked by the host OS.\n\nPlease close the Excel file within the next 15 seconds to permit secure data synchronization."
                        self._send_system_alert(alert_msg)
                        
                        # Grace Period: Wait for the user to close it
                        time.sleep(15)
                        
                        # Attempt 2: The final try
                        try:
                            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                                for s_name, df_out in sheets.items():
                                    df_out.to_excel(writer, sheet_name=s_name, index=False)
                            saved_successfully = True
                        except PermissionError:
                            print(" [Actuator] FATAL: File remains locked after warning. Aborting save to prevent system crash.")
                            fail_msg = f" <b>Save Aborted</b>\n\nThe file <b>{safe_name}</b> was still locked. Mathematical updates were discarded to prevent a system crash. Please close the file and re-run the request."
                            self._send_system_alert(fail_msg)
                            return False, "PermissionError: File locked by user."

                    if saved_successfully:
                        # Revert file modification timestamps to prevent triggering redundant initialization audits
                        if has_micro and not has_macro and original_mtime is not None:
                            try:
                                os.utime(file_path, (original_atime, original_mtime))
                                print(" [Actuator] Temporal state reverted. Redundant monitoring bypassed.")
                            except Exception as e:
                                print(f" [Actuator|Flow 3] Ghost write failed: {e}")

                        print(" [Actuator] Execution Successful. Legacy node synchronized.")
                        return True, "Success"
                else:
                    print(" [Actuator] AI determined no updates are mathematically required right now.")
                    return True, "No updates required"

            return True, "Success"

        except Exception as e:
            print(f" [Actuator] System Crash: {str(e)}")
            return False, f"Crash: {str(e)}"