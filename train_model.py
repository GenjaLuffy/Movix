import os
import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

# ==============================
# Create model directory
# ==============================
MODEL_DIR = "model"
os.makedirs(MODEL_DIR, exist_ok=True)

print("Loading dataset...")

# Load dataset
df = pd.read_csv("dataset/movies.csv")

# ==============================
# Fill missing values
# ==============================
text_columns = [
    "title",
    "genres",
    "keywords",
    "cast",
    "director",
    "overview"
]

for col in text_columns:
    df[col] = df[col].fillna("").astype(str)

# ==============================
# Normalize movie titles
# Used by recommender.py
# ==============================
df["title_norm"] = df["title"].str.lower().str.strip()

# ==============================
# Create feature soup
# ==============================
df["soup"] = (
    df["genres"] + " " +
    df["keywords"] + " " +
    df["cast"] + " " +
    df["director"] + " " +
    df["overview"]
)

print("Training TF-IDF model...")

# Create TF-IDF matrix
vectorizer = TfidfVectorizer(stop_words="english")

tfidf_matrix = vectorizer.fit_transform(df["soup"])

print("Saving model...")

# Save everything
joblib.dump(df, os.path.join(MODEL_DIR, "movies_df.pkl"))
joblib.dump(vectorizer, os.path.join(MODEL_DIR, "vectorizer.pkl"))
joblib.dump(tfidf_matrix, os.path.join(MODEL_DIR, "tfidf_matrix.pkl"))

print("Model saved successfully!")