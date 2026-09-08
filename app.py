import os, sqlite3, hashlib, secrets
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "neopharmax.db")
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "neopharmax-demo-change-this-secret")

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL, role TEXT DEFAULT 'pharmacy_intern',
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS patients(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      patient_code TEXT UNIQUE NOT NULL,
      name TEXT NOT NULL, age INTEGER, sex TEXT, phone TEXT, address TEXT,
      weight REAL, height REAL, complaint TEXT, condition TEXT,
      medications TEXT, allergies TEXT, history TEXT,
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS ai_requests(
      id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id INTEGER,
      symptoms TEXT NOT NULL, result TEXT NOT NULL, created_at TEXT NOT NULL
    );
    """)
    if con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        pw = hashlib.sha256("demo123".encode()).hexdigest()
        con.execute("INSERT INTO users(name,email,password_hash,created_at) VALUES(?,?,?,?)",
                    ("Manpreet Singh","demo@neopharmax.local",pw,datetime.now().isoformat()))
    if con.execute("SELECT COUNT(*) FROM patients").fetchone()[0] == 0:
        seed = [
          ("Rahul Mehta",28,"Male","Fever"),("Simran Kaur",34,"Female","Hypertension"),
          ("Arjun Verma",19,"Male","Respiratory"),("Neha Sharma",45,"Female","Diabetes"),
          ("Karan Singh",52,"Male","Joint Pain"),("Pooja Nair",26,"Female","Gastritis"),
          ("Aditya Rao",39,"Male","Hypertension"),("Fatima Ali",31,"Female","Migraine"),
          ("Vikram Das",60,"Male","Diabetes"),("Ananya Sen",24,"Female","UTI")]
        now=datetime.now().isoformat()
        for i,(name,age,sex,cond) in enumerate(seed,1):
            con.execute("""INSERT INTO patients(patient_code,name,age,sex,condition,created_at,updated_at)
                           VALUES(?,?,?,?,?,?,?)""",
                        (f"P-{i:03d}",name,age,sex,cond,now,now))
    con.commit(); con.close()

def login_required(f):
    @wraps(f)
    def wrapper(*a,**kw):
        if "user_id" not in session:
            return jsonify({"error":"Authentication required"}),401
        return f(*a,**kw)
    return wrapper

@app.route("/")
def index():
    return render_template("index.html", user=session.get("name"))

@app.post("/api/login")
def login():
    data=request.get_json() or {}
    email=data.get("email","").strip().lower()
    password=data.get("password","")
    con=db(); row=con.execute("SELECT * FROM users WHERE email=?",(email,)).fetchone(); con.close()
    if not row or hashlib.sha256(password.encode()).hexdigest()!=row["password_hash"]:
        return jsonify({"error":"Invalid email or password"}),401
    session["user_id"]=row["id"]; session["name"]=row["name"]; session["role"]=row["role"]
    return jsonify({"ok":True,"name":row["name"],"role":row["role"]})

@app.post("/api/logout")
def logout():
    session.clear(); return jsonify({"ok":True})

@app.get("/api/me")
def me():
    if "user_id" not in session: return jsonify({"authenticated":False})
    return jsonify({"authenticated":True,"name":session["name"],"role":session["role"]})

@app.get("/api/stats")
@login_required
def stats():
    con=db()
    total=con.execute("SELECT COUNT(*) c FROM patients").fetchone()["c"]
    meds=con.execute("SELECT COUNT(*) c FROM patients WHERE medications IS NOT NULL AND medications!=''").fetchone()["c"]
    ai=con.execute("SELECT COUNT(*) c FROM ai_requests").fetchone()["c"]
    conds=con.execute("SELECT condition,COUNT(*) n FROM patients WHERE condition!='' GROUP BY condition ORDER BY n DESC").fetchall()
    con.close()
    return jsonify({"total":total,"new_cases":min(total,36),"ai_suggestions":ai,"medications":meds,"conditions":[dict(x) for x in conds]})

@app.get("/api/patients")
@login_required
def patients():
    q=request.args.get("q","").strip()
    con=db()
    if q:
        like=f"%{q}%"
        rows=con.execute("""SELECT * FROM patients WHERE name LIKE ? OR patient_code LIKE ?
                            OR phone LIKE ? OR condition LIKE ? ORDER BY id DESC""",
                         (like,like,like,like)).fetchall()
    else:
        rows=con.execute("SELECT * FROM patients ORDER BY id DESC").fetchall()
    con.close()
    return jsonify([dict(r) for r in rows])

@app.post("/api/patients")
@login_required
def create_patient():
    d=request.get_json() or {}
    if not d.get("name","").strip():
        return jsonify({"error":"Patient name is required"}),400
    con=db()
    next_id=con.execute("SELECT COALESCE(MAX(id),0)+1 n FROM patients").fetchone()["n"]
    code=f"P-{next_id:03d}"; now=datetime.now().isoformat()
    con.execute("""INSERT INTO patients(patient_code,name,age,sex,phone,address,weight,height,complaint,
                    condition,medications,allergies,history,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (code,d["name"].strip(),d.get("age"),d.get("sex"),d.get("phone"),d.get("address"),
         d.get("weight"),d.get("height"),d.get("complaint"),d.get("condition","New Case"),
         d.get("medications"),d.get("allergies"),d.get("history"),now,now))
    con.commit(); row=con.execute("SELECT * FROM patients WHERE id=?",(next_id,)).fetchone(); con.close()
    return jsonify(dict(row)),201

@app.get("/api/patients/<int:pid>")
@login_required
def patient(pid):
    con=db(); row=con.execute("SELECT * FROM patients WHERE id=?",(pid,)).fetchone(); con.close()
    if not row:return jsonify({"error":"Not found"}),404
    return jsonify(dict(row))

@app.put("/api/patients/<int:pid>")
@login_required
def update_patient(pid):
    d=request.get_json() or {}; now=datetime.now().isoformat()
    fields=["name","age","sex","phone","address","weight","height","complaint","condition","medications","allergies","history"]
    sets=", ".join(f"{x}=?" for x in fields)
    vals=[d.get(x) for x in fields]+[now,pid]
    con=db(); cur=con.execute(f"UPDATE patients SET {sets},updated_at=? WHERE id=?",vals)
    con.commit(); row=con.execute("SELECT * FROM patients WHERE id=?",(pid,)).fetchone(); con.close()
    if not cur.rowcount:return jsonify({"error":"Not found"}),404
    return jsonify(dict(row))

@app.delete("/api/patients/<int:pid>")
@login_required
def delete_patient(pid):
    con=db(); cur=con.execute("DELETE FROM patients WHERE id=?",(pid,)); con.commit(); con.close()
    if not cur.rowcount:return jsonify({"error":"Not found"}),404
    return jsonify({"ok":True})

@app.post("/api/ai")
@login_required
def ai():
    d=request.get_json() or {}; symptoms=d.get("symptoms","").strip()
    if not symptoms:return jsonify({"error":"Symptoms are required"}),400
    s=symptoms.lower()
    suggestions=[]
    if any(x in s for x in ["fever","temperature"]): suggestions.append("Febrile illness: review duration, temperature pattern and infection-related findings.")
    if any(x in s for x in ["cough","sore throat","breath","respiratory"]): suggestions.append("Respiratory presentation: consider upper/lower respiratory differential based on examination.")
    if any(x in s for x in ["headache","migraine"]): suggestions.append("Headache syndrome: assess onset, severity, neurological red flags and triggers.")
    if any(x in s for x in ["sugar","glucose","diabet"]): suggestions.append("Metabolic consideration: review glucose/HbA1c and current therapy.")
    if any(x in s for x in ["urine","uti","burning urination"]): suggestions.append("Urinary presentation: assess urinary symptoms and appropriate laboratory confirmation.")
    if not suggestions:suggestions=["No specific pattern detected in this prototype. Review history, examination, vital signs and relevant laboratory data."]
    result={"suggestions":suggestions,
            "next_steps":["Verify patient history and medication/allergy profile.","Review relevant vitals and laboratory findings.","Discuss differential diagnosis with a licensed clinician/faculty member."],
            "disclaimer":"Educational decision-support prototype only. It must not be used for real patient diagnosis or treatment decisions."}
    con=db(); con.execute("INSERT INTO ai_requests(symptoms,result,created_at) VALUES(?,?,?)",
                           (d.get("symptoms"),str(result),datetime.now().isoformat())); con.commit(); con.close()
    return jsonify(result)

@app.get("/api/export")
@login_required
def export():
    con=db(); rows=con.execute("SELECT patient_code,name,age,sex,phone,condition,created_at FROM patients ORDER BY id").fetchall(); con.close()
    import csv, io
    out=io.StringIO(); w=csv.writer(out); w.writerow(rows[0].keys() if rows else ["patient_code","name","age","sex","phone","condition","created_at"])
    for r in rows:w.writerow(list(r))
    mem=io.BytesIO(out.getvalue().encode()); mem.seek(0)
    return send_file(mem,as_attachment=True,download_name="neopharmax_patients.csv",mimetype="text/csv")

if __name__=="__main__":
    init_db()
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)),debug=True)
