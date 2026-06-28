import os
import joblib
import pandas as pd

from sklearn.feature_extraction.text import TfidfVectorizer

MODEL_DIR = "model"
os.makedirs(MODEL_DIR, exist_ok=True)

print("Loading dataset...")

df = pd.read_csv("dataset/movies.csv")

for col in ['genres','keywords','cast','director','title']:
    df[col] = df[col].fillna('').astype(str)

df['title_norm'] = df['title'].str.lower().str.strip()

df['soup'] = (
    df['genres'] + " " +
    df['keywords'] + " " +
    df['cast'] + " " +
    df['director']
)

print("Training TF-IDF...")

vectorizer = TfidfVectorizer(stop_words="english")

tfidf_matrix = vectorizer.fit_transform(df["soup"])

print("Saving model...")

joblib.dump(df, "model/movies_df.pkl")
joblib.dump(vectorizer, "model/vectorizer.pkl")
joblib.dump(tfidf_matrix, "model/tfidf_matrix.pkl")

print("Model Saved Successfully!")