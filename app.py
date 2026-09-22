
import os, sqlite3, json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from functools import wraps

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "neopharmax.db")
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "neopharmax-sih-demo-secret")

DOMAINS = ["Memory", "Attention", "Concentration", "Daily Routine Recall", "Pattern & Object Recognition"]

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL,
      role TEXT NOT NULL, age INTEGER DEFAULT 72, language TEXT DEFAULT 'en',
      location TEXT DEFAULT 'NER Demo'
    );
    CREATE TABLE IF NOT EXISTS sessions(
      id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, domain TEXT,
      score INTEGER, accuracy INTEGER, difficulty TEXT, reaction_ms INTEGER,
      created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS reminders(
      id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, title TEXT,
      time TEXT, kind TEXT, done INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS alerts(
      id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, domain TEXT,
      message TEXT, level TEXT, created_at TEXT, seen INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS notes(
      id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, note TEXT, created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS sync_queue(
      id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, payload TEXT,
      created_at TEXT, synced INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS contacts(
      id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id INTEGER, healthworker_id INTEGER,
      subject TEXT, message TEXT, status TEXT DEFAULT 'Sent', created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS social_memories(
      id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, title TEXT,
      text TEXT, image_label TEXT, created_at TEXT
    );
    """)
    if c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        c.execute("""INSERT INTO users(name,email,password,role,age,language,location)
                     VALUES(?,?,?,?,?,?,?)""",
                  ("Harjit Singh","elder@neopharmax.demo","demo123","elder",72,"en","NER Demo"))
        c.execute("""INSERT INTO users(name,email,password,role,age,language,location)
                     VALUES(?,?,?,?,?,?,?)""",
                  ("Caregiver Demo","caregiver@neopharmax.demo","demo123","caregiver",38,"en","NER Demo"))
        c.execute("""INSERT INTO users(name,email,password,role,age,language,location)
                     VALUES(?,?,?,?,?,?,?)""",
                  ("Health Worker Demo","healthworker@neopharmax.demo","demo123","healthworker",31,"en","NER Demo"))
        uid = c.execute("SELECT id FROM users WHERE email='elder@neopharmax.demo'").fetchone()["id"]
        for x in [
            ("Morning medicines","08:00","Medicines",1),
            ("Drink water","13:00","Hydration",0),
            ("Medical appointment","16:00","Medical appointment",0),
            ("Daily memory practice","18:00","Daily activity",0)
        ]:
            c.execute("INSERT INTO reminders(user_id,title,time,kind,done) VALUES(?,?,?,?,?)",(uid,*x))
        samples = [
            ("Memory",84,90,"Easy",180),("Attention",81,87,"Easy",170),
            ("Concentration",80,85,"Easy",165),("Daily Routine Recall",78,83,"Easy",190),
            ("Pattern & Object Recognition",74,80,"Easy",210),
            ("Memory",77,82,"Easy",205),("Attention",82,88,"Medium",160),
            ("Concentration",79,84,"Easy",175),("Daily Routine Recall",80,86,"Easy",185),
            ("Pattern & Object Recognition",72,78,"Easy",220)
        ]
        for row in samples:
            c.execute("""INSERT INTO sessions(user_id,domain,score,accuracy,difficulty,reaction_ms,created_at)
                         VALUES(?,?,?,?,?,?,?)""",
                      (uid,*row,datetime.now().isoformat(timespec="seconds")))
        for m in [
            ("Family tea memories","Tea gardens, familiar songs and family conversations can be used as memory prompts.","Tea garden"),
            ("Morning routine","Remember the usual morning sequence: wake up, water, medicines, breakfast.","Morning routine")
        ]:
            c.execute("""INSERT INTO social_memories(user_id,title,text,image_label,created_at)
                         VALUES(?,?,?,?,?)""",(uid,*m,datetime.now().isoformat(timespec="seconds")))
    c.commit(); c.close()

def ensure_schema():
    c=db()
    cols=[r["name"] for r in c.execute("PRAGMA table_info(users)").fetchall()]
    if "last_seen" not in cols: c.execute("ALTER TABLE users ADD COLUMN last_seen TEXT")
    c.commit(); c.close()

def touch_last_seen():
    if "user_id" in session:
        c=db(); c.execute("UPDATE users SET last_seen=? WHERE id=?",(datetime.now().isoformat(timespec="seconds"),session["user_id"])); c.commit(); c.close()

def login_required(f):
    @wraps(f)
    def w(*a,**k):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*a,**k)
    return w

def current_user():
    c=db(); u=c.execute("SELECT * FROM users WHERE id=?",(session["user_id"],)).fetchone(); c.close(); return u

def elder_id():
    u=current_user()
    if u["role"]=="elder": return u["id"]
    c=db(); x=c.execute("SELECT id FROM users WHERE role='elder' LIMIT 1").fetchone(); c.close()
    return x["id"]

def add_alert(c, uid, domain, message, level="Review"):
    c.execute("""INSERT INTO alerts(user_id,domain,message,level,created_at)
                 VALUES(?,?,?,?,?)""",(uid,domain,message,level,datetime.now().isoformat(timespec="seconds")))

@app.get("/login")
def login_choice(): return render_template("role_login.html")

@app.route("/login/<role>", methods=["GET","POST"])
def role_login(role):
    roles={"elder":"Elderly Patient","caregiver":"Caregiver","healthworker":"Health Worker"}
    if role not in roles: return redirect("/login")
    if request.method=="POST":
        email=request.form.get("email","").lower().strip(); pw=request.form.get("password","")
        c=db(); u=c.execute("SELECT * FROM users WHERE email=? AND password=? AND role=?",(email,pw,role)).fetchone(); c.close()
        if u: session["user_id"]=u["id"]; touch_last_seen(); return redirect("/")
        flash("Invalid credentials for this portal.")
    return render_template("role_login_form.html",role=role,role_name=roles[role])

@app.get("/logout")
def logout():
    touch_last_seen(); session.clear(); return redirect("/login")

@app.get("/")
@login_required
def dashboard():
    u=current_user(); eid=elder_id(); c=db()
    reminders=c.execute("SELECT * FROM reminders WHERE user_id=? ORDER BY time",(eid,)).fetchall()
    domains=c.execute("""SELECT domain,ROUND(AVG(score),0) score,ROUND(AVG(accuracy),0) accuracy,
                         COUNT(*) n FROM sessions WHERE user_id=? GROUP BY domain""",(eid,)).fetchall()
    recent=c.execute("SELECT * FROM sessions WHERE user_id=? ORDER BY id DESC LIMIT 10",(eid,)).fetchall()
    alerts=c.execute("SELECT * FROM alerts WHERE user_id=? AND seen=0 ORDER BY id DESC LIMIT 5",(eid,)).fetchall()
    memories=c.execute("SELECT * FROM social_memories WHERE user_id=? ORDER BY id DESC LIMIT 4",(eid,)).fetchall()
    c.close()
    return render_template("dashboard.html",u=u,reminders=reminders,domains=domains,recent=recent,alerts=alerts,memories=memories)

@app.get("/games")
@login_required
def games():
    return render_template("games.html",u=current_user())

@app.route("/play/<slug>", methods=["GET","POST"])
@login_required
def play(slug):
    allowed={
        "memory":"Memory",
        "attention":"Attention",
        "concentration":"Concentration",
        "routine":"Daily Routine Recall",
        "pattern":"Pattern & Object Recognition"
    }
    if slug not in allowed: return redirect("/games")
    if request.method=="POST":
        d=request.get_json(silent=True) or {}
        score=int(d.get("score",0)); acc=int(d.get("accuracy",0))
        diff=d.get("difficulty","Easy"); reaction=int(d.get("reaction_ms",180))
        uid=elder_id(); domain=allowed[slug]
        c=db()
        c.execute("""INSERT INTO sessions(user_id,domain,score,accuracy,difficulty,reaction_ms,created_at)
                     VALUES(?,?,?,?,?,?,?)""",
                  (uid,domain,score,acc,diff,reaction,datetime.now().isoformat(timespec="seconds")))
        # Transparent demo rule: flag sustained low memory performance.
        if domain=="Memory" and score<=60:
            add_alert(c,uid,domain,
                      "Memory-domain performance fell into the prototype review range. Consider caregiver follow-up.",
                      "Review")
        c.commit(); c.close()
        return jsonify(ok=True)
    return render_template("play.html",domain=allowed[slug],slug=slug,u=current_user())

@app.get("/reminders")
@login_required
def reminders():
    c=db(); r=c.execute("SELECT * FROM reminders WHERE user_id=? ORDER BY time",(elder_id(),)).fetchall(); c.close()
    return render_template("reminders.html",u=current_user(),reminders=r)

@app.post("/api/reminder/<int:rid>/toggle")
@login_required
def reminder_toggle(rid):
    c=db(); c.execute("""UPDATE reminders SET done=CASE done WHEN 1 THEN 0 ELSE 1 END
                        WHERE id=? AND user_id=?""",(rid,elder_id())); c.commit(); c.close()
    return jsonify(ok=True)

@app.post("/api/reminder")
@login_required
def reminder_add():
    d=request.get_json() or {}
    c=db(); c.execute("""INSERT INTO reminders(user_id,title,time,kind,done)
                        VALUES(?,?,?,?,0)""",
                     (elder_id(),d.get("title","Daily activity"),d.get("time","12:00"),d.get("kind","Daily activity")))
    c.commit(); c.close(); return jsonify(ok=True)

@app.get("/caregiver")
@login_required
def caregiver():
    c=db(); eid=elder_id()
    u=c.execute("SELECT * FROM users WHERE id=?",(eid,)).fetchone()
    domains=c.execute("""SELECT domain,ROUND(AVG(score),0) score,ROUND(AVG(accuracy),0) accuracy,
                         COUNT(*) n FROM sessions WHERE user_id=? GROUP BY domain""",(eid,)).fetchall()
    sessions=c.execute("SELECT * FROM sessions WHERE user_id=? ORDER BY id DESC LIMIT 25",(eid,)).fetchall()
    alerts=c.execute("SELECT * FROM alerts WHERE user_id=? ORDER BY id DESC LIMIT 10",(eid,)).fetchall()
    notes=c.execute("SELECT * FROM notes WHERE user_id=? ORDER BY id DESC LIMIT 8",(eid,)).fetchall()
    patient=c.execute("SELECT id,name,age,language,last_seen,location FROM users WHERE id=?",(eid,)).fetchone()
    c.close()
    return render_template("caregiver.html",u=u,domains=domains,sessions=sessions,alerts=alerts,notes=notes,patient=patient)

@app.get("/healthworker")
@login_required
def healthworker():
    c=db(); eid=elder_id()
    u=c.execute("SELECT * FROM users WHERE id=?",(eid,)).fetchone()
    domains=c.execute("""SELECT domain,ROUND(AVG(score),0) score,ROUND(AVG(accuracy),0) accuracy,
                         COUNT(*) n FROM sessions WHERE user_id=? GROUP BY domain""",(eid,)).fetchall()
    reminders=c.execute("SELECT * FROM reminders WHERE user_id=? ORDER BY time",(eid,)).fetchall()
    patient=c.execute("SELECT id,name,age,language,last_seen,location FROM users WHERE id=?",(eid,)).fetchone()
    contacts=c.execute("SELECT ct.*, p.name patient_name FROM contacts ct JOIN users p ON ct.patient_id=p.id WHERE ct.healthworker_id=? ORDER BY ct.id DESC LIMIT 10",(current_user()["id"],)).fetchall()
    c.close()
    return render_template("healthworker.html",u=u,domains=domains,reminders=reminders,viewer=current_user(),patient=patient,contacts=contacts)


@app.get("/patient-portal")
@login_required
def patient_portal():
    u=current_user()
    # Patient/elderly portal: only the logged-in elderly user's own information.
    if u["role"]!="elder":
        return redirect("/")
    c=db()
    reminders=c.execute("SELECT * FROM reminders WHERE user_id=? ORDER BY time",(u["id"],)).fetchall()
    sessions=c.execute("SELECT * FROM sessions WHERE user_id=? ORDER BY id DESC LIMIT 12",(u["id"],)).fetchall()
    memories=c.execute("SELECT * FROM social_memories WHERE user_id=? ORDER BY id DESC LIMIT 6",(u["id"],)).fetchall()
    c.close()
    return render_template("patient_portal.html",u=u,reminders=reminders,sessions=sessions,memories=memories)

@app.get("/role-portal")
@login_required
def role_portal():
    u=current_user()
    if u["role"]=="elder": return redirect("/patient-portal")
    if u["role"]=="caregiver": return redirect("/caregiver")
    if u["role"]=="healthworker": return redirect("/healthworker")
    return redirect("/")

@app.post("/api/note")
@login_required
def note():
    d=request.get_json() or {}; t=d.get("note","").strip()
    if t:
        c=db(); c.execute("INSERT INTO notes(user_id,note,created_at) VALUES(?,?,?)",
                          (elder_id(),t,datetime.now().isoformat(timespec="seconds"))); c.commit(); c.close()
    return jsonify(ok=True)

@app.post("/api/alert/<int:aid>/seen")
@login_required
def alert_seen(aid):
    c=db(); c.execute("UPDATE alerts SET seen=1 WHERE id=? AND user_id=?",(aid,elder_id())); c.commit(); c.close()
    return jsonify(ok=True)

@app.get("/contact-health-worker")
@login_required
def contact_health_worker():
    u=current_user()
    if u["role"]!="elder": return redirect("/")
    c=db()
    workers=c.execute("SELECT id,name,email,last_seen FROM users WHERE role='healthworker' ORDER BY name").fetchall()
    messages=c.execute("SELECT ct.*, hw.name worker_name FROM contacts ct LEFT JOIN users hw ON ct.healthworker_id=hw.id WHERE ct.patient_id=? ORDER BY ct.id DESC",(u["id"],)).fetchall()
    c.close()
    return render_template("contact_health_worker.html",u=u,workers=workers,messages=messages)

@app.post("/api/contact-health-worker")
@login_required
def send_health_worker_message():
    u=current_user()
    if u["role"]!="elder": return jsonify(ok=False,message="Only the patient can send a request."),403
    d=request.get_json() or {}
    try: wid=int(d.get("healthworker_id",0))
    except: wid=0
    subject=d.get("subject","Support request").strip(); message=d.get("message","").strip()
    c=db(); worker=c.execute("SELECT id FROM users WHERE id=? AND role='healthworker'",(wid,)).fetchone()
    if not worker or not message:
        c.close(); return jsonify(ok=False,message="Choose a health worker and enter a message."),400
    c.execute("INSERT INTO contacts(patient_id,healthworker_id,subject,message,status,created_at) VALUES(?,?,?,?,?,?)",(u["id"],wid,subject,message,"Sent",datetime.now().isoformat(timespec="seconds")))
    c.commit(); c.close(); return jsonify(ok=True)

@app.get("/profile")
@login_required
def profile():
    return render_template("profile.html",u=current_user())

@app.post("/api/language")
@login_required
def language():
    lang=(request.get_json() or {}).get("language","en")
    c=db(); c.execute("UPDATE users SET language=? WHERE id=?",(lang,current_user()["id"])); c.commit(); c.close()
    return jsonify(ok=True)

@app.post("/api/sync")
@login_required
def sync():
    # Prototype synchronization endpoint for offline queued events.
    d=request.get_json() or {}
    payload=json.dumps(d)
    c=db(); c.execute("INSERT INTO sync_queue(user_id,payload,created_at,synced) VALUES(?,?,?,1)",
                      (elder_id(),payload,datetime.now().isoformat(timespec="seconds")))
    c.commit(); c.close()
    return jsonify(ok=True, message="Offline event synchronized.")

@app.get("/api/analytics")
@login_required
def analytics():
    c=db(); eid=elder_id()
    rows=c.execute("""SELECT domain,AVG(score) score,AVG(accuracy) accuracy,COUNT(*) n
                      FROM sessions WHERE user_id=? GROUP BY domain""",(eid,)).fetchall()
    c.close()
    return jsonify([dict(r) for r in rows])

@app.route("/manifest.webmanifest")
def manifest():
    return app.send_static_file("manifest.webmanifest")

@app.route("/service-worker.js")
def sw():
    return app.send_static_file("service-worker.js")

init_db()
ensure_schema()

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)),debug=True)
