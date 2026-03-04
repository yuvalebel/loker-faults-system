"""
Flask Faults System - High-Performance SPA
==========================================
Global caching strategy to eliminate remote DB latency
"""

from flask import Flask, render_template, request, jsonify
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================================================
# FLASK APP INITIALIZATION
# ============================================================================

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False  # Support Hebrew characters

# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================

POSTGRES_URL = os.getenv('DATABASE_URL', 'postgresql://team41:xBjwE7X6BjQjARSGTFcWOg7TJ0ZiQbyq@dpg-d615mm24d50c73eh9o0g-a.oregon-postgres.render.com/studentlocker')
SQLITE_URL = 'sqlite:///faults_system.db'

# Database engines
postgres_engine = create_engine(POSTGRES_URL, echo=False, pool_pre_ping=True, pool_recycle=3600)
sqlite_engine = create_engine(SQLITE_URL, echo=False, connect_args={'check_same_thread': False})

Base = declarative_base()

# ============================================================================
# GLOBAL CACHE - CRITICAL FOR PERFORMANCE
# ============================================================================

GLOBAL_STUDENTS_DF = None  # Will be loaded on startup

def load_students_to_cache():
    """Load all students from PostgreSQL into global cache (RAM)"""
    global GLOBAL_STUDENTS_DF
    
    print("🔄 Loading students from PostgreSQL into RAM cache...")
    
    try:
        query = """
            SELECT DISTINCT
                s.id,
                s."fname",
                s."lname",
                s."studentId",
                s.class,
                s."classNumber",
                s."parentPhone",
                s.email,
                sc.name as school_name
            FROM "Student" s
            LEFT JOIN "School" sc ON s."schoolId" = CAST(sc.id AS TEXT)
            ORDER BY s."fname", s."lname"
        """
        
        with postgres_engine.connect() as conn:
            GLOBAL_STUDENTS_DF = pd.read_sql(query, conn)
        
        print(f"✅ Loaded {len(GLOBAL_STUDENTS_DF)} students into RAM cache")
        return True
    except Exception as e:
        print(f"❌ Error loading students: {e}")
        # Fallback to simple query
        try:
            query = """
                SELECT DISTINCT
                    s.id,
                    s."fname",
                    s."lname",
                    s."studentId",
                    s.class,
                    s."classNumber",
                    s."parentPhone",
                    s.email,
                    NULL as school_name
                FROM "Student" s
                ORDER BY s."fname", s."lname"
            """
            with postgres_engine.connect() as conn:
                GLOBAL_STUDENTS_DF = pd.read_sql(query, conn)
            print(f"✅ Loaded {len(GLOBAL_STUDENTS_DF)} students (fallback mode)")
            return True
        except Exception as e2:
            print(f"❌ Fatal error loading students: {e2}")
            return False

# ============================================================================
# SCHOOL TO REGION MAPPING
# ============================================================================
# ============================================================================
# SCHOOL TO REGION MAPPING (Based on "חלוקת איזורים בתי ספר.xlsx")
# ============================================================================
SCHOOL_MAPPING = {
   'שש שנתי אשל הנשיא': 'South',
    'חטיבת הביניים סוסיא': 'South',
    'טכני חיל האוויר': 'South',
    'אמית ברוכין': 'Center',
    'אולפנת קרני שומרון': 'Center',
    'להבה': 'Center',
    'בעברית תיכון אוניברסי': 'Jerusalem',
    'אמי״ת בנים מודיעין': 'Jerusalem',
    'תבל רמות': 'Jerusalem',
    'ישיבת שעלבים': 'Jerusalem',
    'ענבר': 'Jerusalem',
    'נשמת התורה': 'Jerusalem',
    'מכון לב': 'Jerusalem',
    'אמי"ת מעלה אדומים': 'Jerusalem',
    'אולפנת שעלבים': 'Jerusalem',
    'אורט תעשייה אווירית': 'Center',
    'לאורו נלך': 'Center',
    'מיכה רייסר': 'Center',
    'צמרות': 'Center',
    'אולפנת צביה לוד': 'Center',
    'מקיף י׳ אלברט איינשטיי': 'Center',
    'אולפנת יבנה': 'Center',
    'אמירים (מקיף ה)': 'Center',
    "מקיף ז' רביבים": 'Center',
    'אמי"ת בנות מודיעין': 'Center',
    'נתיבות רבקה': 'Center',
    'סמינר שושנים': 'Center',
    'קינג סולומון הכפר הירו': 'Center',
    'פלך': 'Center',
    'בר אילן': 'Center',
    'שובו': 'Center',
    'בית ספר יצחק שמיר': 'Center',
    'מאיר שלו': 'Center',
    'אולפנת רמלה': 'Center',
    'קריית חינוך חטיבה': 'North',
    'אלדד נתניה': 'North',
    'אולפנית מירון': 'North',
    'תיכון נשר': 'North',
    'אולפנית אמונה אלישבע': 'North',
    'כרמים': 'North',
    'אולפנת סגולה': 'North',
    'אסיף': 'North',
    'שבילים': 'North',
    'חטיבת יונתן': 'Lowland',
    'גולדה': 'Lowland',
    'אולפנית ישורון': 'Lowland',
    'רמון': 'Lowland'
}

def get_school_region(school_name):
    """Get region for a school"""
    return SCHOOL_MAPPING.get(school_name, 'Unknown')

# ============================================================================
# SEVERITY MAPPING
# ============================================================================

SEVERITY_MAP = {
    "תקלה במנעול": 5,
    "הקוד לא עובד": 4,
    "נזק לדלת": 3,
    "מפתח אבוד": 2,
    "אחר": 1
}

def get_severity(fault_type):
    """Get severity level (1-5) based on fault type"""
    return SEVERITY_MAP.get(fault_type, 1)

# ============================================================================
# SQLITE MODEL - Faults Table
# ============================================================================

class Fault(Base):
    __tablename__ = 'faults'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id_ext = Column(String, nullable=False)
    locker_id = Column(String, nullable=True)
    fault_type = Column(String, nullable=False)
    severity = Column(Integer, nullable=False)
    books_stuck = Column(Boolean, default=False)
    is_urgent = Column(Boolean, default=False)
    is_recurring = Column(Boolean, default=False)
    status = Column(String, default='Open')
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    assigned_technician = Column(String, nullable=True)
    technician_notes = Column(String, nullable=True)

# Create tables
Base.metadata.create_all(sqlite_engine)

# Create session
SqliteSession = sessionmaker(bind=sqlite_engine)

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/')
def index():
    """Serve the main SPA page"""
    return render_template('index.html')

@app.route('/api/students', methods=['GET'])
def get_students():
    """Return cached students list as JSON"""
    if GLOBAL_STUDENTS_DF is None:
        return jsonify({'error': 'Students cache not loaded'}), 500
    
    # Convert DataFrame to JSON-friendly format
    students = GLOBAL_STUDENTS_DF.copy()
    students['display_name'] = (
        students['fname'] + ' ' + students['lname'] + 
        ' | ת.ז: ' + students['studentId'] + 
        ' | ' + students['school_name'].fillna('אין בית ספר')
    )
    
    return jsonify(students.to_dict(orient='records'))

@app.route('/api/faults', methods=['GET'])
def get_faults():
    """Return all faults from SQLite with student information"""
    session = SqliteSession()
    try:
        faults = session.query(Fault).order_by(Fault.created_at.desc()).all()
        
        # Enrich with student data from cache
        result = []
        for fault in faults:
            fault_dict = {
                'id': fault.id,
                'student_id_ext': fault.student_id_ext,
                'locker_id': fault.locker_id,
                'fault_type': fault.fault_type,
                'severity': fault.severity,
                'books_stuck': fault.books_stuck,
                'is_urgent': fault.is_urgent,
                'is_recurring': getattr(fault, 'is_recurring', False),  # Safe access for old DB records
                'status': fault.status,
                'description': fault.description,
                'created_at': fault.created_at.isoformat() if fault.created_at else None,
                'resolved_at': fault.resolved_at.isoformat() if fault.resolved_at else None,
                'assigned_technician': fault.assigned_technician,
                'technician_notes': getattr(fault, 'technician_notes', None)  # Safe access for new column
            }
            
            # Get student info from cache
            if GLOBAL_STUDENTS_DF is not None:
                student_info = GLOBAL_STUDENTS_DF[GLOBAL_STUDENTS_DF['id'] == fault.student_id_ext]
                if not student_info.empty:
                    student = student_info.iloc[0]
                    fault_dict['student_name'] = f"{student['fname']} {student['lname']}"
                    fault_dict['studentId'] = student['studentId']
                    school_name = student.get('school_name', 'N/A')
                    fault_dict['school_name'] = school_name
                    # Add region based on school mapping
                    fault_dict['region'] = SCHOOL_MAPPING.get(school_name, 'Unknown')
                else:
                    fault_dict['student_name'] = 'Unknown'
                    fault_dict['studentId'] = 'N/A'
                    fault_dict['school_name'] = 'N/A'
                    fault_dict['region'] = 'Unknown'
            else:
                fault_dict['region'] = 'Unknown'
            
            result.append(fault_dict)
        
        return jsonify(result)
    finally:
        session.close()

@app.route('/api/faults', methods=['POST'])
def create_fault():
    """Create a new fault in SQLite with automatic recurring detection"""
    data = request.get_json()
    
    session = SqliteSession()
    try:
        severity = get_severity(data['fault_type'])
        is_urgent = data.get('books_stuck', False)
        
        # ========================================================================
        # AUTO-DETECT RECURRING FAULT
        # Check if this student had the same fault type before (Resolved/Closed)
        # ========================================================================
        is_recurring = False
        previous_faults = session.query(Fault).filter(
            Fault.student_id_ext == data['student_id_ext'],
            Fault.fault_type == data['fault_type'],
            Fault.status.in_(['Resolved', 'Closed'])
        ).first()
        
        if previous_faults:
            is_recurring = True
        
        new_fault = Fault(
            student_id_ext=data['student_id_ext'],
            locker_id=data.get('locker_id'),
            fault_type=data['fault_type'],
            severity=severity,
            books_stuck=data.get('books_stuck', False),
            is_urgent=is_urgent,
            is_recurring=is_recurring,  # Automatically detected
            status='Open',
            description=data.get('description')
        )
        
        session.add(new_fault)
        session.commit()
        session.refresh(new_fault)
        
        return jsonify({
            'success': True,
            'fault_id': new_fault.id,
            'is_recurring': is_recurring,
            'message': f'תקלה נוצרה בהצלחה{" (זוהתה כתקלה חוזרת)" if is_recurring else ""}'
        })
    except Exception as e:
        session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/update_status', methods=['POST'])
def update_status():
    """Update fault status"""
    data = request.get_json()
    
    session = SqliteSession()
    try:
        fault = session.query(Fault).filter(Fault.id == data['fault_id']).first()
        
        if not fault:
            return jsonify({'success': False, 'error': 'Fault not found'}), 404
        
        new_status = data['status']
        fault.status = new_status
        
        if new_status == 'Resolved' or new_status == 'Closed':
            if not fault.resolved_at:
                fault.resolved_at = datetime.utcnow()
        elif new_status == 'Open':
            fault.resolved_at = None
        
        if 'technician' in data:
            fault.assigned_technician = data['technician']
        
        session.commit()
        
        return jsonify({'success': True, 'message': 'סטטוס עודכן בהצלחה'})
    except Exception as e:
        session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/faults/update', methods=['POST'])
def update_fault_with_notes():
    """
    Update fault with technician notes and status change
    Expected JSON: {fault_id, status, technician_notes}
    """
    data = request.get_json()
    
    session = SqliteSession()
    try:
        fault = session.query(Fault).filter(Fault.id == data['fault_id']).first()
        
        if not fault:
            return jsonify({'success': False, 'error': 'Fault not found'}), 404
        
        # Update status if provided
        if 'status' in data:
            new_status = data['status']
            fault.status = new_status
            
            if new_status in ['Resolved', 'Closed']:
                if not fault.resolved_at:
                    fault.resolved_at = datetime.utcnow()
            elif new_status == 'Open':
                fault.resolved_at = None
        
        # Update technician notes if provided
        if 'technician_notes' in data:
            fault.technician_notes = data['technician_notes']
        
        # Update assigned technician if provided
        if 'technician' in data:
            fault.assigned_technician = data['technician']
        
        session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'התקלה עודכנה בהצלחה',
            'fault': {
                'id': fault.id,
                'status': fault.status,
                'technician_notes': fault.technician_notes,
                'resolved_at': fault.resolved_at.isoformat() if fault.resolved_at else None
            }
        })
    except Exception as e:
        session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        session.close()

# ============================================================================
# SCHEDULING ALGORITHM - 2-STAGE HYBRID MODEL
# ============================================================================

def run_scheduling_algorithm(faults_df, num_technicians):
    """
    3-Stage Scheduling Algorithm (Strict Region Exhaustion)
    
    Stage 1: Mathematical Priority Scoring
    Stage 2: Assignment Logic
        - Phase 1 (Anchors): Assign top priority schools to lock each tech to a region.
        - Phase 2 (Strict Exhaustion): Each tech absorbs ALL remaining schools in their 
                                       assigned region until they hit their workload cap.
        - Phase 3 (Leftovers): Any unassigned schools (due to cap or unassigned region) 
                               are given to the most idle tech globally.
    """
    if faults_df.empty:
        return {}
    
    # Calculate age
    now = datetime.utcnow()
    faults_df['age_days'] = faults_df['created_at'].apply(
        lambda x: (now - x).total_seconds() / 86400 if x else 0
    )
    
    # Group by school
    school_metrics = faults_df.groupby('school_name').agg({
        'fault_id': 'count',
        'severity': 'mean',
        'age_days': 'max',
        'is_recurring': 'max',
        'is_urgent': 'max',
        'region': 'first'
    }).reset_index()
    
    school_metrics.columns = ['school_name', 'fault_count', 'avg_severity', 
                              'max_age_days', 'has_recurring', 'has_urgent', 'region']
    
    # Priority Scoring
    school_metrics['N'] = school_metrics['fault_count'].apply(lambda x: min(x, 5))
    school_metrics['U'] = school_metrics['avg_severity']
    school_metrics['T'] = school_metrics['max_age_days'].apply(lambda x: min(max(x, 1), 5))
    school_metrics['R'] = school_metrics['has_recurring'].apply(lambda x: 5 if x else 1)
    
    school_metrics['priority_score'] = (
        0.35 * school_metrics['N'] +
        0.25 * school_metrics['U'] +
        0.25 * school_metrics['T'] +
        0.15 * school_metrics['R']
    )
    school_metrics.loc[school_metrics['has_urgent'] == True, 'priority_score'] = 10000
    
    school_metrics = school_metrics.sort_values('priority_score', ascending=False).reset_index(drop=True)
    school_metrics['assigned'] = False
    
    # Initialization
    assignments = {}
    technician_workload = {}
    tech_primary_region = {}
    
    for i in range(1, num_technicians + 1):
        tech_name = f'Technician {i}'
        assignments[tech_name] = []
        technician_workload[tech_name] = 0
        tech_primary_region[tech_name] = None
        
    total_faults = len(faults_df)
    workload_cap = (total_faults / num_technicians) * 1.5

    # ========================================================================
    # PHASE 1: ANCHOR SEEDING (Lock regions)
    # ========================================================================
    num_anchors = min(num_technicians, len(school_metrics))
    
    for i in range(num_anchors):
        school = school_metrics.iloc[i]
        tech_name = f'Technician {i + 1}'
        
        school_name = school['school_name']
        region = school['region']
        num_faults = school['fault_count']
        
        assignments[tech_name].append({
            'school_name': school_name,
            'region': region,
            'priority_score': float(school['priority_score']),
            'num_faults': int(num_faults),
            'is_urgent': bool(school['has_urgent']),
            'avg_severity': float(school['avg_severity']),
            'oldest_fault_days': float(school['max_age_days']),
            'faults': faults_df[faults_df['school_name'] == school_name].to_dict(orient='records'),
            'assignment_type': 'Phase 1 - Anchor'
        })
        
        technician_workload[tech_name] += num_faults
        tech_primary_region[tech_name] = region
        school_metrics.loc[i, 'assigned'] = True

    # ========================================================================
    # PHASE 2: STRICT REGION EXHAUSTION
    # ========================================================================
    # Each tech absorbs ALL unassigned schools in their primary region until capped
    
    for tech_name, primary_region in tech_primary_region.items():
        if not primary_region:
            continue
            
        # Find all unassigned schools in this specific region
        region_schools = school_metrics[
            (~school_metrics['assigned']) & 
            (school_metrics['region'] == primary_region)
        ]
        
        for idx, school in region_schools.iterrows():
            num_faults = school['fault_count']
            
            # If the tech has capacity, assign it to them
            if technician_workload[tech_name] + num_faults <= workload_cap:
                school_name = school['school_name']
                assignments[tech_name].append({
                    'school_name': school_name,
                    'region': primary_region,
                    'priority_score': float(school['priority_score']),
                    'num_faults': int(num_faults),
                    'is_urgent': bool(school['has_urgent']),
                    'avg_severity': float(school['avg_severity']),
                    'oldest_fault_days': float(school['max_age_days']),
                    'faults': faults_df[faults_df['school_name'] == school_name].to_dict(orient='records'),
                    'assignment_type': 'Phase 2 - Region Absorbed'
                })
                technician_workload[tech_name] += num_faults
                school_metrics.loc[idx, 'assigned'] = True

    # ========================================================================
    # PHASE 3: GLOBAL LEFTOVERS (Spillover / Uncovered Regions)
    # ========================================================================
    # Any schools still unassigned go to the most idle tech globally
    
    unassigned_schools = school_metrics[~school_metrics['assigned']]
    
    for idx, school in unassigned_schools.iterrows():
        num_faults = school['fault_count']
        school_name = school['school_name']
        region = school['region']
        
        # Find the absolute most idle tech right now
        best_tech = min(technician_workload.items(), key=lambda x: x[1])[0]
        
        assignments[best_tech].append({
            'school_name': school_name,
            'region': region,
            'priority_score': float(school['priority_score']),
            'num_faults': int(num_faults),
            'is_urgent': bool(school['has_urgent']),
            'avg_severity': float(school['avg_severity']),
            'oldest_fault_days': float(school['max_age_days']),
            'faults': faults_df[faults_df['school_name'] == school_name].to_dict(orient='records'),
            'assignment_type': 'Phase 3 - Overflow Leftover'
        })
        
        technician_workload[best_tech] += num_faults
        school_metrics.loc[idx, 'assigned'] = True

    return assignments

@app.route('/api/schedule', methods=['POST'])
def schedule_technicians():
    """
    Smart scheduling endpoint using 2-Stage Hybrid Algorithm
    """
    data = request.get_json()
    num_technicians = data.get('num_technicians', 1)
    
    session = SqliteSession()
    try:
        # Get all open faults
        open_faults = session.query(Fault).filter(Fault.status == 'Open').all()
        
        if not open_faults:
            return jsonify({
                'success': True,
                'message': 'אין תקלות פתוחות',
                'assignments': []
            })
        
        # Enrich faults with student/school data
        faults_data = []
        for fault in open_faults:
            if GLOBAL_STUDENTS_DF is not None:
                student_info = GLOBAL_STUDENTS_DF[GLOBAL_STUDENTS_DF['id'] == fault.student_id_ext]
                if not student_info.empty:
                    school_name = student_info.iloc[0].get('school_name', 'Unknown')
                    student_name = f"{student_info.iloc[0]['fname']} {student_info.iloc[0]['lname']}"
                else:
                    school_name = 'Unknown'
                    student_name = 'Unknown'
            else:
                school_name = 'Unknown'
                student_name = 'Unknown'
            
            region = get_school_region(school_name)
            
            faults_data.append({
                'fault_id': fault.id,
                'student_name': student_name,
                'school_name': school_name,
                'region': region,
                'fault_type': fault.fault_type,
                'severity': fault.severity,
                'is_urgent': fault.is_urgent,
                'books_stuck': fault.books_stuck,
                'is_recurring': getattr(fault, 'is_recurring', False),  # Safe access
                'created_at': fault.created_at
            })
        
        # Create DataFrame for algorithm
        df = pd.DataFrame(faults_data)
        
        # Run the scheduling algorithm
        tech_assignments = run_scheduling_algorithm(df, num_technicians)
        
        # Format output for frontend
        assignments = []
        for tech_name, schools in tech_assignments.items():
            tech_id = int(tech_name.split()[-1])
            
            # Calculate total metrics for this technician
            total_score = sum(s['priority_score'] for s in schools)
            total_faults = sum(s['num_faults'] for s in schools)
            
            # Flatten all faults for this technician
            all_faults = []
            for school in schools:
                all_faults.extend(school['faults'])
            
            assignments.append({
                'technician_id': tech_id,
                'schools': schools,
                'total_score': total_score,
                'total_faults': total_faults,
                'faults': all_faults
            })
        
        return jsonify({
            'success': True,
            'num_technicians': num_technicians,
            'assignments': assignments
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        session.close()

# ============================================================================
# APPLICATION STARTUP
# ============================================================================

if __name__ == '__main__':
    # Load students into cache BEFORE starting the server
    if load_students_to_cache():
        print("✅ Flask server ready with cached students data")
        app.run(debug=True, host='0.0.0.0', port=5000)
    else:
        print("❌ Failed to load students cache. Server not started.")
