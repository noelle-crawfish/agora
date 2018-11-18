import os, requests, json

from flask import Flask, session, render_template, request, redirect, abort
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from functools import wraps
from flask import g, request, redirect, url_for

# Helper functions
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not ("user") in session.keys() or session.get("user") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

def only_anon(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" in session.keys() and not session.get("user") is None:
            return redirect("/dashboard")
        return f(*args, **kwargs)
    return decorated_function

def add_class_to_user(session, class_id):
    user = db.execute("SELECT * FROM users WHERE username = :username", {"username":session["user"]["username"]}).fetchone()
    session["user"] = user
    class_id = "{" + str(class_id) + "}"
    if session["user"]["classes"] is None:
        db.execute("UPDATE users SET classes = :class_id  WHERE username = :username", {"username":session["user"]["username"], "class_id":class_id})
    else:
        db.execute("UPDATE users SET classes = array_cat(classes, :class_id) WHERE username = :username", {"username":session["user"]["username"], "class_id":class_id})
    db.commit()
    user = db.execute("SELECT * FROM users WHERE username = :username", {"username":session["user"]["username"]}).fetchone()
    session["user"] = user

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

@app.route("/")
def index():
    return render_template("homepage.html")

@app.route("/login_requests", methods=["POST"])
def process_login_request():
    username = request.form.get("username")
    password = hash(request.form.get("password"))

    user = db.execute("SELECT * FROM users WHERE username = :username", {"username":username}).fetchone()

    if user is None:
        return render_template("login.html", has_error=True, error="User does not exist")
    elif int(user["password"]) != int(password):
        return render_template("login.html", has_error=True, error="Incorrect password")
    else:
        session["user"] = user
        return redirect("/dashboard")

    return redirect("/")

@app.route("/register_requests", methods=["POST"])
def process_register_request():
    username = request.form.get("username")
    password = request.form.get("password")
    confirm = request.form.get("confirm-password")
    agreed = request.form.get("terms-of-service")

    if not agreed:
        return render_template("register.html", has_error=True, error="Please agree to our terms of service")

    if not password == confirm:
        return render_template("register.html", has_error=True, error="Passwords must match")
    
    # Check to see if user already exists
    old_user = db.execute("SELECT * FROM users WHERE username = :username", {"username":username}).fetchone()
    if not old_user is None:
        return render_template("register.html", has_error=True, error="That username is already taken")

    hashed = hash(password)
    db.execute("INSERT INTO users (username, password) VALUES (:username, :password)", {"username":username, "password":hashed})
    db.commit()
    user = db.execute("SELECT * FROM users WHERE username = :username", {"username":username}).fetchone()
    session["user"] = user
    return redirect("/dashboard")

@app.route("/login")
@only_anon
def login():
    return render_template("login.html")

@app.route("/register")
@only_anon
def register():
    return render_template("register.html")

@app.route("/dashboard")
@login_required
def dashboard():
    dashboard_classes = []
    dash_links = []
    if session["user"]["classes"]:
        for class_id in set(session["user"]["classes"]):
            class_found = db.execute("SELECT * FROM classes WHERE class_id = :class_id", {"class_id":class_id})
            dashboard_classes += class_found
            dash_links += ["/class/" + class_id]

    return render_template("dashboard.html", username=session["user"]["username"], classes=zip(dashboard_classes, dash_links))

@app.route("/add_class", methods=["GET", "POST"])
@login_required
def add_class():
    if request.method == "GET":
        return render_template("add_class.html")
    elif request.method == "POST":
        class_id = request.form.get("class-id")
        to_join = db.execute("SELECT * FROM classes WHERE class_id = :class_id", {"class_id":class_id})
        if to_join is None:
            return render_template("add_class.html", has_error=True, error="Class does not exist")
        else:
            add_class_to_user(session, class_id)
            return render_template("add_class.html", success=True)

@app.route("/create_class", methods=["GET", "POST"])
@login_required
def create_class():
    if request.method == "GET":
        return render_template("create_class.html")
    elif request.method == "POST":
        subject = request.form.get("subject")
        name = request.form.get("class-name")
        # TODO fix this to avoid collisions
        class_id = hash(subject + name)
        db.execute("INSERT INTO classes (subject, class_name, class_id) VALUES (:subject, :class_name, :class_id)", {"subject":subject, "class_name":name, "class_id":class_id})
        db.commit()
        add_class_to_user(session, class_id)
        return redirect("/dashboard")

@app.route("/class/<class_id>")
@login_required
def class_page(class_id):
    class_dict = db.execute("SELECT * FROM classes WHERE class_id = :class_id", {"class_id":class_id}).fetchone()
    if not class_dict:
        return redirect("/error")
    else:
        link = "/submitaproblem/" + class_id
        problem_links=[]
        problems = db.execute("SELECT * FROM problems WHERE class_id = :class_id", {"class_id":class_id}).fetchall()
        for problem in problems:
            problem_links += ["/class/" + str(class_id) + "/" + str(problem["index"])]
        return render_template("class_page.html", class_selected=class_dict, link=link, problems=zip(problems, problem_links))

@app.route("/class/<class_id>/<problem_index>")
@login_required
def problem_view(class_id, problem_index):
    class_dict = db.execute("SELECT * FROM classes WHERE class_id = :class_id", {"class_id":class_id}).fetchone()
    problem_selected = db.execute("SELECT * FROM problems WHERE index = :problem_index", {"problem_index":problem_index}).fetchone()
    if not problem_selected or not problem_selected["class_id"] == class_id:
        return redirect("/error")
    else:
        link = "/submitaproblem/" + class_id
        problem_links=[]
        problems = db.execute("SELECT * FROM problems WHERE class_id = :class_id", {"class_id":class_id}).fetchall()
        for problem in problems:
            problem_links += ["/class/" + str(class_id) + "/" + str(problem["index"])]
        return render_template("problem_selected.html", class_selected=class_dict, link=link, problem_selected=problem_selected)



@app.route("/submitaproblem/<class_id>", methods=["POST", "GET"])
@login_required
def submit_a_problem(class_id):
    if request.method == "GET":
        return render_template("submit_a_problem.html")
    elif request.method == "POST":
        problem_title = request.form.get("title")
        problem_text = request.form.get("problem-text")
        db.execute("INSERT INTO problems (title, question, class_id) VALUES (:title, :question, :class_id)", {"title":problem_title, "question":problem_text, "class_id":class_id})
        db.commit()
        return redirect("/class/" + class_id)

@app.route("/logout")
def logout():
    session["username"] = None
    return redirect("/")

@app.route("/termsofservice")
def tos():
    return "They don't exist just please don't sue us."

@app.route("/error")
def error():
    return render_template("error.html")

if __name__ == "__main__":
    threading.Thread(target=app.run).start()
