import os
import json
import re
import ast
import glob
import pandas as pd
import sqlite3
from datetime import datetime

class LegacyBridge:
    """
    The Nervous System of the Middleware.
    Handles 'Intent Funneling' to reduce token bloat and parses 
    the final JSON patches to send to the Actuator.
    """
    def __init__(self):
        pass

    def get_schema_headers(self, file_path):
        """Extracts ONLY the column names. Zero row data. Extremely token efficient."""
        safe_name = os.path.basename(file_path)
        if not os.path.exists(file_path):
            return f"Error: File {safe_name} not found."
            
        try:
            headers_info = {}
            
            if file_path.endswith('.db'):
                conn = sqlite3.connect(file_path, timeout=10)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                for t in tables:
                    table_name = t[0]
                    if table_name == 'sqlite_sequence': continue
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    headers_info[table_name] = [col[1] for col in cursor.fetchall()]
                conn.close()
                
            elif file_path.endswith('.xlsx'):
                sheets = pd.read_excel(file_path, sheet_name=None)
                for sheet_name, df in sheets.items():
                    headers_info[sheet_name] = df.columns.tolist()
                    
            return json.dumps(headers_info, indent=2)
            
        except Exception as e:
            return f"Error extracting headers from {safe_name}: {str(e)}"

    def get_funneled_schema(self, file_path, required_columns, ghost_mode=True, user_request=None):
        """
        THE DYNAMIC PAYLOAD UPGRADE (CROSS-SHEET COMPLIANT)
        ghost_mode=True: Strips all raw row data, returns only vocabulary.
        ghost_mode=False: Returns actual data rows.
        user_request: Used to trigger Row-Level Filtering for Flow 3.
        """
        safe_name = os.path.basename(file_path)
        mode_str = "Ghost Mode (Vocab Only)" if ghost_mode else "Audit Mode (Row Data Active)"
        print(f"[Bridge] Extracting Token-Optimized Payload [{mode_str}] for {safe_name}...")
        
        if not os.path.exists(file_path):
            return f"Error: File {safe_name} not found."
            
        target_entity_id = None
        target_months = set()
        
        if user_request:
            user_request_str = str(user_request)
            match = re.search(r'TARGET_ENTITY_ID\s*=\s*([A-Za-z0-9_-]+)', user_request_str)
            if not match: 
                match = re.search(r"['\"]target_entity_id['\"]\s*:\s*['\"]([^'\"]+)['\"]", user_request_str, re.IGNORECASE)
            
            if match:
                target_entity_id = match.group(1).strip()
            elif len(user_request_str) < 50: 
                target_entity_id = user_request_str.strip()
                
            if target_entity_id:
                print(f"[Bridge] Contextual Blinders Active: Filtering exclusively for Entity '{target_entity_id}'")
                dates = re.findall(r'\d{2}-([A-Za-z]{3})', str(user_request))
                for d in dates:
                    target_months.add(d.lower())
                
                if not target_months:
                    target_months.add(datetime.now().strftime("%b").lower())

        try:
            funneled_payload = {}
            
            if file_path.endswith('.db'):
                conn = sqlite3.connect(file_path, timeout=10)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                
                for t in tables:
                    table_name = t[0]
                    if table_name == 'sqlite_sequence': continue
                    
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    all_cols = [col[1] for col in cursor.fetchall()]
                    
                    if "ALL" in required_columns:
                        cols_to_keep = all_cols
                    else:
                        cols_to_keep = [c for c in all_cols if c in required_columns]
                        
                    if not cols_to_keep: continue
                    
                    data_rows = []
                    if target_entity_id:
                        id_col = next((c for c in all_cols if 'id' in c.lower()), all_cols[0])
                        query = f"SELECT {','.join(cols_to_keep)} FROM {table_name} WHERE {id_col} = ? ORDER BY timestamp DESC LIMIT 1"
                        cursor.execute(query, (target_entity_id,))
                        rows = cursor.fetchall()
                        data_rows = [dict(row) for row in rows]
                    elif not ghost_mode:
                        query = f"SELECT {','.join(cols_to_keep)} FROM {table_name} LIMIT 10"
                        cursor.execute(query)
                        rows = cursor.fetchall()
                        data_rows = [dict(row) for row in rows]
                        
                    funneled_payload[table_name] = {
                        "schema": cols_to_keep,
                        "data_sample": data_rows
                    }
                conn.close()

            elif file_path.endswith('.xlsx'):
                sheets = pd.read_excel(file_path, sheet_name=None)
                
                for sheet_name, df in sheets.items():
                    if target_entity_id:
                        sheet_lower = sheet_name.lower()
                        is_summary = any(kw in sheet_lower for kw in ["summary", "master", "total", "main"])
                        is_target_month = any(month in sheet_lower for month in target_months)
                        
                        if not is_summary and target_months and not is_target_month:
                            continue 
                            
                    if "ALL" in required_columns:
                        cols_to_keep = df.columns.tolist()
                    else:
                        cols_to_keep = [col for col in df.columns if col in required_columns]
                        if "ALL_TIME_SERIES" in required_columns:
                            date_cols = [c for c in df.columns if re.match(r'^\d{2}-[A-Za-z]{3}$', str(c))]
                            cols_to_keep.extend(date_cols)
                        cols_to_keep = list(dict.fromkeys(cols_to_keep))
                    
                    if not cols_to_keep:
                        continue 
                        
                    schema_types = {col: str(df[col].dtype) for col in cols_to_keep}
                    subset_df = df[cols_to_keep].dropna(how='all')
                    
                    if target_entity_id:
                        mask = subset_df.astype(str).apply(lambda x: x.str.contains(str(target_entity_id), case=False, na=False)).any(axis=1)
                        subset_df = subset_df[mask]

                    include_row_data = (not ghost_mode) or (target_entity_id is not None)

                    data_rows = []
                    if include_row_data:
                        for _, row in subset_df.iterrows():
                            clean_row = {}
                            for col in cols_to_keep:
                                val = row[col]
                                if pd.isna(val) or val == "": continue
                                clean_row[col] = val
                            if clean_row: data_rows.append(clean_row)

                    unique_values = set()
                    if ghost_mode and not target_entity_id:
                        for col in cols_to_keep:
                            col_str = str(col)
                            if re.match(r'^\d{2}-[A-Za-z]{3}$', col_str) or any(keyword in col_str.lower() for keyword in ['status', 'standing', 'grade', 'type']):
                                valid_vals = df[col].dropna().astype(str).unique()
                                unique_values.update([v.strip() for v in valid_vals if v.strip() != "" and v.strip() != "nan"])

                    payload_chunk = {"schema": schema_types}
                    if unique_values: payload_chunk["unique_categorical_vocabulary"] = list(unique_values)
                    if data_rows: payload_chunk["data_sample"] = data_rows
                    
                    funneled_payload[sheet_name] = payload_chunk

            elif file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
                cols_to_keep = df.columns.tolist() if "ALL" in required_columns else [c for c in df.columns if c in required_columns]
                
                if target_entity_id:
                    mask = df[cols_to_keep].astype(str).apply(
                        lambda x: x.str.contains(str(target_entity_id), case=False, na=False)
                    ).any(axis=1)
                    df = df[mask]
                
                data_rows = []
                for _, row in df[cols_to_keep].iterrows():
                    clean_row = {col: val for col, val in row.items() if pd.notna(val) and val != ""}
                    if clean_row: data_rows.append(clean_row)
                
                funneled_payload["CSV_Data"] = {"schema": cols_to_keep, "data_sample": data_rows}

            return json.dumps(funneled_payload, indent=2)
            
        except Exception as e:
            return f"Error generating payload: {str(e)}"

    def get_global_metric_summary(self, current_file, target_id):
        """Agnostic Summary Recovery: Fetches only the summary row for the target ID."""
        try:
            folder = os.path.dirname(current_file) or '.'
            summary_files = [f for f in glob.glob(os.path.join(folder, "*Summary*")) if f.endswith(('.csv', '.xlsx'))]
            if summary_files:
                return self.get_funneled_schema(summary_files[0], ["ALL"], ghost_mode=False, user_request=target_id)
        except Exception: 
            pass
        return "Global Summary Context: N/A"

    def _sanitize_json_string(self, raw_str):
        """Catches unescaped newlines/tabs and MISSING COMMAS."""
        clean_str = re.sub(r'(?<!\\)\n', ' ', raw_str)
        clean_str = re.sub(r'(?<!\\)\r', ' ', clean_str)
        clean_str = re.sub(r'(?<!\\)\t', ' ', clean_str)
        
        clean_str = re.sub(r'\}\s*\{', '}, {', clean_str)
        clean_str = re.sub(r'\]\s*\[', '], [', clean_str)
        
        clean_str = re.sub(r',\s*\}', '}', clean_str)
        clean_str = re.sub(r',\s*\]', ']', clean_str)
        
        return clean_str

    def parse_architect_response(self, raw_llm_response):
        """
        Separates the AI's plain-english 'Pseudocode Plan' from the strict 'JSON Patch'.
        Includes the ultimate LLM formatting sanitizer.
        """
        if not raw_llm_response or raw_llm_response == "Offline":
            return None, "API was offline."

        json_match = re.search(r'```json\n(.*?)\n```', raw_llm_response, re.DOTALL | re.IGNORECASE)
        
        if json_match:
            clean_str = json_match.group(1).strip()
        else:
            start_idx = raw_llm_response.find('{')
            end_idx = raw_llm_response.rfind('}')
            
            if start_idx != -1 and end_idx != -1:
                clean_str = raw_llm_response[start_idx:end_idx+1]
            else:
                return None, "No JSON object found in the response."

        try:
            json_patch = json.loads(clean_str)
            return json_patch, None
        except json.JSONDecodeError as initial_err:
            try:
                sanitized_str = self._sanitize_json_string(clean_str)
                json_patch = json.loads(sanitized_str)
                return json_patch, None
            except json.JSONDecodeError:
                try:
                    json_patch = ast.literal_eval(clean_str)
                    if isinstance(json_patch, dict):
                        return json_patch, None
                except:
                    pass
                return None, f"JSON Parsing Error: {str(initial_err)}"

    def validate_and_route(self, json_patch, actuator, file_path):
        """
        Takes the parsed JSON patch and hands it securely to the Actuator.
        """
        if not json_patch:
            print("[Bridge] Validation Failed: Empty JSON patch.")
            return False
            
        success, message = actuator.apply_json_patch(file_path, json_patch)
        return success