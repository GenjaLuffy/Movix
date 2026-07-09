from functools import wraps
import bcrypt

from flask import (
    Flask,
    render_template,
    session,
    request,
    redirect,
    jsonify,
    url_for
)

from db import get_connection
from recommender import MovieRecommender

app = Flask(__name__)
app.secret_key = "movix-dev-secret-change-me"

# Load recommender once when Flask starts
recommender = MovieRecommender()

# =====================================================
# FLASK APP
# =====================================================

app = Flask(__name__)
app.secret_key = "movix-dev-secret-change-me"


# =====================================================
# LOAD ML MODEL
# =====================================================

recommender = MovieRecommender()


# =====================================================
# HELPERS
# =====================================================

def current_user_id():
    return session.get("user_id")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):

        if "user_id" not in session:

            if request.path.startswith("/api/"):
                return jsonify({
                    "success": False,
                    "message": "Login required"
                }), 401

            return redirect(url_for("login_page"))

        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):

        if "user_id" not in session:
            return redirect(url_for("login_page"))

        if not session.get("is_admin"):
            return jsonify({
                "success": False,
                "message": "Admin only"
            }), 403

        return view(*args, **kwargs)

    return wrapped


# =====================================================
# LANDING PAGE
# =====================================================

@app.route("/")
def landing_page():

    if "user_id" in session:

        if session.get("is_admin"):
            return redirect(url_for("admin_dashboard"))

        return redirect(url_for("home_page"))

    return render_template("landingpage.html")


# =====================================================
# SIGNUP
# =====================================================

@app.route("/signup", methods=["GET", "POST"])
def signup():

    if request.method == "GET":
        return render_template("signup.html")

    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    address = request.form.get("address", "").strip()
    password = request.form.get("password", "")

    if not first_name or not last_name or not email or not password:
        return render_template(
            "signup.html",
            error="Please fill all required fields."
        )

    hashed_password = bcrypt.hashpw(
        password.encode(),
        bcrypt.gensalt()
    ).decode()

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:

        cursor.execute("""
            INSERT INTO users
            (
                first_name,
                last_name,
                email,
                address,
                password
            )
            VALUES
            (%s,%s,%s,%s,%s)
        """, (
            first_name,
            last_name,
            email,
            address,
            hashed_password
        ))

        conn.commit()

    except Exception:
        conn.rollback()

        return render_template(
            "signup.html",
            error="Email already exists."
        )

    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("login_page"))


# =====================================================
# LOGIN
# =====================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM users WHERE email=%s",
        (email,)
    )

    user = cursor.fetchone()

    cursor.close()
    conn.close()

    if user is None:
        return render_template(
            "login.html",
            error="Invalid email or password."
        )

    if not bcrypt.checkpw(
            password.encode(),
            user["password"].encode()):
        return render_template(
            "login.html",
            error="Invalid email or password."
        )

    if user.get("status") == "Blocked":
        return render_template(
            "login.html",
            error="Your account has been blocked."
        )

    session["user_id"] = user["id"]
    session["first_name"] = user["first_name"]
    session["is_admin"] = bool(user.get("is_admin"))

    if session["is_admin"]:
        return redirect(url_for("admin_dashboard"))

    return redirect(url_for("home_page"))


# =====================================================
# LOGOUT
# =====================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("landing_page"))


# =====================================================
# USER PAGES
# =====================================================

@app.route("/home")
@login_required
def home_page():
    return render_template("index.html")


@app.route("/submit_review", methods=["POST"])
@login_required
def submit_review():
    data = request.get_json()

    title = data["title"]
    rating = data["rating"]
    review = data["review"]

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Get movie id from title
    cursor.execute(
    "SELECT id FROM movies WHERE title LIKE %s",
    (f"%{title}%",)
    )
    movie = cursor.fetchone()

    if not movie:
        cursor.close()
        conn.close()
        return jsonify({
            "success": False,
            "message": "Movie not found."
        })

    cursor.execute("""
        INSERT INTO reviews
        (user_id, movie_id, rating, review_text)
        VALUES (%s, %s, %s, %s)
    """, (
        session["user_id"],
        movie["id"],
        rating,
        review
    ))

    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Review submitted successfully."
    })


# =====================================================
# UPDATE PROFILE
# =====================================================




@app.route("/profile/update", methods=["POST"])
@login_required
def update_profile():

    data = request.get_json()

    first_name = data.get("first_name", "").strip()
    last_name = data.get("last_name", "").strip()
    email = data.get("email", "").strip().lower()
    address = data.get("address", "").strip()

    if not first_name or not last_name or not email:
        return jsonify({
            "success": False,
            "message": "First name, last name and email are required."
        }), 400

    conn = get_connection()

    if conn is None:
        return jsonify({
            "success": False,
            "message": "Database connection failed."
        }), 500

    cursor = conn.cursor(dictionary=True)

    try:

        cursor.execute("""
            SELECT id
            FROM users
            WHERE email=%s
            AND id!=%s
        """, (
            email,
            session["user_id"]
        ))

        existing = cursor.fetchone()

        if existing:
            return jsonify({
                "success": False,
                "message": "Email already exists."
            }), 400

        cursor.execute("""
            UPDATE users
            SET
                first_name=%s,
                last_name=%s,
                email=%s,
                address=%s
            WHERE id=%s
        """, (
            first_name,
            last_name,
            email,
            address,
            session["user_id"]
        ))

        conn.commit()

        session["first_name"] = first_name

        return jsonify({
            "success": True,
            "message": "Profile updated successfully."
        })

    except Exception as e:

        conn.rollback()

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

    finally:
        cursor.close()
        conn.close()
@app.route("/profile")
@login_required
def profile_page():

    conn = get_connection()

    if conn is None:
        return "Database connection failed.", 500

    cursor = conn.cursor(dictionary=True)

    user_id = session["user_id"]

    # -------------------------
    # USER
    # -------------------------
    cursor.execute("""
        SELECT *
        FROM users
        WHERE id = %s
    """, (user_id,))
    user = cursor.fetchone()

    # -------------------------
    # COUNTS
    # -------------------------
    cursor.execute("SELECT COUNT(*) AS total FROM watched WHERE user_id=%s", (user_id,))
    watched_count = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM watchlist WHERE user_id=%s", (user_id,))
    watchlist_count = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM favorites WHERE user_id=%s", (user_id,))
    favorites_count = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM reviews WHERE user_id=%s", (user_id,))
    reviews_count = cursor.fetchone()["total"]

    # -------------------------
    # WATCHLIST
    # -------------------------
    cursor.execute("""
        SELECT
            m.id,
            m.title,
            m.poster,
            m.year,
            m.genre,
            m.rating
        FROM watchlist w
        INNER JOIN movies m
            ON w.movie_id = m.id
        WHERE w.user_id = %s
        ORDER BY m.title ASC
    """, (user_id,))

    watchlist = cursor.fetchall()

    # -------------------------
    # FAVORITES
    # -------------------------
    cursor.execute("""
        SELECT
            m.id,
            m.title,
            m.poster,
            m.year,
            m.genre,
            m.rating
        FROM favorites f
        INNER JOIN movies m
            ON f.movie_id = m.id
        WHERE f.user_id = %s
        ORDER BY m.title ASC
    """, (user_id,))

    favorites = cursor.fetchall()

    # -------------------------
    # REVIEWS
    # -------------------------
    cursor.execute("""
        SELECT
            r.id,
            r.movie_id,
            r.rating,
            r.review_text,
            r.status,
            r.created_at,
            m.title,
            m.poster,
            m.year
        FROM reviews r
        INNER JOIN movies m
            ON r.movie_id = m.id
        WHERE r.user_id = %s
        ORDER BY r.created_at DESC
    """, (user_id,))

    reviews = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "profile.html",
        user=user,
        watched_count=watched_count,
        watchlist_count=watchlist_count,
        favorites_count=favorites_count,
        reviews_count=reviews_count,
        watchlist=watchlist,
        favorites=favorites,
        reviews=reviews
    )

# =====================================================
# ADMIN PAGE
# =====================================================

@app.route("/admin")
@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) AS total_users FROM users")
    total_users = cursor.fetchone()["total_users"]

    cursor.execute("SELECT COUNT(*) AS total_movies FROM movies")
    total_movies = cursor.fetchone()["total_movies"]

    cursor.execute("SELECT COUNT(*) AS pending_reviews FROM reviews WHERE status='Pending'")
    pending_reviews = cursor.fetchone()["pending_reviews"]

    cursor.execute("SELECT COUNT(*) AS total_reviews FROM reviews")
    total_reviews = cursor.fetchone()["total_reviews"]

    cursor.execute("""
        SELECT
            id,
            first_name,
            last_name,
            email,
            role,
            status,
            created_at
        FROM users
        WHERE is_admin = 0
        ORDER BY created_at DESC
    """)

    users = cursor.fetchall()
    

    cursor.close()
    conn.close()

    return render_template(
        "admin/admin_dashboard.html",   # Use the correct template path
        total_users=total_users,
        total_movies=total_movies,
        pending_reviews=pending_reviews,
        total_reviews=total_reviews
    )

@app.route("/manage_users")
@admin_required
def manage_users_page():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            id,
            first_name,
            last_name,
            email,
            role,
            status,
            created_at
        FROM users
        WHERE is_admin = 0
        ORDER BY created_at DESC
    """)

    users = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "admin/manage_users.html",
        users=users
    )


@app.route("/manage_movies")
@admin_required
def manage_movies_page():
    return render_template("admin/manage_movies.html")


@app.route("/manage_watchlist")
@admin_required
def manage_watchlist_page():
    return render_template("admin/manage_watchlist.html")

@app.route("/manage_reviews")
@admin_required
def manage_reviews_page():
    return render_template("admin/manage_reviews.html")


@app.route("/api/admin/reviews")
@admin_required
def api_admin_reviews():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            r.id,
            CONCAT(u.first_name, ' ', u.last_name) AS user_name,
            m.title AS movie_title,
            r.rating,
            r.review_text,
            r.status
        FROM reviews r
        JOIN users u ON r.user_id = u.id
        JOIN movies m ON r.movie_id = m.id
        ORDER BY r.created_at DESC
    """)

    reviews = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify(reviews)

# =====================================================
# Review Code
# =====================================================
@app.route("/api/admin/reviews/<int:review_id>/approve", methods=["POST"])
@admin_required
def approve_review(review_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE reviews SET status='Approved' WHERE id=%s",
        (review_id,)
    )

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"success": True})

@app.route("/api/admin/reviews/<int:review_id>", methods=["DELETE"])
@admin_required
def delete_review(review_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM reviews WHERE id=%s",
        (review_id,)
    )

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"success": True})

# =====================================================
# MOVIES API
# =====================================================

@app.route("/api/movies")
def movies():

    data = recommender.df


    movies = []


    for _, movie in data.head(100).iterrows():

        movies.append({

            "id": int(movie["id"]),

            "title": movie["title"],

            "rating": float(
                movie.get(
                    "vote_average",
                    0
                )
            ),

            "genre": movie.get(
                "genres",
                ""
            ),

            "year": movie.get(
                "release_date",
                ""
            ),

            "language": movie.get(
                "original_language",
                ""
            ),

            "description": movie.get(
                "overview",
                ""
            ),

            "poster": movie.get(
                "poster",
                ""
            )

        })


    return jsonify(movies)
# =====================================================
# SINGLE MOVIE DETAILS
# =====================================================

@app.route("/api/movies/<int:movie_id>", methods=["GET"])
@login_required
def api_movie_detail(movie_id):

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT *
        FROM movies
        WHERE id=%s
    """, (movie_id,))

    movie = cursor.fetchone()

    cursor.close()
    conn.close()

    if movie is None:
        return jsonify({
            "success": False,
            "message": "Movie not found."
        }), 404

    return jsonify({
        "success": True,
        "movie": movie
    })


# =====================================================
# MOVIE RECOMMENDATION API
# =====================================================

@app.route("/api/recommendations", methods=["GET", "POST"])
@login_required
def api_recommendations():

    user_id = current_user_id()

    data = request.get_json(silent=True) if request.method == "POST" else {}
    data = data or {}

    genre = data.get("genre", "").strip().lower()
    language = data.get("language", "").strip().lower()
    year = str(data.get("year", "")).strip()

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Get watched movies
    cursor.execute("""
        SELECT m.title
        FROM watched w
        JOIN movies m ON w.movie_id = m.id
        WHERE w.user_id=%s
    """, (user_id,))
    watched = [row["title"] for row in cursor.fetchall()]

    # Get favourite movies
    cursor.execute("""
        SELECT m.title
        FROM favorites f
        JOIN movies m ON f.movie_id = m.id
        WHERE f.user_id=%s
    """, (user_id,))
    favorites = [row["title"] for row in cursor.fetchall()]

    cursor.close()
    conn.close()

    user_movies = list(set(watched + favorites))

    print("=" * 60)
    print("Watched :", watched)
    print("Favorites :", favorites)
    print("User Movies :", user_movies)

    try:

        recommendations = recommender.recommend_for_user(
            user_movies=user_movies,
            top_n=20
        )

        print("Recommendations Returned:", len(recommendations))

        cleaned = []

        for movie in recommendations:

            if isinstance(movie, str):
                cleaned.append({
                "title": movie,
                "poster_url": ""
            })
            else:
                cleaned.append(movie)
        recommendations = cleaned

        # Genre filter
        if genre:
            recommendations = [
                movie for movie in recommendations
                if genre in str(
                    movie.get("genre", movie.get("genres", ""))
                ).lower()
            ]

        # Language filter
        if language:
            recommendations = [
                movie for movie in recommendations
                if language == str(
                    movie.get("language", "")
                ).lower()
            ]

        # Year filter
        if year:
            recommendations = [
                movie for movie in recommendations
                if str(movie.get("year", "")) == year
            ]

        print("After Filters:", len(recommendations))
        print("=" * 60)

        return jsonify({
            "success": True,
            "count": len(recommendations),
            "recommendations": recommendations
        })

    except Exception as e:

        print("Recommendation Error:", e)

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# HELPER FUNCTION
# =====================================================

def _add_to_table(table_name):
    """
    Generic helper to add a movie to:
    - watchlist
    - favorites
    - watched
    """

    data = request.get_json(silent=True) or request.form

    movie_id = data.get("movie_id")

    if not movie_id:
        return jsonify({
            "success": False,
            "message": "movie_id is required."
        }), 400

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute(f"""
            INSERT IGNORE INTO {table_name}
            (user_id, movie_id)
            VALUES (%s, %s)
        """, (
            current_user_id(),
            movie_id
        ))

        conn.commit()

    except Exception as e:

        conn.rollback()

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

    finally:

        cursor.close()
        conn.close()

    return jsonify({
        "success": True,
        "message": "Movie added successfully."
    })


# =====================================================
# WATCHLIST
# =====================================================

@app.route("/api/watchlist", methods=["POST"])
@login_required
def add_watchlist():
    return _add_to_table("watchlist")


# =====================================================
# FAVORITES
# =====================================================

@app.route("/api/favorites", methods=["POST"])
@login_required
def add_favorites():
    return _add_to_table("favorites")


# =====================================================
# WATCHED
# =====================================================

@app.route("/api/watched", methods=["POST"])
@login_required
def add_watched():
    return _add_to_table("watched")


# =====================================================
# CREATE REVIEW
# =====================================================

@app.route("/api/reviews", methods=["POST"])
@login_required
def create_review():

    data = request.get_json(silent=True) or request.form

    movie_id = data.get("movie_id")
    rating = data.get("rating")
    review_text = data.get("text")

    if not movie_id:
        return jsonify({
            "success": False,
            "message": "movie_id is required."
        }), 400

    if not rating:
        return jsonify({
            "success": False,
            "message": "rating is required."
        }), 400

    if not review_text:
        return jsonify({
            "success": False,
            "message": "review text is required."
        }), 400

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            INSERT INTO reviews
            (
                user_id,
                movie_id,
                rating,
                review_text,
                status
            )
            VALUES
            (%s,%s,%s,%s,'Pending')
        """, (
            current_user_id(),
            movie_id,
            rating,
            review_text
        ))

        conn.commit()

    except Exception as e:

        conn.rollback()

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

    finally:

        cursor.close()
        conn.close()

    return jsonify({
        "success": True,
        "message": "Review submitted successfully."
    })


# =====================================================
# HEALTH CHECK
# =====================================================

@app.route("/api/health")
def health():

    return jsonify({
        "success": True,
        "message": "Movix API is running."
    })


# =====================================================
# RUN APPLICATION
# =====================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )