import os
import pandas as pd
import sqlite3
import random
from datetime import date
import calendar

def get_month_days(year, month, current_date):
    """Generates days for a month, marking maintenance windows and future days."""
    num_days = calendar.monthrange(year, month)[1]
    days = []
    for day in range(1, num_days + 1):
        d = date(year, month, day)
        col_name = d.strftime("%d-%b")
        
        if d > current_date:
            status = '' 
        else:
            status = 'OK' if random.random() < 0.95 else 'Offline'
            
        days.append({'date_obj': d, 'col_name': col_name, 'status': status})
    return days

def create_multi_sheet_infrastructure():
    print("[Seeder] Initializing IT Server SLA Enterprise Infrastructure...")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)

    print("   -> Forging Universal Request Database (IT_maintenance_requests.db)...")
    it_db_path = os.path.join(data_dir, "IT_maintenance_requests.db")
    
    if os.path.exists(it_db_path): 
        try: os.remove(it_db_path)
        except: pass

    conn = sqlite3.connect(it_db_path)
    conn.execute('''CREATE TABLE universal_requests (
            request_id INTEGER PRIMARY KEY AUTOINCREMENT, 
            user_id VARCHAR(50), 
            domain VARCHAR(50),
            department VARCHAR(50),
            request_reason TEXT,
            metadata TEXT,
            status VARCHAR(20) DEFAULT 'Pending Audit',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')
    conn.commit()
    conn.close()

    print("   -> Generating Multi-Sheet Legacy Excel Nodes...")
    clusters = ["Database", "Compute", "Networking", "Storage", "Security"]
    
    demo_date = date(2026, 5, 8) 
    months = [
        {"name": "1_February", "year": 2026, "month": 2},
        {"name": "2_March", "year": 2026, "month": 3},
        {"name": "3_April", "year": 2026, "month": 4},
        {"name": "4_May", "year": 2026, "month": 5}
    ]
    
    server_counter = 1001 
    
    for cluster in clusters:
        file_path = os.path.join(data_dir, f"IT_Uptime_{cluster}.xlsx")
        writer = pd.ExcelWriter(file_path, engine='openpyxl')
        
        summary_data = []
        servers = []
        
        for _ in range(5):
            server_id = f"SRV{server_counter}"
            servers.append({
                "Server_ID": server_id,
                "Hostname": f"{cluster.lower()}-node-{server_counter}",
                "Cluster_Group": cluster,
                "IP_Address": f"192.168.1.{random.randint(10, 250)}"
            })
            server_counter += 1

        for m in months:
            month_days = get_month_days(m['year'], m['month'], demo_date)
            month_sheet_data = []
            
            for i, srv in enumerate(servers):
                row = srv.copy()
                expected_pings = 0
                success_count = 0
                
                is_failing = (i % 4 == 0)
                
                for day in month_days:
                    status = day['status']
                    if status in ['OK', 'Offline']:
                        status = 'OK' if random.random() < (0.80 if is_failing else 0.99) else 'Offline'
                    
                    row[day['col_name']] = status
                    
                    if status not in ['', None]:
                        expected_pings += 1
                        if status == 'OK':
                            success_count += 1
                
                row['Monthly_Expected_Pings'] = expected_pings
                row['Monthly_Success_Count'] = success_count
                row['Monthly_Uptime_Percentage'] = round((success_count / expected_pings * 100), 2) if expected_pings > 0 else 0
                
                month_sheet_data.append(row)
                
                if len(summary_data) <= i:
                    summary_data.append(srv.copy())
                    summary_data[i]['Total_Expected_Pings'] = 0
                    summary_data[i]['Total_Success_Count'] = 0
                
                summary_data[i]['Total_Expected_Pings'] += expected_pings
                summary_data[i]['Total_Success_Count'] += success_count
            
            df_month = pd.DataFrame(month_sheet_data)
            df_month.to_excel(writer, sheet_name=m['name'], index=False)
        
        for row in summary_data:
            t_expected = row['Total_Expected_Pings']
            t_success = row['Total_Success_Count']
            row['Quarterly_Uptime_Percentage'] = round((t_success / t_expected * 100), 2) if t_expected > 0 else 0
            row['SLA_Status'] = "Pending Audit"

        df_summary = pd.DataFrame(summary_data)
        df_summary.to_excel(writer, sheet_name="Quarterly_Summary", index=False)
        writer.close()

    print("[Seeder] Infrastructure synchronized. IT SLA nodes ready.")

if __name__ == "__main__":
    create_multi_sheet_infrastructure()