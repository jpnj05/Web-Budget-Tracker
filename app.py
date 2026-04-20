from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_dance.contrib.google import make_google_blueprint, google
from flask_login import LoginManager, login_user, logout_user, UserMixin, login_required, current_user
import json
import os
import uuid
from datetime import datetime, timedelta
from supabase import create_client

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-in-production")

@app.template_filter('format_date')
def format_date_filter(date_str):
    """Jinja filter: '2026-04-12 02:20' -> 'Sunday, April 12, 2026 · 2:20 AM'"""
    try:
        dt = datetime.strptime(str(date_str), "%Y-%m-%d %H:%M")
        return dt.strftime("%A, %B %d, %Y · %I:%M %p").replace(" 0", " ").replace("AM","AM").replace("PM","PM")
    except Exception:
        return date_str

login_manager = LoginManager()
login_manager.login_view = "google.login"
login_manager.init_app(app)

class User(UserMixin):
    def __init__(self, email):
        self.id = email
        self.email = email

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

google_bp = make_google_blueprint(
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    scope=[
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile"
    ],
    redirect_url="/google_login"
)
app.register_blueprint(google_bp, url_prefix="/login")

def load_data():
    if not current_user.is_authenticated:
        return {}

    email = current_user.email
    user_resp = supabase.table("users").select("*").eq("email", email).single().execute()
    user_data = user_resp.data if user_resp.data else None

    if not user_data:
        user_data = default_user_data()
        user_data["email"] = email
        return {email: user_data}

    expenses_resp = supabase.table("expenses").select("*").eq("user_email", email).order("date", {"ascending": True}).execute()
    history_resp = supabase.table("history").select("*").eq("user_email", email).order("archived_at", {"ascending": False}).execute()

    user_data["expenses"] = expenses_resp.data or []
    user_data["history"] = history_resp.data or []
    user_data.setdefault("revert_snapshot", None)

    for k, v in default_user_data().items():
        user_data.setdefault(k, v)

    return {email: user_data}

def save_data(data):
    if not isinstance(data, dict) or len(data) != 1:
        return

    email, user_data = next(iter(data.items()))
    if email is None:
        return

    user_row = {
        "email": email,
        "budget": user_data.get("budget", 0),
        "period": user_data.get("period", "month"),
        "period_start": user_data.get("period_start", period_start_for(user_data.get("period", "month"))),
        "savings_goal": user_data.get("savings_goal", 0)
    }
    supabase.table("users").upsert(user_row).execute()

    supabase.table("expenses").delete().eq("user_email", email).execute()
    expenses = user_data.get("expenses", []) or []
    if expenses:
        rows = []
        for e in expenses:
            rows.append({
                "id": e.get("id"),
                "user_email": email,
                "name": e.get("name"),
                "amount": e.get("amount"),
                "category": e.get("category"),
                "date": e.get("date"),
            })
        supabase.table("expenses").insert(rows).execute()

    supabase.table("history").delete().eq("user_email", email).execute()
    history = user_data.get("history", []) or []
    if history:
        rows = []
        for h in history:
            rows.append({
                "id": h.get("id"),
                "user_email": email,
                "period": h.get("period"),
                "period_start": h.get("period_start"),
                "label": h.get("label"),
                "budget": h.get("budget"),
                "savings_goal": h.get("savings_goal"),
                "expenses": h.get("expenses"),
                "archived_at": h.get("archived_at"),
            })
        supabase.table("history").insert(rows).execute()

def default_user_data():
    return {
        "budget": 0,
        "period": "month",       # day | week | month
        "period_start": datetime.now().strftime("%Y-%m-%d"),
        "savings_goal": 0,
        "expenses": [],
        "history": []             # list of archived period snapshots
    }

def get_period_label(period, start_str):
    """Human-readable label for a period, e.g. 'Monday, April 07, 2025'"""
    try:
        dt = datetime.strptime(start_str, "%Y-%m-%d")
    except Exception:
        return start_str
    if period == "day":
        return dt.strftime("%A, %B %d, %Y")
    elif period == "week":
        end = dt + timedelta(days=6)
        return f"Week of {dt.strftime('%B %d')} – {end.strftime('%B %d, %Y')}"
    else:
        return dt.strftime("%B %Y")

def period_start_for(period):
    now = datetime.now()
    if period == "day":
        return now.strftime("%Y-%m-%d")
    elif period == "week":
        monday = now - timedelta(days=now.weekday())
        return monday.strftime("%Y-%m-%d")
    else:
        return now.strftime("%Y-%m-01")

def period_ended(period, start_str):
    """Return True if the stored period has passed."""
    try:
        start = datetime.strptime(start_str, "%Y-%m-%d")
    except Exception:
        return False
    now = datetime.now()
    if period == "day":
        return now.date() > start.date()
    elif period == "week":
        return now.date() >= (start + timedelta(days=7)).date()
    else:
        # next month started
        if now.month != start.month or now.year != start.year:
            return True
        return False

def maybe_reset(user_data):
    """Archive current period to history and reset if period has ended."""
    period = user_data.get("period", "month")
    start_str = user_data.get("period_start", period_start_for(period))

    if period_ended(period, start_str) and user_data.get("expenses"):
        # Archive
        snapshot = {
            "id": str(uuid.uuid4()),
            "period": period,
            "period_start": start_str,
            "label": get_period_label(period, start_str),
            "budget": user_data.get("budget", 0),
            "savings_goal": user_data.get("savings_goal", 0),
            "expenses": user_data.get("expenses", []),
            "archived_at": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        if "history" not in user_data:
            user_data["history"] = []
        user_data["history"].insert(0, snapshot)   # newest first
        user_data["expenses"] = []
        user_data["period_start"] = period_start_for(period)

    return user_data

def compute_personality(total, budget, period, expenses):
    """
    Smart personality: considers purchase frequency and timing.
    Returns (label, css_class, detail)
    """
    if budget <= 0:
        return "No budget set", "neutral", ""

    ratio = total / budget if budget > 0 else 0
    now = datetime.now()

    # Count purchases in last 24h
    recent_count = 0
    evening_count = 0
    morning_count = 0
    for e in expenses:
        try:
            dt = datetime.strptime(e["date"], "%Y-%m-%d %H:%M")
            delta = now - dt
            if delta.total_seconds() < 86400:
                recent_count += 1
            h = dt.hour
            if 18 <= h <= 23:
                evening_count += 1
            if 6 <= h <= 11:
                morning_count += 1
        except Exception:
            pass

    # Determine label
    if ratio >= 1.0:
        label = "Impulsive Spender"
        css = "danger"
        if recent_count >= 3:
            detail = f"You made {recent_count} purchases in the last 24 hours."
        else:
            detail = "You've exceeded your budget."
    elif ratio >= 0.75:
        label = "Heavy Spender"
        css = "warning"
        detail = f"You've used {ratio*100:.0f}% of your budget."
        if evening_count > morning_count and evening_count > 2:
            detail += " You tend to spend more in the evenings."
    elif ratio >= 0.5:
        label = "Balanced Spender"
        css = "warning"
        detail = f"Halfway through your budget with {len(expenses)} purchase(s)."
    elif ratio > 0:
        label = "Saver"
        css = "safe"
        detail = f"Only {ratio*100:.0f}% spent — great discipline!"
        if morning_count > evening_count and morning_count > 1:
            detail += " Most purchases are in the morning."
    else:
        label = "No spending yet"
        css = "neutral"
        detail = "Start tracking your expenses below."

    return label, css, detail

class Expense:
    def __init__(self, name, amount, category):
        self.id = str(uuid.uuid4())
        self.name = name.strip().capitalize()
        self.amount = amount
        self.category = category
        self.date = datetime.now().strftime("%Y-%m-%d %H:%M")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "category": self.category,
            "date": self.date
        }

def format_expense_date(date_str):
    """Convert '2025-04-11 19:42' → 'Friday, April 11, 2025 · 7:42 PM'"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
        return dt.strftime("%A, %B %d, %Y · %I:%M %p").replace(" 0", " ")
    except Exception:
        return date_str

# ------------------- Routes -------------------

@app.route("/")
@login_required
def index():
    all_data = load_data()
    user_data = all_data.get(current_user.email, default_user_data())

    # Ensure all keys exist on old records
    for k, v in default_user_data().items():
        user_data.setdefault(k, v)

    # Auto-reset if period ended
    user_data = maybe_reset(user_data)
    all_data[current_user.email] = user_data
    save_data(all_data)

    expenses      = user_data["expenses"]
    budget        = user_data["budget"]
    period        = user_data["period"]
    period_start  = user_data["period_start"]
    savings_goal  = user_data.get("savings_goal", 0)
    history       = user_data.get("history", [])

    total     = sum(e["amount"] for e in expenses)
    remaining = budget - total

    # Savings goal progress
    savings_pct = 0
    if savings_goal > 0 and budget > 0:
        saved = max(0, remaining)
        savings_pct = min(100, saved / savings_goal * 100)

    period_label = get_period_label(period, period_start)

    personality, personality_class, personality_detail = compute_personality(total, budget, period, expenses)
    suggestion = "⚠ You ran out of budget!" if remaining < 0 else ""

    # Group expenses by category — no merging, each shown individually
    grouped_expenses = {}
    for e in expenses:
        cat = e["category"]
        grouped_expenses.setdefault(cat, [])
        grouped_expenses[cat].append({
            "name":   e["name"],
            "amount": e["amount"],
            "id":     e["id"],
            "date":   format_expense_date(e.get("date", ""))
        })

    expense_count = sum(len(v) for v in grouped_expenses.values())

    revert_snapshot = user_data.get("revert_snapshot")

    return render_template(
        "index.html",
        grouped_expenses=grouped_expenses,
        expense_count=expense_count,
        total=total,
        budget=budget,
        remaining=remaining,
        period=period,
        period_label=period_label,
        savings_goal=savings_goal,
        savings_pct=savings_pct,
        suggestion=suggestion,
        personality=personality,
        personality_class=personality_class,
        personality_detail=personality_detail,
        history=history,
        revert_snapshot=revert_snapshot,
        current_user_email=current_user.email,
    )

@app.route("/set_budget", methods=["POST"])
@login_required
def set_budget():
    try:
        budget = float(request.form["budget"])
        if budget < 0:
            return redirect("/")
    except ValueError:
        return redirect("/")

    period = request.form.get("period", "month")
    if period not in ("day", "week", "month"):
        period = "month"

    try:
        savings_goal = float(request.form.get("savings_goal", 0))
        if savings_goal < 0:
            savings_goal = 0
    except ValueError:
        savings_goal = 0

    all_data = load_data()
    user_data = all_data.get(current_user.email, default_user_data())
    for k, v in default_user_data().items():
        user_data.setdefault(k, v)

    old_period = user_data.get("period", "month")

    user_data["budget"] = budget
    user_data["savings_goal"] = savings_goal

    # If period changed, reset period_start
    if period != old_period:
        user_data["period"] = period
        user_data["period_start"] = period_start_for(period)

    all_data[current_user.email] = user_data
    save_data(all_data)
    return redirect("/")

@app.route("/add", methods=["POST"])
@login_required
def add_expense():
    name     = request.form["name"].strip()
    category = request.form.get("category", "").strip()

    if not category:
        category = "Other"

    try:
        amount = float(request.form["amount"])
        if amount <= 0 or not name:
            return redirect("/")
    except ValueError:
        return redirect("/")

    expense = Expense(name, amount, category).to_dict()
    all_data = load_data()
    user_data = all_data.get(current_user.email, default_user_data())
    for k, v in default_user_data().items():
        user_data.setdefault(k, v)
    user_data["expenses"].append(expense)
    all_data[current_user.email] = user_data
    save_data(all_data)
    return redirect("/")

@app.route("/delete/<expense_id>")
@login_required
def delete_expense(expense_id):
    all_data = load_data()
    user_data = all_data.get(current_user.email, default_user_data())
    user_data["expenses"] = [e for e in user_data["expenses"] if e.get("id") != expense_id]
    all_data[current_user.email] = user_data
    save_data(all_data)
    return redirect("/")

@app.route("/clear_expenses")
@login_required
def clear_expenses():
    all_data = load_data()
    user_data = all_data.get(current_user.email, default_user_data())
    user_data["expenses"] = []
    all_data[current_user.email] = user_data
    save_data(all_data)
    return redirect("/")

@app.route("/history/delete/<history_id>")
@login_required
def delete_history(history_id):
    all_data = load_data()
    user_data = all_data.get(current_user.email, default_user_data())
    user_data["history"] = [h for h in user_data.get("history", []) if h.get("id") != history_id]
    all_data[current_user.email] = user_data
    save_data(all_data)
    return redirect("/")

def shift_expense_date(original_date_str, period, old_period_start_str, new_period_start_str):
    """
    Shift an expense date from the old period into the equivalent position
    in the new period, preserving the time-of-day and relative day offset.

    - day:   keep same HH:MM, move to today's date
    - week:  keep same day-of-week (Mon=0..Sun=6) and HH:MM, move to current week
    - month: keep same day-of-month and HH:MM, move to current month
             (clamps to last day of month if the day doesn't exist, e.g. Feb 30 → Feb 28)
    """
    try:
        orig_dt = datetime.strptime(original_date_str, "%Y-%m-%d %H:%M")
    except Exception:
        return original_date_str  # unparseable — leave as-is

    try:
        old_start = datetime.strptime(old_period_start_str, "%Y-%m-%d")
        new_start = datetime.strptime(new_period_start_str, "%Y-%m-%d")
    except Exception:
        return original_date_str

    if period == "day":
        # Same time today
        new_dt = new_start.replace(hour=orig_dt.hour, minute=orig_dt.minute)

    elif period == "week":
        # Use the actual weekday of the expense (Mon=0 ... Sun=6)
        # and place it on that same weekday in the new week (anchored to Monday)
        weekday = orig_dt.weekday()  # 0=Mon, 6=Sun, independent of period_start
        new_monday = new_start - timedelta(days=new_start.weekday())
        new_dt = (new_monday + timedelta(days=weekday)).replace(
            hour=orig_dt.hour, minute=orig_dt.minute
        )

    else:  # month
        # Preserve day-of-month if it exists in the new month.
        # If it doesn't (e.g. March 31 → April which only has 30 days),
        # instead of clamping we find the last occurrence of the same
        # weekday in the new month — so Tuesday Mar 31 → last Tuesday of April.
        import calendar
        day = orig_dt.day
        last_day = calendar.monthrange(new_start.year, new_start.month)[1]
        if day > last_day:
            # Day doesn't exist in new month — find the last same weekday
            target_weekday = orig_dt.weekday()  # e.g. Tuesday = 1
            # Walk backwards from the last day of the new month
            candidate = new_start.replace(day=last_day)
            while candidate.weekday() != target_weekday:
                candidate -= timedelta(days=1)
            new_dt = candidate.replace(hour=orig_dt.hour, minute=orig_dt.minute)
        else:
            new_dt = new_start.replace(day=day, hour=orig_dt.hour, minute=orig_dt.minute)

    return new_dt.strftime("%Y-%m-%d %H:%M")


@app.route("/history/reapply/<history_id>")
@login_required
def reapply_history(history_id):
    """
    Add all expenses from a history snapshot into current expenses.
    Dates are shifted to the equivalent position in the current period
    (same day-of-week/day-of-month and time-of-day).
    Saves current state first so the user can revert if needed.
    """
    all_data = load_data()
    user_data = all_data.get(current_user.email, default_user_data())
    for k, v in default_user_data().items():
        user_data.setdefault(k, v)

    snapshot = next((h for h in user_data.get("history", []) if h.get("id") == history_id), None)
    if snapshot:
        # Save current state as revert point BEFORE changing anything
        user_data["revert_snapshot"] = {
            "expenses": [dict(e) for e in user_data["expenses"]],
            "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "from_label": snapshot.get("label", "unknown period")
        }

        snap_period      = snapshot.get("period", user_data.get("period", "month"))
        old_period_start = snapshot.get("period_start", "")
        new_period_start = user_data.get("period_start", period_start_for(snap_period))

        # Append historical expenses with fresh IDs and shifted dates
        for e in snapshot.get("expenses", []):
            new_e = dict(e)
            new_e["id"]   = str(uuid.uuid4())
            new_e["date"] = shift_expense_date(
                e.get("date", ""),
                snap_period,
                old_period_start,
                new_period_start
            )
            user_data["expenses"].append(new_e)

    all_data[current_user.email] = user_data
    save_data(all_data)
    return redirect("/")


@app.route("/history/revert")
@login_required
def revert_reapply():
    """Restore expenses to state before last reapply. One-use only."""
    all_data = load_data()
    user_data = all_data.get(current_user.email, default_user_data())
    for k, v in default_user_data().items():
        user_data.setdefault(k, v)

    revert = user_data.get("revert_snapshot")
    if revert:
        user_data["expenses"] = revert.get("expenses", [])
        user_data["revert_snapshot"] = None

    all_data[current_user.email] = user_data
    save_data(all_data)
    return redirect("/")

@app.route("/history/keep")
@login_required
def keep_expenses():
    """Dismiss the revert snapshot — user wants to keep current expenses."""
    all_data = load_data()
    user_data = all_data.get(current_user.email, default_user_data())
    for k, v in default_user_data().items():
        user_data.setdefault(k, v)
    user_data["revert_snapshot"] = None
    all_data[current_user.email] = user_data
    save_data(all_data)
    return redirect("/")

@app.route("/google_login")
def google_login():
    if not google.authorized:
        return redirect(url_for("google.login", prompt="select_account"))
    resp = google.get("/oauth2/v2/userinfo")
    if not resp.ok:
        return "Failed to fetch user info"
    email = resp.json()["email"]
    login_user(User(email))
    return redirect("/")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    session.pop("google_oauth_token", None)
    return redirect(url_for("google.login", prompt="select_account"))

if __name__ == "__main__":
    app.run(debug=True)