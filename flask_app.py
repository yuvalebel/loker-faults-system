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

SCHOOL_MAPPING = {
    'שש שנתי אשל הנשיא': 'South', 'חטיבת הביניים סוסיא': 'South', 'טכני חיל האוויר': 'South',
    'אמית ברוכין': 'Center', 'אולפנת קרני שומרון': 'Center', 'להבה': 'Center',
    'בעברית תיכון אוניברסי': 'Jerusalem', 'אמי״ת בנים מודיעין': 'Jerusalem', 'תבל רמות': 'Jerusalem',
    'ישיבת שעלבים': 'Jerusalem', 'ענבר': 'Jerusalem', 'נשמת התורה': 'Jerusalem',
    'מכון לב': 'Jerusalem', 'אמי"ת מעלה אדומים': 'Jerusalem', 'אולפנת שעלבים': 'Jerusalem',
    'אורט תעשייה אווירית': 'Center', 'לאורו נלך': 'Center', 'מיכה רייסר': 'Center',
    'צמרות': 'Center', 'אולפנת צביה לוד': 'Center', 'מקיף י׳ אלברט איינשטיי': 'Center',
    'אולפנת יבנה': 'Center', 'אמירים (מקיף ה)': 'Center', "מקיף ז' רביבים": 'Center',
    'אמי"ת בנות מודיעין': 'Center', 'נתיבות רבקה': 'Center', 'סמינר שושנים': 'Center',
    'קינג סולומון הכפר הירו': 'Center', 'פלך': 'Center', 'בר אילן': 'Center',
    'שובו': 'Center', 'בית ספר יצחק שמיר': 'Center', 'מאיר שלו': 'Center',
    'אולפנת רמלה': 'Center', 'קריית חינוך חטיבה': 'North', 'אלדד נתניה': 'North',
    'אולפנית מירון': 'North', 'תיכון נשר': 'North', 'אולפנית אמונה אלישבע': 'North',
    'כרמים': 'North', 'אולפנת סגולה': 'North', 'אסיף': 'North', 'שבילים': 'North',
    'חטיבת יונתן': 'Lowland', 'גולדה': 'Lowland', 'אולפנית ישורון': 'Lowland', 'רמון': 'Lowland'
}

def get_school_region(school_name):
    """Get region for a school"""
    return SCHOOL_MAPPING.get(school_name, 'Unknown')

# ============================================================================
# SEVERITY MAPPING
# ============================================================================

SEVERITY_MAP = {
    "תקלה במנעול": 5,
    "ספרים תקועים": 4,
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
                    fault_dict['school_name'] = student.get('school_name', 'N/A')
                else:
                    fault_dict['student_name'] = 'Unknown'
                    fault_dict['studentId'] = 'N/A'
                    fault_dict['school_name'] = 'N/A'
            
            result.append(fault_dict)
        
        return jsonify(result)
    finally:
        session.close()

@app.route('/api/faults', methods=['POST'])
def create_fault():
    """Create a new fault in SQLite"""
    data = request.get_json()
    
    session = SqliteSession()
    try:
        severity = get_severity(data['fault_type'])
        is_urgent = data.get('books_stuck', False)
        
        new_fault = Fault(
            student_id_ext=data['student_id_ext'],
            locker_id=data.get('locker_id'),
            fault_type=data['fault_type'],
            severity=severity,
            books_stuck=data.get('books_stuck', False),
            is_urgent=is_urgent,
            status='Open',
            description=data.get('description')
        )
        
        session.add(new_fault)
        session.commit()
        session.refresh(new_fault)
        
        return jsonify({
            'success': True,
            'fault_id': new_fault.id,
            'message': 'תקלה נוצרה בהצלחה'
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

@app.route('/api/schedule', methods=['POST'])
def schedule_technicians():
    """
    Smart scheduling algorithm
    Formula: Priority Score = 0.35*N + 0.25*U + 0.25*T + 0.15*R (PER SCHOOL)
    Where:
    - N = Number of open faults in school
    - U = Number of urgent faults (books stuck)
    - T = Total severity score
    - R = Number of recently reported faults (last 24 hours)
    
    If is_urgent -> Priority = 1000 (override)
    Schools are distributed evenly across technicians using load balancing.
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
                'created_at': fault.created_at
            })
        
        # Group by school and calculate priority scores
        df = pd.DataFrame(faults_data)
        
        # Calculate recent faults (last 24 hours)
        now = datetime.utcnow()
        df['is_recent'] = df['created_at'].apply(
            lambda x: 1 if (now - x).total_seconds() < 86400 else 0
        )
        
        school_scores = df.groupby('school_name').agg({
            'fault_id': 'count',  # N - number of faults
            'books_stuck': 'sum',  # U - urgent faults
            'severity': 'sum',     # T - total severity
            'is_recent': 'sum',    # R - recent faults
            'region': 'first',
            'is_urgent': 'max'     # Check if any urgent
        }).reset_index()
        
        school_scores.columns = ['school_name', 'N', 'U', 'T', 'R', 'region', 'has_urgent']
        
        # Calculate priority score FOR EACH SCHOOL
        # Formula: 0.35*N + 0.25*U + 0.25*T + 0.15*R
        school_scores['priority_score'] = (
            0.35 * school_scores['N'] +
            0.25 * school_scores['U'] +
            0.25 * school_scores['T'] +
            0.15 * school_scores['R']
        )
        
        # Override to 1000 if urgent
        school_scores.loc[school_scores['has_urgent'] == True, 'priority_score'] = 1000
        
        # Sort schools by priority (highest first)
        school_scores = school_scores.sort_values('priority_score', ascending=False)
        
        # Initialize technicians
        technicians = [{'id': i+1, 'score': 0, 'schools': [], 'faults': []} 
                      for i in range(num_technicians)]
        
        # Distribute schools to technicians using load balancing
        # Each school goes to the technician with the lowest current score
        for _, school_row in school_scores.iterrows():
            # Find technician with minimum workload
            tech_idx = min(range(num_technicians), 
                          key=lambda i: technicians[i]['score'])
            
            # Get all faults for this school
            school_faults = df[df['school_name'] == school_row['school_name']].to_dict(orient='records')
            
            # Assign school to this technician
            technicians[tech_idx]['score'] += school_row['priority_score']
            technicians[tech_idx]['schools'].append({
                'school_name': school_row['school_name'],
                'region': school_row['region'],
                'priority_score': school_row['priority_score'],
                'num_faults': school_row['N']
            })
            technicians[tech_idx]['faults'].extend(school_faults)
        
        # Format assignments
        assignments = []
        for tech in technicians:
            assignments.append({
                'technician_id': tech['id'],
                'schools': tech['schools'],
                'total_score': tech['score'],
                'total_faults': len(tech['faults']),
                'faults': tech['faults']
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
