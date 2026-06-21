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
# AUTH
# ==============================
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html")

    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    address = request.form.get("address", "").strip()
    password = request.form.get("password", "")

    if not all([first_name, last_name, email, password]):
        return render_template("signup.html", error="Fill all required fields"), 400

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    conn = get_connection()
    cursor = conn.cursor()

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


@app.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
    user = cursor.fetchone()
    conn.close()

    if not user or not bcrypt.checkpw(password.encode(), user["password"].encode()):
        return render_template("login.html", error="Invalid credentials")

    session["user_id"] = user["id"]
    session["first_name"] = user["first_name"]
    session["is_admin"] = bool(user.get("is_admin"))

    return redirect(url_for("home_page"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing_page"))


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
def get_movie(movie_id):
    try:
        movie = recommender.get_movie_by_id(movie_id)

        if movie is None:
            return jsonify({"error": "Movie not found"}), 404

        return jsonify(movie)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
# ==============================
# 🔥 FIXED RECOMMENDATION SYSTEM
# ==============================
@app.route("/api/recommendations", methods=["POST"])
@login_required
def api_recommendations():
    user_id = current_user_id()

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT m.title
        FROM movies m
        JOIN watched w ON w.movie_id = m.id
        WHERE w.user_id=%s
    """, (user_id,))
    watched = cursor.fetchall()

    cursor.execute("""
        SELECT m.title
        FROM movies m
        JOIN favorites f ON f.movie_id = m.id
        WHERE f.user_id=%s
    """, (user_id,))
    favorites = cursor.fetchall()

    cursor.execute("""
        SELECT m.title
        FROM movies m
        JOIN watchlist wl ON wl.movie_id = m.id
        WHERE wl.user_id=%s
    """, (user_id,))
    watchlist = cursor.fetchall()

    conn.close()

    user_movies = list(set(
        [m["title"] for m in watched] +
        [m["title"] for m in favorites] +
        [m["title"] for m in watchlist]
    ))

    # -----------------------
    # CASE 1: NO HISTORY
    # -----------------------
    if not user_movies:
        results = recommender.df.sort_values(
            "popularity",
            ascending=False
        ).head(10).to_dict(orient="records")

        return jsonify(results)

    # -----------------------
    # CASE 2: ML RECOMMENDATIONS
    # -----------------------
    results = recommender.recommend_for_user(
    user_movies=user_movies,
    top_n=12
)

    # -----------------------
    # SAFETY FALLBACK
    # -----------------------
    if not results:
        results = recommender.df.sample(10).to_dict(orient="records")

    # return jsonify(results)
# ==============================
# ADD MOVIES (WATCHLIST / FAV / WATCHED)
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
# MOVIE PAGE
# ==============================
@app.route("/movie/<int:movie_id>")
def movie_detail(movie_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM movies WHERE id=%s", (movie_id,))
    movie = cursor.fetchone()

    conn.close()

    if not movie:
        return "Movie not found", 404

    return render_template("movie_detail.html", movie=movie)


# ==============================
# RUN
# ==============================
if __name__ == "__main__":
    app.run(debug=True)