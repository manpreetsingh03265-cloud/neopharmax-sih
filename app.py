import os, sqlite3, hashlib, secrets
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, send_file
from werkzeug.utils import secure_filename

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "neopharmax.db")
UPLOAD_DIR = os.path.join(BASE, "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "neopharmax-demo-change-this-secret")


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def now():
    return datetime.now().isoformat(timespec="seconds")


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def add_column_if_missing(con, table, column, definition):
    cols = {r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL, role TEXT DEFAULT 'physician',
      patient_code TEXT, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS patients(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      patient_code TEXT UNIQUE NOT NULL,
      user_id INTEGER,
      name TEXT NOT NULL, age INTEGER, sex TEXT, phone TEXT, address TEXT,
      weight REAL, height REAL, complaint TEXT, condition TEXT,
      medications TEXT, allergies TEXT, history TEXT,
      abha_id TEXT, language TEXT DEFAULT 'English', symptoms TEXT,
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS ai_requests(
      id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id INTEGER,
      symptoms TEXT NOT NULL, result TEXT NOT NULL, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS appointments(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      patient_id INTEGER NOT NULL, physician_id INTEGER,
      appointment_date TEXT NOT NULL, appointment_time TEXT NOT NULL,
      reason TEXT, status TEXT DEFAULT 'Requested', created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS connections(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      patient_id INTEGER NOT NULL, physician_id INTEGER NOT NULL,
      connection_code TEXT UNIQUE NOT NULL, status TEXT DEFAULT 'Active',
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS reports(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      patient_id INTEGER NOT NULL, filename TEXT NOT NULL,
      original_name TEXT NOT NULL, category TEXT DEFAULT 'Medical Report',
      uploaded_at TEXT NOT NULL
    );
    """)

    # Safe migration for an older copy of the prototype.
    add_column_if_missing(con, "users", "patient_code", "TEXT")
    add_column_if_missing(con, "patients", "user_id", "INTEGER")
    add_column_if_missing(con, "patients", "abha_id", "TEXT")
    add_column_if_missing(con, "patients", "language", "TEXT DEFAULT 'English'")
    add_column_if_missing(con, "patients", "symptoms", "TEXT")

    con.execute("UPDATE users SET role='physician' WHERE email='demo@neopharmax.local'")
    physician = con.execute("SELECT id FROM users WHERE email=?", ("demo@neopharmax.local",)).fetchone()
    if not physician:
        con.execute(
            "INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)",
            ("Manpreet Singh", "demo@neopharmax.local", hash_password("demo123"), "physician", now())
        )

    # Keep the original demo records if they already exist.
    if con.execute("SELECT COUNT(*) FROM patients").fetchone()[0] == 0:
        seed = [
          ("Rahul Mehta",28,"Male","Fever"),("Simran Kaur",34,"Female","Hypertension"),
          ("Arjun Verma",19,"Male","Respiratory"),("Neha Sharma",45,"Female","Diabetes"),
          ("Karan Singh",52,"Male","Joint Pain"),("Pooja Nair",26,"Female","Gastritis"),
          ("Aditya Rao",39,"Male","Hypertension"),("Fatima Ali",31,"Female","Migraine"),
          ("Vikram Das",60,"Male","Diabetes"),("Ananya Sen",24,"Female","UTI")]
        for i,(name,age,sex,cond) in enumerate(seed,1):
            con.execute("""INSERT INTO patients(patient_code,name,age,sex,condition,created_at,updated_at)
                           VALUES(?,?,?,?,?,?,?)""", (f"P-{i:03d}",name,age,sex,cond,now(),now()))

    # Create a patient-side demo account and link it to a patient record.
    patient_user = con.execute("SELECT * FROM users WHERE email=?", ("patient@neopharmax.local",)).fetchone()
    patient_row = con.execute("SELECT * FROM patients WHERE patient_code='NPX-000001'").fetchone()
    if not patient_row:
        con.execute("""INSERT INTO patients(patient_code,name,age,sex,phone,condition,language,created_at,updated_at)
                       VALUES(?,?,?,?,?,?,?,?,?)""",
                    ("NPX-000001","Demo Patient",25,"Female","+91 90000 00000","General Consultation","English",now(),now()))
        patient_row = con.execute("SELECT * FROM patients WHERE patient_code='NPX-000001'").fetchone()
    if not patient_user:
        con.execute("""INSERT INTO users(name,email,password_hash,role,patient_code,created_at)
                       VALUES(?,?,?,?,?,?)""",
                    ("Demo Patient","patient@neopharmax.local",hash_password("patient123"),"patient","NPX-000001",now()))

    con.commit(); con.close()


def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if "user_id" not in session:
            return jsonify({"error":"Authentication required"}), 401
        return f(*a, **kw)
    return wrapper


def role_required(*roles):
    def deco(f):
        @wraps(f)
        def wrapper(*a, **kw):
            if "user_id" not in session:
                return jsonify({"error":"Authentication required"}), 401
            if session.get("role") not in roles:
                return jsonify({"error":"This feature is not available for this account"}), 403
            return f(*a, **kw)
        return wrapper
    return deco


@app.route("/")
def index():
    return render_template("index.html", user=session.get("name"))


@app.post("/api/login")
def login():
    data=request.get_json() or {}
    email=data.get("email","").strip().lower()
    password=data.get("password","")
    con=db(); row=con.execute("SELECT * FROM users WHERE email=?",(email,)).fetchone(); con.close()
    if not row or hash_password(password) != row["password_hash"]:
        return jsonify({"error":"Invalid email or password"}),401
    session.clear()
    session["user_id"]=row["id"]; session["name"]=row["name"]; session["role"]=row["role"]
    session["patient_code"]=row["patient_code"]
    return jsonify({"ok":True,"name":row["name"],"role":row["role"],"patient_code":row["patient_code"]})


@app.post("/api/logout")
def logout():
    session.clear(); return jsonify({"ok":True})


@app.get("/api/me")
def me():
    if "user_id" not in session: return jsonify({"authenticated":False})
    return jsonify({"authenticated":True,"name":session["name"],"role":session["role"],"patient_code":session.get("patient_code")})


@app.get("/api/stats")
@role_required("physician", "pharmacy_intern")
def stats():
    con=db()
    total=con.execute("SELECT COUNT(*) c FROM patients").fetchone()["c"]
    meds=con.execute("SELECT COUNT(*) c FROM patients WHERE medications IS NOT NULL AND medications!=''").fetchone()["c"]
    ai=con.execute("SELECT COUNT(*) c FROM ai_requests").fetchone()["c"]
    appointments=con.execute("SELECT COUNT(*) c FROM appointments WHERE status!='Completed'").fetchone()["c"]
    conds=con.execute("SELECT condition,COUNT(*) n FROM patients WHERE condition!='' GROUP BY condition ORDER BY n DESC").fetchall()
    con.close()
    return jsonify({"total":total,"new_cases":min(total,36),"ai_suggestions":ai,"medications":meds,"appointments":appointments,"conditions":[dict(x) for x in conds]})


@app.get("/api/patients")
@role_required("physician", "pharmacy_intern")
def patients():
    q=request.args.get("q","").strip()
    con=db()
    if q:
        like=f"%{q}%"
        rows=con.execute("""SELECT * FROM patients WHERE name LIKE ? OR patient_code LIKE ?
                            OR phone LIKE ? OR condition LIKE ? ORDER BY id DESC""", (like,like,like,like)).fetchall()
    else:
        rows=con.execute("SELECT * FROM patients ORDER BY id DESC").fetchall()
    con.close()
    return jsonify([dict(r) for r in rows])


@app.post("/api/patients")
@role_required("physician", "pharmacy_intern")
def create_patient():
    d=request.get_json() or {}
    if not d.get("name","").strip(): return jsonify({"error":"Patient name is required"}),400
    con=db()
    n=con.execute("SELECT COALESCE(MAX(id),0)+1 n FROM patients").fetchone()["n"]
    code=f"NPX-{n:06d}"; timestamp=now()
    con.execute("""INSERT INTO patients(patient_code,name,age,sex,phone,address,weight,height,complaint,
                    condition,medications,allergies,history,abha_id,language,symptoms,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (code,d["name"].strip(),d.get("age"),d.get("sex"),d.get("phone"),d.get("address"),
         d.get("weight"),d.get("height"),d.get("complaint"),d.get("condition","New Case"),
         d.get("medications"),d.get("allergies"),d.get("history"),d.get("abha_id"),d.get("language","English"),d.get("symptoms"),timestamp,timestamp))
    con.commit(); row=con.execute("SELECT * FROM patients WHERE id=?",(con.execute("SELECT last_insert_rowid()").fetchone()[0],)).fetchone(); con.close()
    return jsonify(dict(row)),201


@app.get("/api/patients/<int:pid>")
@role_required("physician", "pharmacy_intern")
def patient(pid):
    con=db(); row=con.execute("SELECT * FROM patients WHERE id=?",(pid,)).fetchone(); con.close()
    if not row:return jsonify({"error":"Not found"}),404
    return jsonify(dict(row))


@app.put("/api/patients/<int:pid>")
@role_required("physician", "pharmacy_intern")
def update_patient(pid):
    d=request.get_json() or {}; timestamp=now()
    fields=["name","age","sex","phone","address","weight","height","complaint","condition","medications","allergies","history","abha_id","language","symptoms"]
    sets=", ".join(f"{x}=?" for x in fields)
    vals=[d.get(x) for x in fields]+[timestamp,pid]
    con=db(); cur=con.execute(f"UPDATE patients SET {sets},updated_at=? WHERE id=?",vals)
    con.commit(); row=con.execute("SELECT * FROM patients WHERE id=?",(pid,)).fetchone(); con.close()
    if not cur.rowcount:return jsonify({"error":"Not found"}),404
    return jsonify(dict(row))


@app.delete("/api/patients/<int:pid>")
@role_required("physician", "pharmacy_intern")
def delete_patient(pid):
    con=db(); cur=con.execute("DELETE FROM patients WHERE id=?",(pid,)); con.commit(); con.close()
    if not cur.rowcount:return jsonify({"error":"Not found"}),404
    return jsonify({"ok":True})


@app.get("/api/patient/me")
@role_required("patient")
def patient_me():
    con=db(); row=con.execute("SELECT * FROM patients WHERE patient_code=?",(session.get("patient_code"),)).fetchone(); con.close()
    if not row:return jsonify({"error":"Patient profile not found"}),404
    return jsonify(dict(row))


@app.put("/api/patient/me")
@role_required("patient")
def update_patient_me():
    d=request.get_json() or {}; code=session.get("patient_code")
    fields=["name","age","sex","phone","address","weight","height","complaint","condition","medications","allergies","history","abha_id","language","symptoms"]
    sets=", ".join(f"{x}=?" for x in fields)
    vals=[d.get(x) for x in fields]+[now(),code]
    con=db(); con.execute(f"UPDATE patients SET {sets},updated_at=? WHERE patient_code=?",vals); con.commit()
    row=con.execute("SELECT * FROM patients WHERE patient_code=?",(code,)).fetchone(); con.close()
    return jsonify(dict(row))


@app.get("/api/appointments")
@login_required
def appointments():
    con=db()
    if session.get("role") == "patient":
        row=con.execute("SELECT id FROM patients WHERE patient_code=?",(session.get("patient_code"),)).fetchone()
        pid=row[0] if row else -1
        rows=con.execute("""SELECT a.*,p.patient_code,p.name AS patient_name FROM appointments a
                            JOIN patients p ON p.id=a.patient_id WHERE a.patient_id=? ORDER BY a.appointment_date,a.appointment_time""",(pid,)).fetchall()
    else:
        rows=con.execute("""SELECT a.*,p.patient_code,p.name AS patient_name FROM appointments a
                            JOIN patients p ON p.id=a.patient_id ORDER BY a.appointment_date,a.appointment_time""").fetchall()
    con.close(); return jsonify([dict(r) for r in rows])


@app.post("/api/appointments")
@role_required("patient")
def create_appointment():
    d=request.get_json() or {}
    if not d.get("date") or not d.get("time"):
        return jsonify({"error":"Appointment date and time are required"}),400
    con=db(); prow=con.execute("SELECT id FROM patients WHERE patient_code=?",(session.get("patient_code"),)).fetchone()
    if not prow:return jsonify({"error":"Patient profile not found"}),404
    physician=con.execute("SELECT id FROM users WHERE role IN ('physician','pharmacy_intern') ORDER BY id LIMIT 1").fetchone()
    con.execute("""INSERT INTO appointments(patient_id,physician_id,appointment_date,appointment_time,reason,status,created_at)
                   VALUES(?,?,?,?,?,?,?)""",(prow[0],physician[0] if physician else None,d["date"],d["time"],d.get("reason"),"Requested",now()))
    con.commit(); con.close(); return jsonify({"ok":True}),201


@app.post("/api/connections")
@role_required("physician", "pharmacy_intern")
def create_connection():
    d=request.get_json() or {}; code=d.get("patient_code","").strip()
    con=db(); p=con.execute("SELECT id FROM patients WHERE patient_code=?",(code,)).fetchone()
    if not p:return jsonify({"error":"Patient ID not found"}),404
    physician=session["user_id"]
    existing=con.execute("SELECT * FROM connections WHERE patient_id=? AND physician_id=? AND status='Active'",(p[0],physician)).fetchone()
    if existing:return jsonify(dict(existing))
    c="NX-"+secrets.token_hex(3).upper()
    con.execute("INSERT INTO connections(patient_id,physician_id,connection_code,status,created_at) VALUES(?,?,?,?,?)",(p[0],physician,c,"Active",now()))
    con.commit(); row=con.execute("SELECT * FROM connections WHERE connection_code=?",(c,)).fetchone(); con.close()
    return jsonify(dict(row)),201


@app.post("/api/connections/join")
@role_required("patient")
def join_connection():
    d=request.get_json() or {}; code=d.get("connection_code","").strip().upper()
    con=db(); conn=con.execute("SELECT * FROM connections WHERE connection_code=? AND status='Active'",(code,)).fetchone()
    if not conn:return jsonify({"error":"Connection code not found or inactive"}),404
    if conn["patient_id"] != con.execute("SELECT id FROM patients WHERE patient_code=?",(session.get("patient_code"),)).fetchone()[0]:
        return jsonify({"error":"This connection code belongs to another patient"}),403
    con.commit(); con.close(); return jsonify({"ok":True,"message":"Patient connected to physician workflow"})


@app.get("/api/reports")
@login_required
def reports():
    con=db()
    if session.get("role") == "patient":
        p=con.execute("SELECT id FROM patients WHERE patient_code=?",(session.get("patient_code"),)).fetchone()
        rows=con.execute("SELECT * FROM reports WHERE patient_id=? ORDER BY id DESC",(p[0],)).fetchall() if p else []
    else:
        rows=con.execute("SELECT r.*,p.patient_code,p.name AS patient_name FROM reports r JOIN patients p ON p.id=r.patient_id ORDER BY r.id DESC").fetchall()
    con.close(); return jsonify([dict(r) for r in rows])


@app.post("/api/reports")
@role_required("patient", "physician", "pharmacy_intern")
def upload_report():
    if "file" not in request.files:return jsonify({"error":"Select a file"}),400
    file=request.files["file"]
    if not file.filename:return jsonify({"error":"Select a file"}),400
    category=request.form.get("category","Medical Report")
    if session.get("role") == "patient":
        con=db(); p=con.execute("SELECT id FROM patients WHERE patient_code=?",(session.get("patient_code"),)).fetchone(); con.close()
        pid=p[0] if p else None
    else:
        pid=request.form.get("patient_id",type=int)
    if not pid:return jsonify({"error":"Patient is required"}),400
    ext=os.path.splitext(file.filename)[1].lower()
    if ext not in {".pdf",".png",".jpg",".jpeg"}:return jsonify({"error":"Use PDF, PNG or JPG"}),400
    stored=secrets.token_hex(8)+ext
    file.save(os.path.join(UPLOAD_DIR,stored))
    con=db(); con.execute("INSERT INTO reports(patient_id,filename,original_name,category,uploaded_at) VALUES(?,?,?,?,?)",(pid,stored,secure_filename(file.filename),category,now())); con.commit(); con.close()
    return jsonify({"ok":True,"filename":stored}),201


@app.post("/api/ai")
@role_required("physician", "pharmacy_intern")
def ai():
    d=request.get_json() or {}; symptoms=d.get("symptoms","").strip()
    if not symptoms:return jsonify({"error":"Symptoms are required"}),400
    s=symptoms.lower(); suggestions=[]
    if any(x in s for x in ["fever","temperature"]): suggestions.append("Febrile illness: review duration, temperature pattern and infection-related findings.")
    if any(x in s for x in ["cough","sore throat","breath","respiratory"]): suggestions.append("Respiratory presentation: consider upper/lower respiratory differential based on examination.")
    if any(x in s for x in ["headache","migraine"]): suggestions.append("Headache syndrome: assess onset, severity, neurological red flags and triggers.")
    if any(x in s for x in ["sugar","glucose","diabet"]): suggestions.append("Metabolic consideration: review glucose/HbA1c and current therapy.")
    if any(x in s for x in ["urine","uti","burning urination"]): suggestions.append("Urinary presentation: assess urinary symptoms and appropriate laboratory confirmation.")
    if not suggestions:suggestions=["No specific pattern detected in this prototype. Review history, examination, vital signs and relevant laboratory data."]
    result={"suggestions":suggestions,"next_steps":["Verify patient history and medication/allergy profile.","Review relevant vitals and laboratory findings.","Discuss differential diagnosis with a licensed clinician/faculty member."],"disclaimer":"Educational decision-support prototype only. It must not be used for real patient diagnosis or treatment decisions."}
    con=db(); con.execute("INSERT INTO ai_requests(symptoms,result,created_at) VALUES(?,?,?)",(symptoms,str(result),now())); con.commit(); con.close()
    return jsonify(result)


@app.get("/api/export")
@role_required("physician", "pharmacy_intern")
def export():
    con=db(); rows=con.execute("SELECT patient_code,name,age,sex,phone,condition,created_at FROM patients ORDER BY id").fetchall(); con.close()
    import csv, io
    out=io.StringIO(); w=csv.writer(out); w.writerow(rows[0].keys() if rows else ["patient_code","name","age","sex","phone","condition","created_at"])
    for r in rows:w.writerow(list(r))
    mem=io.BytesIO(out.getvalue().encode()); mem.seek(0)
    return send_file(mem,as_attachment=True,download_name="neopharmax_patients.csv",mimetype="text/csv")


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)), debug=True)
