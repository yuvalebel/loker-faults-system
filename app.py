"""
Streamlit Faults System - Sidecar Architecture
===============================================
This application uses a hybrid database approach:
- PostgreSQL (Legacy/Read-Only): Existing students data
- SQLite (New/Write): New faults system data
"""

import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================

# Database URLs
POSTGRES_URL = os.getenv('DATABASE_URL', 'postgresql://team41:xBjwE7X6BjQjARSGTFcWOg7TJ0ZiQbyq@dpg-d615mm24d50c73eh9o0g-a.oregon-postgres.render.com/studentlocker')
SQLITE_URL = 'sqlite:///faults_system.db'

@st.cache_resource
def init_db_connection():
    """
    Initialize and cache database connections.
    This prevents recreating connections on every rerun.
    Returns: tuple of (postgres_engine, sqlite_engine)
    """
    postgres_engine = create_engine(
        POSTGRES_URL,
        echo=False,
        pool_pre_ping=True,  # Verify connection health
        pool_recycle=3600    # Recycle connections after 1 hour
    )
    
    sqlite_engine = create_engine(
        SQLITE_URL,
        echo=False,
        connect_args={'check_same_thread': False}
    )
    
    return postgres_engine, sqlite_engine

# Get cached database engines
postgres_engine, sqlite_engine = init_db_connection()

Base = declarative_base()

# ============================================================================
# SEVERITY MAPPING - חומרת תקלות
# ============================================================================

SEVERITY_MAP = {
    "תקלה במנעול": 5,        # Lock Malfunction - חמור ביותר
    "ספרים תקועים": 4,        # Books Stuck - דחוף
    "הקוד לא עובד": 4,        # Code Not Working - דחוף
    "נזק לדלת": 3,            # Door Damage - בינוני
    "מפתח אבוד": 2,           # Lost Key - קל
    "אחר": 1                   # Other - קל ביותר
}

def get_severity(fault_type):
    """Get severity level (1-5) based on fault type"""
    return SEVERITY_MAP.get(fault_type, 1)

# ============================================================================
# SCHOOL TO REGION MAPPING - Intelligence Layer
# ============================================================================
# This mapping determines which region each school belongs to
# The database only stores school_name, region is determined here

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
    """Get region for a school based on SCHOOL_MAPPING"""
    return SCHOOL_MAPPING.get(school_name, 'Unknown')

# ============================================================================
# SQLITE MODEL - New Faults Table
# ============================================================================

class Fault(Base):
    __tablename__ = 'faults'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id_ext = Column(String, nullable=False)  # מפתח זר לתלמיד מ-PostgreSQL
    locker_id = Column(String, nullable=True)
    fault_type = Column(String, nullable=False)  # סוג התקלה מרשימה
    severity = Column(Integer, nullable=False)  # חומרת התקלה (1-5)
    books_stuck = Column(Boolean, default=False)  # האם יש ספרים תקועים?
    is_urgent = Column(Boolean, default=False)
    status = Column(String, default='Open')
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)  # תאריך אוטומטי
    resolved_at = Column(DateTime, nullable=True)
    assigned_technician = Column(String, nullable=True)
    
    # ============== METHODS - Object-Oriented Approach ==============
    
    def mark_as_in_progress(self, technician_name=None):
        """Mark fault as InProgress and optionally assign technician"""
        self.status = 'InProgress'
        if technician_name:
            self.assigned_technician = technician_name
        return self
    
    def mark_as_resolved(self):
        """Mark fault as Resolved with timestamp"""
        self.status = 'Resolved'
        self.resolved_at = datetime.utcnow()
        return self
    
    def mark_as_closed(self):
        """Mark fault as Closed"""
        self.status = 'Closed'
        if not self.resolved_at:
            self.resolved_at = datetime.utcnow()
        return self
    
    def reopen(self):
        """Reopen a closed fault"""
        self.status = 'Open'
        self.resolved_at = None
        return self
    
    def update_description(self, new_description):
        """Update the fault description"""
        self.description = new_description
        return self
    
    def toggle_urgency(self):
        """Toggle urgent status"""
        self.is_urgent = not self.is_urgent
        return self
    
    def get_student_info(self):
        """Get student information from PostgreSQL"""
        query = f"""
            SELECT 
                s.id,
                s."fname" || ' ' || s."lname" as name,
                s."studentId",
                sc.name as school_name
            FROM "Student" s
            LEFT JOIN "School" sc ON s."schoolId" = sc.id
            WHERE s.id = '{self.student_id_ext}'
        """
        
        with postgres_engine.connect() as conn:
            result = pd.read_sql(query, conn)
            if not result.empty:
                return result.iloc[0].to_dict()
        return None
    
    def to_dict(self):
        """Convert Fault object to dictionary"""
        return {
            'id': self.id,
            'student_id_ext': self.student_id_ext,
            'locker_id': self.locker_id,
            'fault_type': self.fault_type,
            'severity': self.severity,
            'books_stuck': self.books_stuck,
            'is_urgent': self.is_urgent,
            'status': self.status,
            'description': self.description,
            'created_at': self.created_at,
            'resolved_at': self.resolved_at,
            'assigned_technician': self.assigned_technician
        }
    
    def __repr__(self):
        return f"<Fault(id={self.id}, type='{self.fault_type}', status='{self.status}', urgent={self.is_urgent})>"

# Create SQLite tables
Base.metadata.create_all(sqlite_engine)

# Create sessions
PostgresSession = sessionmaker(bind=postgres_engine)
SqliteSession = sessionmaker(bind=sqlite_engine)

# ============================================================================
# DATA ACCESS FUNCTIONS
# ============================================================================

def get_students():
    """
    Fetch students from PostgreSQL (Read-Only)
    Returns a pandas DataFrame with student information
    """
    # Try with School table first, fallback to Student only
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
            df = pd.read_sql(query, conn)
        
        return df
    except Exception:
        # Fallback: query without School table
        query = """
            SELECT DISTINCT
                s.id,
                s.fname,
                s.lname,
                s."studentId",
                s.class,
                s."classNumber",
                s."parentPhone",
                s.email,
                NULL as school_name
            FROM "Student" s
            ORDER BY s.fname, s.lname
        """
        
        with postgres_engine.connect() as conn:
            df = pd.read_sql(query, conn)
        
        return df

def get_student_locker(student_id):
    """
    Get locker information for a specific student
    """
    query = f"""
        SELECT 
            l.id,
            l."lockerNumber",
            c.name as closet_name,
            co.name as complex_name
        FROM "Locker" l
        LEFT JOIN "Closet" c ON l."closetId" = c.id
        LEFT JOIN "Complex" co ON c."complexId" = co.id
        WHERE l."studentId" = '{student_id}'
        LIMIT 1
    """
    
    try:
        with postgres_engine.connect() as conn:
            result = pd.read_sql(query, conn)
            if not result.empty:
                return result.iloc[0]
    except Exception as e:
        st.error(f"Error fetching locker: {e}")
    
    return None

def save_fault(student_id_ext, locker_id, fault_type, books_stuck, is_urgent, description):
    """
    Save a new fault to SQLite database (OOP Approach)
    Returns: Fault object if successful, None if failed
    """
    session = SqliteSession()
    try:
        # חישוב חומרה אוטומטי לפי סוג התקלה
        severity = get_severity(fault_type)
        
        # תקלה דחופה = ספרים תקועים בלוקר
        is_urgent = books_stuck
        
        new_fault = Fault(
            student_id_ext=student_id_ext,
            locker_id=locker_id,
            fault_type=fault_type,
            severity=severity,
            books_stuck=books_stuck,
            is_urgent=is_urgent,
            status='Open',
            description=description
        )
        session.add(new_fault)
        session.commit()
        session.refresh(new_fault)  # Get the ID after commit
        fault_dict = new_fault.to_dict()
        session.close()
        return fault_dict
    except Exception as e:
        session.rollback()
        session.close()
        st.error(f"שגיאה בשמירת תקלה: {e}")
        return None

def get_all_faults():
    """
    Get all faults from SQLite database as Fault objects
    Returns: List of Fault objects
    """
    session = SqliteSession()
    try:
        faults = session.query(Fault).order_by(Fault.created_at.desc()).all()
        return faults
    finally:
        session.close()

def get_all_faults_df():
    """
    Get all faults as pandas DataFrame (for display purposes)
    """
    faults = get_all_faults()
    if not faults:
        return pd.DataFrame()
    
    data = [fault.to_dict() for fault in faults]
    return pd.DataFrame(data)

def get_faults_with_student_info():
    """
    Get faults with student information from PostgreSQL (OOP Approach)
    Returns: List of dicts with fault + student info
    """
    faults = get_all_faults()
    
    if not faults:
        return pd.DataFrame()
    
    # Get unique student IDs
    student_ids = list(set([f.student_id_ext for f in faults]))
    student_ids_str = "','".join(student_ids)
    
    # Fetch student info from PostgreSQL (try with School, fallback without)
    try:
        query = f"""
            SELECT 
                s.id,
                s.fname || ' ' || s.lname as student_name,
                s."studentId",
                sc.name as school_name
            FROM "Student" s
            LEFT JOIN "School" sc ON s."schoolId" = CAST(sc.id AS TEXT)
            WHERE s.id IN ('{student_ids_str}')
        """
        
        with postgres_engine.connect() as conn:
            students_df = pd.read_sql(query, conn)
    except Exception:
        # Fallback: query without School table
        query = f"""
            SELECT 
                s.id,
                s.fname || ' ' || s.lname as student_name,
                s."studentId",
                NULL as school_name
            FROM "Student" s
            WHERE s.id IN ('{student_ids_str}')
        """
        
        with postgres_engine.connect() as conn:
            students_df = pd.read_sql(query, conn)
    
    try:
        # Create enriched fault data
        enriched_data = []
        for fault in faults:
            fault_dict = fault.to_dict()
            student_info = students_df[students_df['id'] == fault.student_id_ext]
            
            if not student_info.empty:
                student_row = student_info.iloc[0]
                fault_dict['student_name'] = student_row['student_name']
                fault_dict['studentId'] = student_row['studentId']
                fault_dict['school_name'] = student_row.get('school_name', 'N/A')
            else:
                fault_dict['student_name'] = 'Unknown'
                fault_dict['studentId'] = 'N/A'
                fault_dict['school_name'] = 'N/A'
            
            enriched_data.append(fault_dict)
        
        return pd.DataFrame(enriched_data)
    except Exception as e:
        st.error(f"Error fetching student info: {e}")
        # Fallback to basic data
        return pd.DataFrame([f.to_dict() for f in faults])

def get_fault_by_id(fault_id):
    """
    Get a single Fault object by ID
    """
    session = SqliteSession()
    try:
        fault = session.query(Fault).filter(Fault.id == fault_id).first()
        return fault
    finally:
        session.close()

def update_fault_status(fault_id, new_status, technician_name=None):
    """
    Update fault status using OOP methods
    """
    session = SqliteSession()
    try:
        fault = session.query(Fault).filter(Fault.id == fault_id).first()
        
        if not fault:
            return False
        
        if new_status == 'InProgress':
            fault.mark_as_in_progress(technician_name)
        elif new_status == 'Resolved':
            fault.mark_as_resolved()
        elif new_status == 'Closed':
            fault.mark_as_closed()
        elif new_status == 'Open':
            fault.reopen()
        
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        st.error(f"Error updating fault: {e}")
        return False
    finally:
        session.close()

def delete_fault(fault_id):
    """
    Delete a fault by ID
    """
    session = SqliteSession()
    try:
        fault = session.query(Fault).filter(Fault.id == fault_id).first()
        if fault:
            session.delete(fault)
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        st.error(f"Error deleting fault: {e}")
        return False
    finally:
        session.close()

@st.dialog("פרטי תקלה")
def show_fault_details(fault_id):
    """
    Display fault details in a dialog with view/edit modes
    """
    # קבלת האובייקט המלא מהמסד נתונים
    fault_obj = get_fault_by_id(fault_id)
    
    if not fault_obj:
        st.error("❌ תקלה לא נמצאה")
        return
    
    # המרה למילון עם מידע תלמיד
    try:
        # שליפת מידע תלמיד
        query = f"""
            SELECT 
                s.fname || ' ' || s.lname as student_name,
                s."studentId",
                sc.name as school_name
            FROM "Student" s
            LEFT JOIN "School" sc ON s."schoolId" = CAST(sc.id AS TEXT)
            WHERE s.id = '{fault_obj.student_id_ext}'
        """
        with postgres_engine.connect() as conn:
            student_df = pd.read_sql(query, conn)
        
        if not student_df.empty:
            student_info = student_df.iloc[0]
            student_name = student_info['student_name']
            student_id = student_info['studentId']
            school_name = student_info.get('school_name', 'לא ידוע')
        else:
            student_name = "לא ידוע"
            student_id = "N/A"
            school_name = "לא ידוע"
    except:
        student_name = "לא ידוע"
        student_id = "N/A"
        school_name = "לא ידוע"
    
    # ניהול מצב עריכה
    if 'edit_mode' not in st.session_state:
        st.session_state.edit_mode = False
    
    st.markdown(f"### תקלה מספר #{fault_id}")
    st.divider()
    
    # מצב צפייה
    if not st.session_state.edit_mode:
        st.markdown(f"""
        **📋 פרטי התקלה:**
        - **שם תלמיד:** {student_name}
        - **ת.ז:** {student_id}
        - **בית ספר:** {school_name}
        - **מספר לוקר:** {fault_obj.locker_id or 'לא צוין'}
        - **סוג תקלה:** {fault_obj.fault_type}
        - **חומרה:** {'⭐' * fault_obj.severity} ({fault_obj.severity}/5)
        - **ספרים תקועים:** {'✅ כן' if fault_obj.books_stuck else '❌ לא'}
        - **נוצר בתאריך:** {fault_obj.created_at}
        """)
        
        # הצגת סטטוס
        status_map = {'Open': '🟢 פתוח', 'InProgress': '🟡 בטיפול', 'Resolved': '✅ נפתר', 'Closed': '🔒 סגור'}
        st.markdown(f"**סטטוס נוכחי:** {status_map.get(fault_obj.status, fault_obj.status)}")
        
        if fault_obj.assigned_technician:
            st.info(f"👷 **טכנאי מוקצה:** {fault_obj.assigned_technician}")
        
        if fault_obj.description:
            st.text_area("תיאור התקלה:", value=fault_obj.description, disabled=True, height=100)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✏️ עריכת פרטים", type="primary", use_container_width=True):
                st.session_state.edit_mode = True
                st.rerun()
        with col2:
            if st.button("סגור", use_container_width=True):
                st.session_state.edit_mode = False
                st.rerun()
    
    # מצב עריכה
    else:
        st.info("🔧 מצב עריכה - ערוך את הפרטים ולחץ 'שמור שינויים'")
        
        # בחירת סטטוס
        status_options = ['Open', 'InProgress', 'Resolved', 'Closed']
        status_labels = {'Open': '🟢 פתוח', 'InProgress': '🟡 בטיפול', 'Resolved': '✅ נפתר', 'Closed': '🔒 סגור'}
        current_status_index = status_options.index(fault_obj.status) if fault_obj.status in status_options else 0
        
        new_status = st.selectbox(
            "סטטוס",
            options=status_options,
            index=current_status_index,
            format_func=lambda x: status_labels.get(x, x),
            key=f"edit_status_{fault_id}"
        )
        
        # שדה טכנאי - מוצג רק אם הסטטוס הוא בטיפול
        technician_name = None
        if new_status == 'InProgress':
            technician_name = st.text_input(
                "שם טכנאי",
                value=fault_obj.assigned_technician or '',
                key=f"edit_tech_{fault_id}"
            )
        
        # עריכת תיאור
        new_description = st.text_area(
            "תיאור התקלה",
            value=fault_obj.description or '',
            height=150,
            key=f"edit_desc_{fault_id}"
        )
        
        st.divider()
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 שמור שינויים", type="primary", use_container_width=True):
                # עדכון התקלה
                session = SqliteSession()
                try:
                    fault = session.query(Fault).filter(Fault.id == fault_id).first()
                    if fault:
                        # עדכון סטטוס
                        if new_status == 'InProgress':
                            fault.mark_as_in_progress(technician_name)
                        elif new_status == 'Resolved':
                            fault.mark_as_resolved()
                        elif new_status == 'Closed':
                            fault.mark_as_closed()
                        elif new_status == 'Open':
                            fault.reopen()
                        
                        # עדכון תיאור
                        if new_description != fault.description:
                            fault.update_description(new_description)
                        
                        session.commit()
                        st.success("✅ התקלה עודכנה בהצלחה!")
                        st.session_state.edit_mode = False
                        st.rerun()
                except Exception as e:
                    session.rollback()
                    st.error(f"❌ שגיאה בעדכון: {e}")
                finally:
                    session.close()
        
        with col2:
            if st.button("ביטול", use_container_width=True):
                st.session_state.edit_mode = False
                st.rerun()

# ============================================================================
# CUSTOM CSS STYLING - Material Design Professional Theme
# ============================================================================

def local_css():
    """Inject custom CSS for professional SaaS dashboard look"""
    st.markdown("""
    <style>
    /* Import Roboto Font */
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap');
    
    /* Global Styles - RTL Support */
    html, body, [class*="css"] {
        font-family: 'Roboto', 'Helvetica Neue', Arial, sans-serif;
        direction: rtl;
        text-align: right;
    }
    
    /* Main Background */
    .stApp {
        background-color: #f0f2f6;
        direction: rtl;
    }
    
    /* Force RTL for all elements */
    * {
        direction: rtl;
        text-align: right;
    }
    
    /* Fix input fields alignment */
    .stTextInput input,
    .stTextArea textarea,
    .stSelectbox select,
    .stNumberInput input {
        text-align: right;
        direction: rtl;
    }
    
    /* Header Styling */
    h1 {
        color: #1e293b;
        font-weight: 700;
        padding: 1rem 0;
        border-bottom: 3px solid #3b82f6;
    }
    
    h2, h3 {
        color: #334155;
        font-weight: 500;
    }
    
    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1e293b 0%, #334155 100%);
    }
    
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] label {
        color: #ffffff !important;
    }
    
    /* Sidebar Metrics - Special Styling */
    [data-testid="stSidebar"] [data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.2);
    }
    
    [data-testid="stSidebar"] [data-testid="stMetric"] label {
        color: #cbd5e1 !important;
    }
    
    [data-testid="stSidebar"] [data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #ffffff !important;
        font-weight: 700;
    }
    
    [data-testid="stSidebar"] [data-testid="stMetric"] [data-testid="stMetricDelta"] {
        color: #94a3b8 !important;
    }
    
    /* Sidebar Info/Success boxes */
    [data-testid="stSidebar"] .stAlert {
        background: rgba(255, 255, 255, 0.1) !important;
        color: #ffffff !important;
        border-left-color: #3b82f6 !important;
    }
    
    /* Metric Cards - Material Design */
    [data-testid="stMetric"] {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        border: 1px solid #e2e8f0;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    
    [data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.12);
    }
    
    [data-testid="stMetric"] label {
        font-size: 0.875rem;
        font-weight: 500;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    [data-testid="stMetric"] [data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 700;
        color: #1e293b;
    }
    
    /* Buttons - Material Design */
    .stButton > button {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.75rem 2rem;
        font-weight: 500;
        font-size: 1rem;
        box-shadow: 0 2px 6px rgba(59, 130, 246, 0.3);
        transition: all 0.3s ease;
        text-transform: none;
    }
    
    .stButton > button:hover {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
        transform: translateY(-1px);
    }
    
    .stButton > button:active {
        transform: translateY(0);
        box-shadow: 0 2px 4px rgba(59, 130, 246, 0.3);
    }
    
    /* Secondary Button */
    .stButton > button[kind="secondary"] {
        background: linear-gradient(135deg, #64748b 0%, #475569 100%);
        box-shadow: 0 2px 6px rgba(100, 116, 139, 0.3);
    }
    
    .stButton > button[kind="secondary"]:hover {
        background: linear-gradient(135deg, #475569 0%, #334155 100%);
        box-shadow: 0 4px 12px rgba(100, 116, 139, 0.4);
    }
    
    /* Input Fields */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div {
        border-radius: 8px;
        border: 1px solid #cbd5e1;
        background-color: white;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        transition: border-color 0.2s, box-shadow 0.2s;
    }
    
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus,
    .stSelectbox > div > div:focus-within {
        border-color: #3b82f6;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
    }
    
    /* DataFrames */
    [data-testid="stDataFrame"] {
        background: white;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        overflow: hidden;
        border: 1px solid #e2e8f0;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: white;
        padding: 1rem;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 0.75rem 1.5rem;
        font-weight: 500;
        background-color: transparent;
        border: none;
        color: #64748b;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: white;
        box-shadow: 0 2px 6px rgba(59, 130, 246, 0.3);
    }
    
    /* Info/Warning/Success/Error boxes */
    .stAlert {
        border-radius: 8px;
        border-left: 4px solid;
        box-shadow: 0 2px 6px rgba(0,0,0,0.08);
    }
    
    /* Divider */
    hr {
        margin: 2rem 0;
        border: none;
        border-top: 2px solid #e2e8f0;
    }
    
    /* Checkbox */
    .stCheckbox {
        padding: 0.5rem;
    }
    
    /* Multiselect */
    .stMultiSelect [data-baseweb="tag"] {
        background-color: #3b82f6;
        border-radius: 6px;
    }
    
    /* Custom Card Container */
    .custom-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        border: 1px solid #e2e8f0;
        margin-bottom: 1rem;
    }
    
    /* Header Banner */
    .header-banner {
        background: linear-gradient(135deg, #1e293b 0%, #334155 50%, #475569 100%);
        padding: 2rem;
        border-radius: 12px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        color: white;
        text-align: center;
    }
    
    .header-banner h1 {
        color: white;
        border: none;
        margin: 0;
        font-size: 2.5rem;
        text-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }
    
    .header-banner p {
        color: #cbd5e1;
        margin-top: 0.5rem;
        font-size: 1.1rem;
    }
    
    /* Scrollbar */
    ::-webkit-scrollbar {
        width: 10px;
        height: 10px;
    }
    
    ::-webkit-scrollbar-track {
        background: #f1f5f9;
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: #cbd5e1;
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: #94a3b8;
    }
    </style>
    """, unsafe_allow_html=True)

def header_banner():
    """Display professional header banner"""
    st.markdown("""
    <div class="header-banner">
        <h1>🔧 מערכת ניהול תקלות לוקרים</h1>
        <p>ממשק מקצועי לניהול ודיווח תקלות | Sidecar Architecture</p>
    </div>
    """, unsafe_allow_html=True)

# ============================================================================
# STREAMLIT APPLICATION
# ============================================================================

def main():
    st.set_page_config(
        page_title="מערכת ניהול תקלות לוקרים",
        page_icon="🔧",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Apply custom CSS
    local_css()
    
    # Display header banner
    header_banner()
    
    # Sidebar for database info
    with st.sidebar:
        st.header("📊 מידע על מסדי הנתונים")
        st.info("**PostgreSQL (קריאה בלבד)**\nנתוני תלמידים קיימים")
        st.success("**SQLite (כתיבה)**\nנתוני תקלות חדשים")
        
        # Database statistics
        try:
            students_df = get_students()
            faults = get_all_faults()  # Now returns list of objects
            
            st.metric("סה\"כ תלמידים", len(students_df))
            st.metric("סה\"כ תקלות", len(faults))
            st.metric("תקלות פתוחות", len([f for f in faults if f.status == 'Open']))
        except Exception as e:
            st.error(f"Error loading statistics: {e}")
        
        # Smart Scheduling Configuration
        st.divider()
        st.header("⚙️ הגדרות תזמון חכם")
        
        num_technicians = st.number_input(
            "מספר טכנאים זמינים",
            min_value=1,
            max_value=10,
            value=1,
            step=1,
            help="כמה טכנאים זמינים לטיפול בתקלות?"
        )
    
    # Main tabs
    tab1, tab2, tab3 = st.tabs(["📝 דיווח תקלה חדשה", "📋 צפייה בכל התקלות", "👥 רשימת תלמידים"])
    
    # TAB 1: Report New Fault
    with tab1:
        st.header("דיווח על תקלה חדשה")
        
        try:
            students_df = get_students()
            
            if students_df.empty:
                st.warning("לא נמצאו תלמידים במסד הנתונים.")
                return
            
            # Create student display name
            students_df['display_name'] = (
                students_df['fname'] + ' ' + 
                students_df['lname'] + ' | ת.ז: ' + 
                students_df['studentId'] + ' | ' + 
                students_df['school_name'].fillna('אין בית ספר')
            )
            
            # Student selection
            col1, col2 = st.columns([2, 1])
            
            with col1:
                selected_student_display = st.selectbox(
                    "בחר תלמיד",
                    options=students_df['display_name'].tolist(),
                    help="בחר את התלמיד המדווח על התקלה"
                )
                
                # Get selected student data
                selected_student = students_df[students_df['display_name'] == selected_student_display].iloc[0]
                student_id = selected_student['id']
                
                # Display student info
                st.info(f"**תלמיד:** {selected_student['fname']} {selected_student['lname']}\n\n"
                       f"**ת.ז:** {selected_student['studentId']}\n\n"
                       f"**כיתה:** {selected_student['class']}' {selected_student['classNumber']}\n\n"
                       f"**בית ספר:** {selected_student['school_name']}")
            
            with col2:
                # Get locker information
                locker_info = get_student_locker(student_id)
                
                if locker_info is not None:
                    st.success(f"**לוקר נמצא**\n\n"
                             f"**מספר:** #{locker_info['lockerNumber']}\n\n"
                             f"**מיקום:** {locker_info['complex_name']} - {locker_info['closet_name']}")
                    locker_id = locker_info['id']
                else:
                    st.warning("⚠️ לא משויך לוקר לתלמיד זה")
                    locker_id = None
            
            # Fault details form
            st.subheader("פרטי התקלה")
            
            col3, col4 = st.columns(2)
            
            with col3:
                fault_type = st.selectbox(
                    "סוג התקלה",
                    options=[
                        "תקלה במנעול",
                        "נזק לדלת",
                        "הקוד לא עובד",
                        "ספרים תקועים",
                        "מפתח אבוד",
                        "אחר"
                    ]
                )
            
            # ספרים תקועים
            books_stuck = st.checkbox("📚 יש ספרים תקועים בלוקר?", value=False, help="האם התלמיד צריך את הספרים בדחיפות?")
            
            description = st.text_area(
                "תיאור (אופציונלי)",
                placeholder="תאר את התקלה בפירוט (לא חובה)...",
                height=100
            )
            
            # Submit button
            if st.button("📤 שלח דיווח תקלה", type="primary", use_container_width=True):
                new_fault = save_fault(
                    student_id_ext=student_id,
                    locker_id=locker_id,
                    fault_type=fault_type,
                    books_stuck=books_stuck,
                    is_urgent=False,
                    description=description if description.strip() else None
                )
                
                if new_fault:
                    st.success(f"✅ תקלה #{new_fault['id']} דווחה בהצלחה!")
                    st.balloons()
                    st.rerun()
        
        except Exception as e:
            st.error(f"שגיאה בטעינת תלמידים: {e}")
            st.exception(e)
    
    # TAB 2: View All Faults
    with tab2:
        st.header("כל דיווחי התקלות")
        
        try:
            faults_with_info = get_faults_with_student_info()
            
            if faults_with_info.empty:
                st.info("עדיין לא דווחו תקלות.")
            else:
                # Filters
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    status_filter = st.multiselect(
                        "סינון לפי סטטוס",
                        options=faults_with_info['status'].unique(),
                        default=faults_with_info['status'].unique()
                    )
                
                with col2:
                    urgent_filter = st.selectbox(
                        "סינון לפי דחיפות",
                        options=["הכל", "דחופות בלבד", "לא דחופות"]
                    )
                
                with col3:
                    fault_type_filter = st.multiselect(
                        "סינון לפי סוג",
                        options=faults_with_info['fault_type'].unique(),
                        default=faults_with_info['fault_type'].unique()
                    )
                
                # Apply filters
                filtered_df = faults_with_info[faults_with_info['status'].isin(status_filter)]
                
                if urgent_filter == "דחופות בלבד":
                    filtered_df = filtered_df[filtered_df['books_stuck'] == True]
                elif urgent_filter == "לא דחופות":
                    filtered_df = filtered_df[filtered_df['books_stuck'] == False]
                
                if fault_type_filter:
                    filtered_df = filtered_df[filtered_df['fault_type'].isin(fault_type_filter)]
                
                # Display statistics
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("סה\"כ תקלות", len(filtered_df))
                col2.metric("דחופות", len(filtered_df[(filtered_df['books_stuck'] == True) & (filtered_df['status'] == 'Open')]))
                col3.metric("פתוחות", len(filtered_df[filtered_df['status'] == 'Open']))
                col4.metric("נפתרו", len(filtered_df[filtered_df['status'] == 'Resolved']))
                
                st.divider()
                
                # Display faults table
                display_df = filtered_df[[
                    'id', 'student_name', 'studentId', 'school_name',
                    'fault_type', 'severity', 'books_stuck', 'status', 
                    'description', 'created_at'
                ]].copy()
                
                # Format student ID for better display
                display_df['studentId'] = display_df['studentId'].astype(str)
                display_df['school_name'] = display_df['school_name'].fillna('לא ידוע')
                
                display_df.columns = [
                    'מזהה', 'שם התלמיד', 'ת.ז תלמיד', 'בית ספר',
                    'סוג תקלה', 'חומרה', 'ספרים תקועים', 'סטטוס', 
                    'תיאור', 'נוצר בתאריך'
                ]
                
                # טבלה אינטראקטיבית עם בחירת שורה
                event = st.dataframe(
                    display_df,
                    use_container_width=True,
                    hide_index=True,
                    on_select="rerun",
                    selection_mode="single-row",
                    column_config={
                        "חומרה": st.column_config.NumberColumn(
                            "חומרה",
                            help="רמת חומרה: 5=חמור ביותר, 1=קל",
                            format="⭐ %d"
                        ),
                        "ספרים תקועים": st.column_config.CheckboxColumn("ספרים תקועים"),
                        "נוצר בתאריך": st.column_config.DatetimeColumn(
                            "נוצר בתאריך",
                            format="DD/MM/YYYY HH:mm"
                        )
                    }
                )
                
                # אם נבחרה שורה - הצג dialog
                if event.selection.rows:
                    selected_row_index = event.selection.rows[0]
                    selected_fault_id = int(filtered_df.iloc[selected_row_index]['id'])
                    show_fault_details(selected_fault_id)
                
                st.divider()
                st.info("💡 לחץ על שורה בטבלה למעלה כדי לצפות ולערוך את פרטי התקלה")
                
                st.divider()
                
                # Export option
                if st.button("📥 ייצא ל-CSV"):
                    csv = display_df.to_csv(index=False)
                    st.download_button(
                        "הורד CSV",
                        csv,
                        "faults_report.csv",
                        "text/csv"
                    )
        
        except Exception as e:
            st.error(f"שגיאה בטעינת תקלות: {e}")
            st.exception(e)
    
    # TAB 3: Students List
    with tab3:
        st.header("מסד נתוני תלמידים (PostgreSQL - קריאה בלבד)")
        
        try:
            students_df = get_students()
            
            if students_df.empty:
                st.warning("לא נמצאו תלמידים.")
            else:
                # Search
                search_term = st.text_input("🔍 חיפוש תלמידים", placeholder="חפש לפי שם, ת.ז או אימייל...")
                
                if search_term:
                    mask = (
                        students_df['fname'].str.contains(search_term, case=False, na=False) |
                        students_df['lname'].str.contains(search_term, case=False, na=False) |
                        students_df['studentId'].str.contains(search_term, case=False, na=False) |
                        students_df['email'].str.contains(search_term, case=False, na=False)
                    )
                    filtered_students = students_df[mask]
                else:
                    filtered_students = students_df
                
                st.info(f"מציג {len(filtered_students)} מתוך {len(students_df)} תלמידים")
                
                # Display students
                display_students = filtered_students[[
                    'fname', 'lname', 'studentId', 'class', 'classNumber',
                    'parentPhone', 'email', 'school_name'
                ]].copy()
                
                display_students.columns = [
                    'שם פרטי', 'שם משפחה', 'ת.ז', 'כיתה', 'מספר בכיתה',
                    'טלפון הורה', 'אימייל', 'בית ספר'
                ]
                
                st.dataframe(
                    display_students,
                    use_container_width=True,
                    hide_index=True
                )
        
        except Exception as e:
            st.error(f"שגיאה בטעינת תלמידים: {e}")
            st.exception(e)

if __name__ == "__main__":
    main()
