import os
import pandas as pd
import sqlite3
import random
from datetime import date
import calendar

def get_month_days(year, month, current_date):
    """Generates days for a month, marking Sundays as Holidays and future days as blank."""
    num_days = calendar.monthrange(year, month)[1]
    days = []
    for day in range(1, num_days + 1):
        d = date(year, month, day)
        col_name = d.strftime("%d-%b")
        
        if d.weekday() == 6: 
            status = 'Holiday'
        elif d > current_date:
            status = '' 
        else:
            status = 'P' if random.random() < 0.85 else 'A'
            
        days.append({'date_obj': d, 'col_name': col_name, 'status': status})
    return days

def create_multi_sheet_infrastructure():
    print("[Seeder] Initializing Wide-Dynamic Enterprise Infrastructure...")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)

    print("   -> Forging Universal Request Database (EDU_leave_requests.db)...")
    edu_db_path = os.path.join(data_dir, "EDU_leave_requests.db")
    
    if os.path.exists(edu_db_path): 
        try: os.remove(edu_db_path)
        except: pass
    
    conn = sqlite3.connect(edu_db_path)
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
    departments = ["Civil", "Mechanical", "Computer_Science", "AI_DS", "ECE"]
    
    demo_date = date(2026, 5, 8) 
    
    months = [
        {"name": "1_February", "year": 2026, "month": 2},
        {"name": "2_March", "year": 2026, "month": 3},
        {"name": "3_April", "year": 2026, "month": 4},
        {"name": "4_May", "year": 2026, "month": 5}
    ]
    
    student_counter = 16 
    
    for dept in departments:
        file_path = os.path.join(data_dir, f"EDU_Attendance_{dept}.xlsx")
        writer = pd.ExcelWriter(file_path, engine='openpyxl')
        
        summary_data = []
        students = []
        
        for _ in range(5):
            student_id = f"2026EDU{student_counter:04d}"
            students.append({
                "Roll_Number": student_id,
                "Student_Name": f"Student_{student_counter}",
                "Department": dept,
                "Contact_Number": f"919876543{student_counter:03d}"
            })
            student_counter += 1

        for m in months:
            month_days = get_month_days(m['year'], m['month'], demo_date)
            month_sheet_data = []
            
            for i, student in enumerate(students):
                row = student.copy()
                working_days = 0
                attended = 0
                
                is_struggling = (i % 4 == 0)
                
                for day in month_days:
                    status = day['status']
                    if status in ['P', 'A']:
                        status = 'P' if random.random() < (0.45 if is_struggling else 0.90) else 'A'
                    
                    row[day['col_name']] = status
                    
                    if status not in ['Holiday', '', None]:
                        working_days += 1
                        if status == 'P':
                            attended += 1
                
                row['Monthly_Working_Days'] = working_days
                row['Monthly_Attended'] = attended
                row['Monthly_Percentage'] = round((attended / working_days * 100), 2) if working_days > 0 else 0
                
                month_sheet_data.append(row)
                
                if len(summary_data) <= i:
                    summary_data.append(student.copy())
                    summary_data[i]['Total_Working_Days'] = 0
                    summary_data[i]['Total_Attended'] = 0
                
                summary_data[i]['Total_Working_Days'] += working_days
                summary_data[i]['Total_Attended'] += attended
            
            df_month = pd.DataFrame(month_sheet_data)
            df_month.to_excel(writer, sheet_name=m['name'], index=False)
        
        for row in summary_data:
            t_working = row['Total_Working_Days']
            t_attended = row['Total_Attended']
            row['Semester_Percentage'] = round((t_attended / t_working * 100), 2) if t_working > 0 else 0
            row['Academic_Standing'] = "Pending Audit"

        df_summary = pd.DataFrame(summary_data)
        df_summary.to_excel(writer, sheet_name="Semester_Summary", index=False)
        writer.close()

    print("[Seeder] Infrastructure synchronized with Gateway. System ready for missions.")

if __name__ == "__main__":
    create_multi_sheet_infrastructure()