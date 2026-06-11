#!/usr/bin/env python
# coding: utf-8

# In[ ]:

from flask import Flask, request, render_template, redirect, url_for, session, jsonify, send_from_directory, flash, send_file
import pymysql.cursors
import logging
import pandas as pd
import os
import threading
import boto3
import json
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import requests
import shutil
from db_connect.mysql_handler import *
from argon2 import PasswordHasher
from argon2.low_level import Type
import sys
import uuid
import zipfile
from s3_helpers import (read_json_s3, write_json_s3, get_bytes_s3, put_bytes_s3,
                        delete_key_s3, upload_file_s3, s3_key_exists)


###########################################################JPMS-JSON###########################################################





APP_PUBLIC_URL = os.environ.get("APP_PUBLIC_URL", "http://localhost:5000")
JWT_ENABLED = False
JWT_SECRET = "my_jwt_secret"  # only needed if JWT_ENABLED=True
 
###############################################################################################################################

#iniializing logger 


jpms_logger = logging.getLogger("JPMS")
jpms_logger.setLevel(logging.DEBUG)
aaa_logger = logging.getLogger("AAA")
aaa_logger.setLevel(logging.DEBUG)
jpms_logger.info("JPMS APP HAS STARTED")


#iniializing flask app
app = Flask(__name__)
_sm = boto3.client("secretsmanager", region_name=os.environ.get("AWS_REGION", "ap-south-1"))
app.secret_key = json.loads(_sm.get_secret_value(SecretId=os.environ["APP_SECRET_ID"])["SecretString"])["flask_secret_key"]
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=int(os.environ.get("SESSION_LIFETIME_DAYS", "1")))



#creating the directory for storing tmp file 
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
Temp_DIR = os.path.join(BASE_DIR, "tmp")
os.makedirs(Temp_DIR, exist_ok=True)

#getting the Databaase IP info 
base_dir = os.path.dirname(os.path.abspath(__file__))  # path to mysql_handler.py
# Single-RDS deployment: multi-company encrypted config (.enc/secret.key) removed.
# CONFIG only supplies the cache-namespace key(s) used by the Redis cache loop below.
COMPANY = os.environ.get("COMPANY", "jio")
CONFIG = {COMPANY: {}}

FOLDER_LIST = [
    "Bill of Quantity(BOQ)",
    "Deployment Guideline", "Field Test", 
    "Golden Parameter Audit", "Inventory Format", "Key Performance Indicator (KPI)", "Material Availability",
    "Material Dispatch", "Nominal Site List", "Office Dependent Database (ODD)","Project Management", "Site Database",
    "Site Dispatch Plan", "Site Survey", "SW Upgrade","Validation Testing Guideline","VTP Report"
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s"
)



# ############################################################################## variables Declaration #######################################################################
print("IMS_backend has started", flush=True)

###########################################################################utility functions########################################################################################
def clean_df_for_mysql(df):
    # Replace NaN with None
    df = df.where(pd.notna(df), None)

    # Replace blank strings ("" or strings with only spaces) with None
    df = df.applymap(lambda x: None if isinstance(x, str) and x.strip() == "" else x)

    return df        

    
def get_client_ip():
    # Honor reverse proxy
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote_addr
###################################################################################Logger code##################################################################################
@app.before_request
def log_incoming_request():
    jpms_logger.debug(f"Incoming {request.method} {request.path} from {request.remote_addr}")
    session.permanent = True
    if "kpi-automation/status" in request.path or "kpi-automation/pending" in request.path or "kpi-automation/job-params" in request.path:
        return None
    public_endpoints = ("home", "landing_page", "login", "static", "submit_query", "download_file_onlyoffice", "onlyoffice_callback", "api_kpi_automation_status", "api_kpi_automation_pending", "upload_kpi_automation", "get_kpi_job_params")
    if request.endpoint not in public_endpoints:
        if "username" not in session:
            
            aaa_logger.info(f"Timestamp:{datetime.now()}|SourceIP:{get_client_ip()}|Username:Unknown|SessionId:NA|Activity Performed:Session_timeout|Activity Status:Successfull_Logout")
            return redirect(url_for('landing_page',next=request.path))

@app.after_request
def log_response(response):
    jpms_logger.debug(f"Responded with {response.status} to {request.method} {request.path}")
    return response 
#####################################################################################User_info_encryption#########################################################################

# Configure Argon2id (no extra keys/pepper needed)
ph = PasswordHasher( 
    time_cost=3,
    memory_cost=64_000,  # ~64 MB
    parallelism=2,
    hash_len=32,
    type=Type.ID,
)

def hash_plaintext(plaintext):

    try:
        new_hash = ph.hash(plaintext)  # random salt embedded in hash string
        return new_hash
    except Exception as e:
        print(f"error While hashing the plain text:{e}")

def check_password(stored_hash, user_entered_password):
    try:
        ph.verify(stored_hash, user_entered_password)   # ← uses salt/params embedded in stored_hash
        return True
    except Exception as e:
        print(f"error While hashing the plain text:{e}") 
        return False
        
def check_for_hashing():
    
    company = session.get('company')
	# Replace with your actual user verification logic
    conn = get_db_connection(company)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    # Ensure the user table exists (fresh RDS won't have it; created like kpi_automation)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ims_user_details (
            userid            INT AUTO_INCREMENT PRIMARY KEY,
            username          VARCHAR(100) UNIQUE,
            password          VARCHAR(255),
            Name              VARCHAR(150),
            Class             VARCHAR(50),
            Team              VARCHAR(50),
            status            VARCHAR(50) DEFAULT 'Active',
            automation_access VARCHAR(255),
            is_hashed         TINYINT(1) DEFAULT 0
        )
    """)
    cursor.execute("SELECT * FROM ims_user_details WHERE is_hashed = %s", (0,))
    rows = cursor.fetchall()
    cols = [c[0] for c in cursor.description]   # keeps column order even if rows=[]
    df = pd.DataFrame(rows, columns=cols)
	
    pwd = df[df['password'].astype('string').notna()][['userid','password']]
    
    
    hashed_pwd = []
    if not pwd.empty:
        for _,row in pwd.iterrows():
            hashed_pwd.append((hash_plaintext(row['password']), row['userid']))
    else:
        print("All passwords have been hashed")
    cursor.executemany(
        "UPDATE ims_user_details SET password=%s, is_hashed=1 WHERE userid=%s",
        hashed_pwd
    )
    conn.commit()        
    cursor.close()
    conn.close()
     


            
#######################################################################################
#####################################################################################Home page URL#######################################################################               
@app.route('/landing')
def home():
    next_page = request.args.get('next_page')
    print(f"I am printing the bext page{next_page}")
    company = request.args.get('company')
    print(f"i am printing the selection {company}")
    if company:
        session['company'] = company
        check_for_hashing()
    try:
        return render_template('IMSlogin.html',next_page = next_page,selected_company=company)  # This ensures proper URL loading
    except Exception as e:
        app.logger.error(f"Error loading template: {str(e)}")  # Log the error
        return "An error occurred. Check the logs.", 500

        
@app.route('/login', methods=['GET', 'POST'])
def login():
    
    if request.method == 'POST':
        
        next_page = request.form.get('next_page')
        username = request.form['username']
        password = request.form['password']
        company = session.get('company')
        print(f"next_page is {next_page,company}")
        if company == None:
            return render_template('IMSlogin.html',next_page = next_page,error="Please select the Project before entering the credentials")
        ip_address = request.remote_addr
        
       
        # Replace with your actual user verification logic
        conn = get_db_connection(company)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT * FROM ims_user_details WHERE username = %s",username)
        user_info = cursor.fetchone()
        
        if user_info['status'] == 'Disabled':
            return render_template('IMSlogin.html', next_page=next_page, error="Your Account is Expired. Please contact with JPMS Team.")
        
        if user_info is None:
            # User not found in database
            cursor.close()
            conn.close()
            return render_template('IMSlogin.html', next_page=next_page, error="User not found. Please check your username.")
        
        
        hashed_password = user_info['password'] 
        valid_user = check_password(hashed_password,password)
        cursor.close()
        conn.close()
        if valid_user == True:
        
            # Save the username in session
            session['username'] = user_info['username']
            session['Name'] = user_info['Name']
            session['company'] = company
            session['Class'] = user_info.get('Class')
            session['Team'] = user_info.get('Team')
            session['sid'] = uuid.uuid4()
            aaa_logger.info(f"Timestamp:{datetime.now()}|SourceIP:{get_client_ip()}|Username:{session.get('username')}|SessionId:{session.get('sid')}|Activity Performed:Login|Activity Status:Successfull_Login")
            if next_page == "None":
                # land the user directly on the KPI Automation page
                return redirect(url_for('kpi'))
            else:
                return redirect(next_page)
        else:
            # Invalid credentials
            session['username'] = user_info['username']
            session['sid'] = uuid.uuid4()
            aaa_logger.info(f"Timestamp:{datetime.now()}|SourceIP:{get_client_ip()}|Username:{session['username']}|SessionId:{session['sid']}|Activity Performed:Login|Activity Status:Failed_login")
            return render_template('IMSlogin.html', next_page = next_page, error="Invalid username or password")
    
    # When user first comes to /login (GET), show login form
    return render_template('IMSlogin.html')


@app.route('/submit_query', methods=['POST'])
def submit_query():
    print("submit_query called")
    conn = None
    cursor = None

    try:
        # Accept both FormData POST or JSON
        email = request.form.get('email') or request.json.get('email')
        username = request.form.get('username') or request.json.get('username')
        query = request.form.get('query') or request.json.get('query')

        if not email or not username or not query:
            return jsonify({"status": "error", "message": "All fields are required."}), 400

        conn = get_db_connection("jpms_admin")
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO query_module (email, username, query)
            VALUES (%s, %s, %s)
        """, (email, username, query))

        conn.commit()

        return jsonify({"status": "success"}), 200

    except Exception as e:
        print("❌ ERROR in submit_query:", str(e))
        return jsonify({"status": "error", "message": "Server error"}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()        

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        # You can later send reset email or show message here
        return render_template('forgot_password.html', message="🔗 A reset link has been sent to your email.")
    return render_template('forgot_password.html')

####################################################### Landing Page #################################################################################

@app.route('/')
def landing_page():
    next_page = request.args.get('next')
    #print(f"I am prining nextpage {next_page}")
    return render_template('IMSlogin.html',next_page=next_page)     



@app.route('/logout')
def logout():
    ip_address = request.remote_addr
    aaa_logger.info(f"Timestamp:{datetime.now()}|SourceIP:{get_client_ip()}|Username:{session.get('username')}|SessionId:{session.get('sid')}|Activity Performed:Logout|Activity Status:Successfull_Logout")
    session.clear()
    
       #Clear session
    return redirect(url_for('landing_page'))  # Redirect to login page



####################################################################Automation SECTION######################################################

@app.route('/automation-module')
def automation_module():
    user_logged_in = 'username' in session
    name = session.get('Name', 'Guest')
    return render_template('automation_module.html' ,user_logged_in=user_logged_in, name=name)







########################################################################### Automation_Module ####################################

@app.route('/check-access/<int:box_number>')
def check_access(box_number):
    if 'username' not in session:
        return {"allowed": False, "reason": "not logged in"}

    username = session.get('username')
    company = session.get('company', 'jio')

    conn = get_db_connection(company)
    cursor = conn.cursor()  # IMPORTANT

    cursor.execute(
        "SELECT automation_access FROM ims_user_details WHERE username = %s",
        (username,)
    )
    result = cursor.fetchone()
    
    
    conn.close()
    

    # If user not found or column empty
    if not result or not result["automation_access"]:
        access_list = []
    else:
        access_string = result["automation_access"]  # e.g. "1,2,3"
        access_list = [x.strip() for x in access_string.split(",")]

    if str(box_number) in access_list:
        return {"allowed": True}
    else:
        return {"allowed": False}

#################################################################### 5G gNodeB Weekly Progress Report ######################################################
@app.route('/automation-module/kpi-automation')
def kpi():
    user_logged_in = 'username' in session
    name = session.get('Name', 'Guest')
    if 'username' not in session:
        return redirect(url_for('landing_page', next=request.path))
    company = session.get('company', 'jio')
    kpi_reports = []
    try:
        conn = get_db_connection(company)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS kpi_automation (
                job_id VARCHAR(100) PRIMARY KEY,
                template_id VARCHAR(100),
                created_by VARCHAR(100),
                uploaded_at DATETIME,
                started_at DATETIME,
                finished_at DATETIME,
                input_filename VARCHAR(255),
                status VARCHAR(50),
                error_message TEXT,
                is_deleted TINYINT(1) DEFAULT 0,
                trend_status VARCHAR(50) DEFAULT 'idle',
                is_trend_updated TINYINT(1) DEFAULT 0,
                post_processed TINYINT(1) DEFAULT 0
            )
        """)
        cursor.execute("SELECT * FROM kpi_automation WHERE is_deleted = 0 ORDER BY uploaded_at DESC")
        kpi_reports = []
        for row in cursor.fetchall():
            d = dict(row)
            for k in ('uploaded_at', 'started_at', 'finished_at'):
                if d.get(k) and hasattr(d[k], 'strftime'):
                    d[k] = d[k].strftime("%Y-%m-%d %H:%M:%S")
            kpi_reports.append(d)
        cursor.close()
        conn.close()
    except Exception:
        pass
    return render_template('kpi_automation.html',
                          user_logged_in=user_logged_in,
                          name=name,
                          kpi_reports=kpi_reports)

@app.route('/api/kpi-automation/job-params/<job_id>', methods=['GET'])
def get_kpi_job_params(job_id):
    company = request.headers.get('X-KPI-Company', 'jio')
    try:
        conn = get_db_connection(company)
        cursor = conn.cursor()
        cursor.execute("SELECT post_processed FROM kpi_automation WHERE job_id = %s", (job_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if row:
            # post_processed is TINYINT(1) (0/1)
            return jsonify({
                "status": "success",
                "job_id": job_id,
                "post_process": bool(row.get('post_processed', 0))
            })
        else:
            return jsonify({"status": "error", "message": "Job not found"}), 404
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500



# ==============================
# KPI Automation – Upload Handler
# Stores CSV + meta.json on 89 server
# ==============================

# S3 key prefixes (replaces the Z:\ network drive)
KPI_INPUT_PREFIX     = "inputs"
KPI_OUTPUT_PREFIX    = "outputs"
MAPPING_KEY          = "mapping.json"
TEMPLATES_CONFIG_KEY = "templates_config.json"
TEMPLATES_PREFIX     = "templates/prepost"

# SQS queue used to dispatch automation jobs to the worker fleet (ASG).

SQS_QUEUE_URL = os.environ["SQS_QUEUE_URL"]
_sqs_client = None
def get_sqs():
    global _sqs_client
    if _sqs_client is None:
        _sqs_client = boto3.client("sqs", region_name=os.environ.get("AWS_REGION", "ap-south-1"))
    return _sqs_client


def generate_kpi_job_id() -> str:
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    rand = uuid.uuid4().hex[:6].upper()
    return f"KPI_{now}_{rand}"


@app.route('/upload-kpi-automation', methods=['POST'])
def upload_kpi_automation():
    """
    Handles KPI Automation form submit:
    - Receives kpi_file (CSV) + template_id
    - Creates inputs/jobs/<job_id>/ on 89
    - Saves kpi_input.csv and meta.json
    """
    is_localhost = request.remote_addr in ('127.0.0.1', 'localhost', '::1')
    if 'username' not in session and not is_localhost:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    # Prioritize form data (for automation) over session data
    username = request.form.get('username') or session.get('username', 'Yug.Patel')
    company = request.form.get('company') or session.get('company', 'jio')


    kpi_file = request.files.get('kpi_file')
    template_id = request.form.get('template_id')
    report_type = request.form.get('report_type', 'daily')
    jcp_format_str = request.form.get('jcp_format', 'false')
    jcp_format = True if jcp_format_str.lower() == 'true' else False
    post_process_str = request.form.get('post_process', 'false')
    post_process = True if post_process_str.lower() == 'true' else False


    if not kpi_file or kpi_file.filename == "":
        return jsonify({"status": "error", "message": "CSV file (kpi_file) is required"}), 400
    if not template_id:
        return jsonify({"status": "error", "message": "template_id is required"}), 400

    # Generate job id
    job_id = generate_kpi_job_id()

    # Save CSV to a temp local file first (pandas normalizes it below, then we upload to S3)
    import tempfile
    safe_name = secure_filename(kpi_file.filename) or "kpi_input.csv"
    csv_path = os.path.join(tempfile.gettempdir(), f"{job_id}_kpi_input.csv")
    csv_key  = f"{KPI_INPUT_PREFIX}/{job_id}/kpi_input.csv"
    try:
        kpi_file.save(csv_path)

        # --- Date & Time Normalization ---
        try:
            import pandas as pd
            df = pd.read_csv(csv_path, low_memory=False)
            updated = False
            
            # Replace all variants of blank/empty/nan with '-' as strictly requested
            df.fillna('-', inplace=True)
            df.replace(to_replace=['', ' ', 'nan', 'NaN', 'None', 'null', 'Nil'], value='-', inplace=True)
            updated = True
            
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'], format='mixed', dayfirst=True).dt.strftime('%d-%m-%Y')
                updated = True
                
            if 'Time' in df.columns:
                time_str = df['Time'].astype(str).str.replace('.', ':', regex=False)
                df['Time'] = pd.to_datetime(time_str, format='mixed', errors='coerce').dt.strftime('%H:%M')
                df['Time'] = df['Time'].fillna('00:00')
                updated = True

             # Standardize 'Cell' column presence
            if 'Cell' not in df.columns:
                cell_aliases = ['Cell ID']
                for alias in cell_aliases:
                    if alias in df.columns:
                        df.rename(columns={alias: 'Cell'}, inplace=True)
                        updated = True
                        break
                
            if updated:
                df.to_csv(csv_path, index=False)
        except Exception as norm_err:
            print(f"Warning: Failed to normalize Date/Time formats for {csv_path}: {norm_err}")

        # Upload the (normalized) CSV to S3, then remove the temp file
        upload_file_s3(csv_path, csv_key)
        try:
            os.remove(csv_path)
        except Exception:
            pass
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error saving CSV: {e}"}), 500    
            

    # Prepare metadata
    company = session.get('company', 'jio')
    uploaded_at = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
    started_at = uploaded_at

    # Save meta.json with template_id and basic info
    meta = {
        "job_id": job_id,
        "template_id": template_id,
        "report_type": report_type,
        "jcp_format": jcp_format,
        "post_process": post_process,
        "original_filename": safe_name,
        "created_by": username,
        "company": company,
        "uploaded_at": uploaded_at,
        "created_at": uploaded_at
    }

    try:
        write_json_s3(f"{KPI_INPUT_PREFIX}/{job_id}/meta.json", meta)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error writing meta.json: {e}"}), 500
    # Insert record into kpi_automation table
    try:
        conn = get_db_connection(company)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO kpi_automation 
            (job_id, template_id, created_by, uploaded_at, started_at, finished_at, input_filename, status, is_deleted, post_processed)
            VALUES (%s, %s, %s, %s, %s, NULL, %s, 'Queued', 0, %s)
        """, (job_id, template_id, username, uploaded_at, started_at, safe_name, 1 if post_process else 0))
   
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to save job record: {e}"}), 500

    # Enqueue the job to SQS — the automation worker fleet (ASG) picks it up.
   
    try:
        get_sqs().send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=json.dumps({"job_id": job_id, "company": company})
        )
    except Exception as e:
        
        return jsonify({
            "status": "queued",
            "job_id": job_id,
            "message": f"Job saved but failed to enqueue to SQS: {e}"
        }), 200

    return jsonify({
        "status": "queued",
        "job_id": job_id,
        "message": "Job queued for processing"
    }), 200


@app.route('/api/kpi-automation/status', methods=['POST'])
def api_kpi_automation_status():
    """Called by JCP 241 to update job status, started_at, finished_at. No session required."""
    data = request.get_json() or {}
    job_id = data.get("job_id")
    status_val = data.get("status")
    error_msg = data.get("error_message")
    started_at = data.get("started_at")
    finished_at = data.get("finished_at")

    if not job_id or not status_val:
        return jsonify({"error": "job_id and status required"}), 400

    company = request.headers.get('X-KPI-Company') or session.get('company', 'jio') or 'jio'
    try:
        conn = get_db_connection(company)
        cursor = conn.cursor()
        updates = ["status = %s"]
        params = [status_val]
        now_ist = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
        if status_val == "Running":
            updates.append("started_at = %s")
            params.append(now_ist)
        elif status_val in ("Finished", "Success", "Failed"):
            updates.append("finished_at = %s")
            params.append(now_ist)
        
        if error_msg is not None:
            updates.append("error_message = %s")
            params.append(error_msg)
        params.append(job_id)
        cursor.execute(
            f"UPDATE kpi_automation SET {', '.join(updates)} WHERE job_id = %s",
            params
        )
        conn.commit()
        cursor.close()
        conn.close()
     
        
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/kpi-automation/jobs', methods=['GET'])
def api_kpi_automation_jobs():
    """Returns job list as JSON for frontend polling."""
    if 'username' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    company = session.get('company', 'jio')
    try:
        conn = get_db_connection(company)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM kpi_automation WHERE is_deleted = 0 ORDER BY uploaded_at DESC")
        rows = cursor.fetchall()
        # Convert datetime to ISO string for JSON
        jobs = []
        for r in rows:
            d = dict(r)
            for k in ('uploaded_at', 'started_at', 'finished_at'):
                if d.get(k) and hasattr(d[k], 'strftime'):
                    d[k] = d[k].strftime("%Y-%m-%d %H:%M:%S")
            jobs.append(d)
        cursor.close()
        conn.close()
        return jsonify({"jobs": jobs})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/kpi-automation/templates', methods=['GET'])
def get_automation_templates():
    data = read_json_s3(TEMPLATES_CONFIG_KEY)
    if data is not None:
        return jsonify({"status": "success", "templates": data})
    return jsonify({"status": "error", "message": "Config not found"}), 404

@app.route('/modify-template', methods=['POST'])
def modify_template():
    action = request.form.get('template_action')
    base_template_id = request.form.get('edit_template_id')
    new_template_name = request.form.get('new_template_name')

    file = request.files.get('template_file')
    if not file or file.filename == '':
        flash("No template file selected.")
        return redirect(request.referrer)

    try:
        config = read_json_s3(TEMPLATES_CONFIG_KEY) or {}

        from werkzeug.utils import secure_filename
        sec_name = secure_filename(file.filename)
        filename_only, ext = os.path.splitext(sec_name)
        timestamp_str = datetime.now().strftime("%Y%m%d")
        final_filename = f"{filename_only}_{timestamp_str}{ext}"
        final_key = f"{TEMPLATES_PREFIX}/{final_filename}"

        if action == 'edit':
            if not base_template_id or base_template_id not in config:
                flash("Invalid template selected for editing.")
                return redirect(request.referrer)

            old_filename = config[base_template_id]
            put_bytes_s3(final_key, file.read())          # upload new file to S3
            config[base_template_id] = final_filename
            write_json_s3(TEMPLATES_CONFIG_KEY, config)

            if old_filename and old_filename != final_filename:
                try:
                    delete_key_s3(f"{TEMPLATES_PREFIX}/{old_filename}")
                except Exception as ex:
                    print(f"Failed to delete old template {old_filename}: {ex}")
            flash("Template successfully updated!", "success")

        elif action == 'create':
            if not new_template_name:
                flash("Please provide a name for the new template.")
                return redirect(request.referrer)
            put_bytes_s3(final_key, file.read())
            config[new_template_name] = final_filename
            write_json_s3(TEMPLATES_CONFIG_KEY, config)
            flash("New template successfully created and mapped!", "success")

        return redirect(request.referrer)
    except Exception as e:
        flash(f"Error modifying template: {str(e)}")
        return redirect(request.referrer)

@app.route('/api/kpi-automation/get-mapping', methods=['GET'])
def get_kpi_mapping():
    """Reads mapping.json from S3 and returns it as JSON."""
    data = read_json_s3(MAPPING_KEY)
    if data is not None:
        return jsonify({"status": "success", "content": data})
    return jsonify({"status": "error", "message": "mapping.json not found"}), 404

@app.route('/api/kpi-automation/update-mapping', methods=['POST'])
def update_kpi_mapping():
    """Updates mapping.json on 89 server with content from frontend."""
    if 'username' not in session:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
        
    try:
        data = request.get_json()
        if not data or 'content' not in data:
            return jsonify({"status": "error", "message": "Missing content"}), 400

        new_content = data['content']
        if not isinstance(new_content, dict):
             return jsonify({"status": "error", "message": "Content must be a valid JSON object"}), 400

        write_json_s3(MAPPING_KEY, new_content)

        username = session.get('username')
        jpms_logger.info(f"User {username} updated mapping.json in S3")

        return jsonify({"status": "success", "message": "Mapping updated successfully"})
    except json.JSONDecodeError as je:
        return jsonify({"status": "error", "message": f"Invalid JSON format: {str(je)}"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error updating mapping: {str(e)}"}), 500




@app.route('/api/kpi-automation/download-template/<template_id>', methods=['GET'])
def download_kpi_template(template_id):
    data = read_json_s3(TEMPLATES_CONFIG_KEY)
    if data is None:
        return jsonify({"status": "error", "message": "Config not found"}), 404
    if template_id not in data:
        return jsonify({"status": "error", "message": "Template ID not found"}), 404

    filename = data[template_id]
    key = f"{TEMPLATES_PREFIX}/{filename}"
    if not s3_key_exists(key):
        return "Template file does not exist in S3", 404
    return send_file(get_bytes_s3(key), as_attachment=True, download_name=filename)

@app.route('/api/kpi-automation/pending', methods=['GET'])
def api_kpi_automation_pending():
    """Returns list of pending (Queued) jobs. Used by Job Picker on 241."""
    company = request.args.get('company', 'jio')
    try:
        conn = get_db_connection(company)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT job_id FROM kpi_automation 
            WHERE status = 'Queued' AND is_deleted = 0 
            ORDER BY uploaded_at ASC
        """)
        rows = cursor.fetchall()
        job_ids = [r['job_id'] for r in rows]
        cursor.close()
        conn.close()
        return jsonify({"pending_jobs": job_ids})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/delete-kpi-job/<job_id>', methods=['POST'])
def delete_kpi_job(job_id):
    if 'username' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    company = session.get('company', 'jio')
    try:
        conn = get_db_connection(company)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE kpi_automation SET is_deleted = 1 WHERE job_id = %s",
            (job_id,)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/download-kpi-report/<job_id>')
def download_kpi_report(job_id):
    if 'username' not in session:
        return redirect(url_for('landing_page'))

    key = f"{KPI_OUTPUT_PREFIX}/{job_id}/{job_id}.zip"
    if s3_key_exists(key):
        return send_file(get_bytes_s3(key), as_attachment=True,
                         download_name=f"{job_id}.zip")
    return "Zip report not found or not yet generated", 404
        
@app.route('/download-process-report/<job_id>')
def download_process_report(job_id):
    if 'username' not in session:
        return redirect(url_for('landing_page'))

    key = f"{KPI_OUTPUT_PREFIX}/{job_id}/{job_id}_processed/{job_id}_processed.zip"
    if s3_key_exists(key):
        return send_file(get_bytes_s3(key), as_attachment=True,
                         download_name=f"{job_id}_processed.zip")
    return "Zip report not found or not yet generated", 404
        


def create_zip_for_processed_files(job_id, processed_dir):
    """Creates a ZIP file of the processed folder"""
    try:
        if not os.path.exists(processed_dir):
            print(f"❌ Cannot ZIP: Directory {processed_dir} does not exist.")
            return

        zip_filename = f"{job_id}_processed.zip"
        # We save the ZIP inside the processed_dir as requested
        zip_path = os.path.join(processed_dir, zip_filename)

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in os.listdir(processed_dir):
                # ZIP everything in the folder EXCEPT the zip file itself
                if not file.endswith(".zip"):
                    file_path = os.path.join(processed_dir, file)
                    zipf.write(file_path, arcname=file)

        print(f"📦 Successfully created ZIP: {zip_path}")
        return zip_path

    except Exception as e:
        print(f"❌ ZIP creation error: {str(e)}")
    

def process_job_output(job_id):
    """
    Process Excel files for a given job from KPI_OUTPUT_JOBS_PATH
    and save processed files to {job_id}_processed folder.
    """
    job_output_dir = os.path.join(KPI_OUTPUT_JOBS_PATH, job_id)
    processed_dir = os.path.join(job_output_dir, f"{job_id}_processed")
    os.makedirs(processed_dir, exist_ok=True)

    # Look for ZIP files in job output folder
    for f in os.listdir(job_output_dir):
        if f.endswith(".zip"):
            zip_path = os.path.join(job_output_dir, f)
            unzip_and_process(zip_path, processed_dir)

    # Also, process any Excel files already in output folder
    for f in os.listdir(job_output_dir):
        if f.endswith(".xlsx"):
            file_path = os.path.join(job_output_dir, f)
            try:
                print(f"Processing Excel file: {file_path}")
                process_excel(file_path)

                # Save processed file to processed_dir
                dest_path = os.path.join(processed_dir, f)
                shutil.copy(file_path, dest_path)
                print(f"Saved processed file to: {dest_path}")
            except Exception as e:
                print(f"Error processing {file_path}: {e}")


def unzip_and_process(zip_path, processed_dir, job_output_dir, job_id, company):
    """Unzip the ZIP file, process Excel files, save to processed_dir, and update DB"""

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(job_output_dir)  # ✅ extract inside job folder

    # Process extracted Excel files
    for root, dirs, files in os.walk(job_output_dir):
        for file in files:
            if file.endswith(".xlsx"):
                file_path = os.path.join(root, file)
                try:
                    print(f"Processing extracted Excel file: {file_path}")
                    
                    process_excel(file_path)

                    # ✅ Copy to processed_dir
                    dest_path = os.path.join(processed_dir, file)
                    shutil.copy(file_path, dest_path)

                    print(f"Saved processed file to: {dest_path}")

                except Exception as e:
                    print(f"Error processing {file_path}: {e}")

    # ✅ STEP 1: Create the ZIP file
    create_zip_for_processed_files(job_id, processed_dir)

    # ✅ STEP 2: Database Connection Logic
    try:
        print(f"Updating database status for Job ID: {job_id}")
        conn = get_db_connection(company)
        cursor = conn.cursor()
        
        # Update the specific table and column
        query = "UPDATE kpi_automation SET post_processed = 1 WHERE job_id = %s"
        cursor.execute(query, (job_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        print(f"✅ Database updated successfully: post_processed = 1")
    except Exception as e:
        print(f"❌ Database update error: {e}")


if __name__ == '__main__':
    port = 5010
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("Invalid port. Using default 5010.")

    
    
    print(f"Flask is starting on port {port}/")
    
    app.run(host='0.0.0.0', port=port)   # local dev only — Gunicorn imports `app` directly