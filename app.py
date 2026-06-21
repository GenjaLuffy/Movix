from functools import wraps
import bcrypt
from flask import Flask, render_template, request, redirect, session, jsonify, url_for

from db import get_connection
from recommender import MovieRecommender

app = Flask(__name__)
app.secret_key = "movix-dev-secret-change-me"


# ==============================
# ML MODEL
# ==============================
recommender = MovieRecommender("dataset/movies.csv")


# ==============================
# AUTH HELPERS
# ==============================
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Not authenticated"}), 401
            return redirect(url_for("login_page"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Not authenticated"}), 401

        if not session.get("is_admin"):
            return jsonify({"error": "Admin required"}), 403

        return view(*args, **kwargs)
    return wrapped


def current_user_id():
    return session.get("user_id")


# ==============================
# PAGES
# ==============================
@app.route("/")
def landing_page():
    if "user_id" in session:
        return redirect(url_for("home_page"))
    return render_template("landingpage.html")


@app.route("/signup", methods=["GET"])
def signup_page():
    return render_template("signup.html")


@app.route("/signup", methods=["POST"])
def signup():
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    address = request.form.get("address", "").strip()
    password = request.form.get("password", "")

    if not all([first_name, last_name, email, password]):
        return render_template("signup.html", error="Fill all required fields"), 400

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            INSERT INTO users (first_name, last_name, email, address, password)
            VALUES (%s, %s, %s, %s, %s)
        """, (first_name, last_name, email, address, hashed))
        conn.commit()
    except Exception:
        return render_template("signup.html", error="Email already exists"), 400
    finally:
        conn.close()

    return redirect(url_for("login_page"))


@app.route("/login", methods=["GET"])
def login_page():
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
    user = cursor.fetchone()
    conn.close()

    if not user or not bcrypt.checkpw(password.encode(), user["password"].encode()):
        return render_template("login.html", error="Invalid credentials")

    if user.get("status") == "Blocked":
        return render_template("login.html", error="Account blocked")

    session["user_id"] = user["id"]
    session["first_name"] = user["first_name"]
    session["is_admin"] = bool(user.get("is_admin"))

    return redirect(url_for("admin_dashboard" if session["is_admin"] else "home_page"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing_page"))


# ==============================
# PAGES
# ==============================
@app.route("/home")
@login_required
def home_page():
    return render_template("index.html")


@app.route("/profile")
@login_required
def profile_page():
    return render_template("profile.html")


@app.route("/admin")
@admin_required
def admin_dashboard():
    return render_template("admin/admin_dashboard.html")


# ==============================
# MOVIES API
# ==============================
@app.route("/api/movies")
def api_movies():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM movies WHERE status='Published' ORDER BY popularity DESC")
    movies = cursor.fetchall()

    conn.close()
    return jsonify(movies)


@app.route("/api/movies/<int:movie_id>")
def api_movie_detail(movie_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM movies WHERE id=%s", (movie_id,))
    movie = cursor.fetchone()

    conn.close()

    if not movie:
        return jsonify({"error": "Not found"}), 404

    return jsonify(movie)


# ==============================
# 🔥 ML RECOMMENDATIONS
# ==============================
@app.route("/api/recommendations")
@login_required
def api_recommendations():
    user_id = current_user_id()

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # watched
    cursor.execute("""
        SELECT m.title
        FROM movies m
        JOIN watched w ON w.movie_id = m.id
        WHERE w.user_id=%s
    """, (user_id,))
    watched = [r["title"] for r in cursor.fetchall()]

    # favorites
    cursor.execute("""
        SELECT m.title
        FROM movies m
        JOIN favorites f ON f.movie_id = m.id
        WHERE f.user_id=%s
    """, (user_id,))
    favorites = [r["title"] for r in cursor.fetchall()]

    conn.close()

    user_movies = list(set(watched + favorites))

    try:
        results = recommender.recommend_for_user(user_movies, top_n=12)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify(results)


# ==============================
# WATCHLIST / FAVORITES / WATCHED
# ==============================
def _add(table):
    data = request.get_json(silent=True) or request.form
    movie_id = data.get("movie_id")

    if not movie_id:
        return jsonify({"error": "movie_id required"}), 400

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"""
        INSERT IGNORE INTO {table} (user_id, movie_id)
        VALUES (%s, %s)
    """, (current_user_id(), movie_id))

    conn.commit()
    conn.close()

    return jsonify({"success": True})


@app.route("/api/watchlist", methods=["POST"])
@login_required
def add_watchlist():
    return _add("watchlist")


@app.route("/api/favorites", methods=["POST"])
@login_required
def add_favorites():
    return _add("favorites")


@app.route("/api/watched", methods=["POST"])
@login_required
def add_watched():
    return _add("watched")


# ==============================
# REVIEWS
# ==============================
@app.route("/api/reviews", methods=["POST"])
@login_required
def create_review():
    data = request.get_json(silent=True) or request.form

    movie_id = data.get("movie_id")
    rating = data.get("rating")
    text = data.get("text")

    if not movie_id or not rating or not text:
        return jsonify({"error": "Missing fields"}), 400

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO reviews (user_id, movie_id, rating, review_text, status)
        VALUES (%s,%s,%s,%s,'Pending')
    """, (current_user_id(), movie_id, rating, text))

    conn.commit()
    conn.close()

    return jsonify({"success": True})


# ==============================
# RUN APP
# ==============================
if __name__ == "__main__":
    app.run(debug=True)