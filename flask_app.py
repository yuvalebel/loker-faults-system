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
                'assigned_technician': fault.assigned_technician
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

# ============================================================================
# SCHEDULING ALGORITHM - 2-STAGE HYBRID MODEL
# ============================================================================

def run_scheduling_algorithm(faults_df, num_technicians):
    """
    2-Stage Hybrid Scheduling Algorithm
    
    Stage 1: Mathematical Priority Scoring
    Formula: Score = 0.35*N + 0.25*U + 0.25*T + 0.15*R
    
    Variables:
    - N (Efficiency - 35%): Count of open faults (normalized 1-5+)
    - U (Severity - 25%): Average severity score (1-5 scale)
    - T (Fairness - 25%): Age of oldest fault in days (normalized 1-5+)
    - R (Recurring - 15%): 5 if is_recurring=True, else 1
    
    CRITICAL OVERRIDE: If any fault has is_urgent=True -> Score = 10000
    
    Stage 2: Regional Anchor & Cluster Assignment
    - Sort all schools by Score (descending)
    - For each technician:
        - Find highest priority unassigned school (Anchor)
        - Assign ALL schools from that same region to this technician
        - Move to next technician with next highest unassigned school
    - Each technician works in ONE region only (minimizes travel)
    - If region has too many faults, split between technicians
    
    Args:
        faults_df: DataFrame with fault data including school_name, region, severity, 
                   is_urgent, is_recurring, created_at
        num_technicians: Number of available technicians
    
    Returns:
        Dictionary mapping technician names to lists of assigned schools with details
    """
    
    if faults_df.empty:
        return {}
    
    # ========================================================================
    # STAGE 1: CALCULATE PRIORITY SCORES FOR EACH SCHOOL
    # ========================================================================
    
    now = datetime.utcnow()
    
    # Calculate age of each fault in days
    faults_df['age_days'] = faults_df['created_at'].apply(
        lambda x: (now - x).total_seconds() / 86400 if x else 0
    )
    
    # Group by school and calculate metrics
    school_metrics = faults_df.groupby('school_name').agg({
        'fault_id': 'count',           # N: Count of faults
        'severity': 'mean',             # U: Average severity
        'age_days': 'max',              # T: Oldest fault age
        'is_recurring': 'max',          # R: Any recurring fault?
        'is_urgent': 'max',             # Override check
        'region': 'first'               # Region mapping
    }).reset_index()
    
    school_metrics.columns = ['school_name', 'fault_count', 'avg_severity', 
                              'max_age_days', 'has_recurring', 'has_urgent', 'region']
    
    # ========================================================================
    # APPLY THE SCORING FORMULA WITH NORMALIZATION
    # ========================================================================
    
    # N: Normalize fault count (1-5+)
    school_metrics['N'] = school_metrics['fault_count'].apply(lambda x: min(x, 5))
    
    # U: Average severity is already 1-5 scale
    school_metrics['U'] = school_metrics['avg_severity']
    
    # T: Normalize age in days (1-5+)
    school_metrics['T'] = school_metrics['max_age_days'].apply(lambda x: min(max(x, 1), 5))
    
    # R: Recurring flag (5 if True, 1 if False)
    school_metrics['R'] = school_metrics['has_recurring'].apply(lambda x: 5 if x else 1)
    
    # Calculate base score using the formula
    school_metrics['priority_score'] = (
        0.35 * school_metrics['N'] +
        0.25 * school_metrics['U'] +
        0.25 * school_metrics['T'] +
        0.15 * school_metrics['R']
    )
    
    # CRITICAL OVERRIDE: Urgent faults get MAXIMUM priority (books_stuck = True)
    school_metrics.loc[school_metrics['has_urgent'] == True, 'priority_score'] = 10000
    
    # ========================================================================
    # STAGE 2: ANCHOR & CLUSTER ASSIGNMENT
    # ========================================================================
    
    # Sort schools by priority score (highest first)
    school_metrics = school_metrics.sort_values('priority_score', ascending=False).reset_index(drop=True)
    
    # Track which schools have been assigned
    school_metrics['assigned'] = False
    
    # Initialize technician assignments
    assignments = {}
    for i in range(1, num_technicians + 1):
        assignments[f'Technician {i}'] = []
    
    # Assign schools using Regional Anchor & Cluster strategy
    tech_index = 0
    
    while school_metrics[~school_metrics['assigned']].shape[0] > 0:
        # Get current technician
        current_tech = f'Technician {tech_index + 1}'
        
        # Find the highest priority unassigned school (ANCHOR)
        unassigned_schools = school_metrics[~school_metrics['assigned']]
        
        if unassigned_schools.empty:
            break
        
        # Get the top priority school and its region
        anchor_school = unassigned_schools.iloc[0]
        anchor_region = anchor_school['region']
        
        # Get ALL unassigned schools from the same region as the anchor
        region_schools = school_metrics[
            (school_metrics['region'] == anchor_region) & 
            (~school_metrics['assigned'])
        ]
        
        # Assign all schools in this region to the current technician
        for _, school in region_schools.iterrows():
            # Get all faults for this school
            school_faults = faults_df[faults_df['school_name'] == school['school_name']]
            
            assignments[current_tech].append({
                'school_name': school['school_name'],
                'region': school['region'],
                'priority_score': float(school['priority_score']),
                'num_faults': int(school['fault_count']),
                'is_urgent': bool(school['has_urgent']),
                'avg_severity': float(school['avg_severity']),
                'oldest_fault_days': float(school['max_age_days']),
                'faults': school_faults.to_dict(orient='records')
            })
            
            # Mark school as assigned
            school_metrics.loc[school_metrics['school_name'] == school['school_name'], 'assigned'] = True
        
        # Move to next technician (round-robin)
        tech_index = (tech_index + 1) % num_technicians
    
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
