import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class MovieRecommender:
    def __init__(self, dataset_path):

        self.df = pd.read_csv(dataset_path)

        # clean data
        self.df["genres"] = self.df["genres"].fillna("")

        # feature column
        self.df["features"] = self.df["genres"]

        # vectorizer
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.matrix = self.vectorizer.fit_transform(self.df["features"])

    # ==========================================
    # 🔥 MEMORY SAFE RECOMMENDER
    # ==========================================
    def recommend_for_user(self, user_movies, top_n=10):

        if not user_movies:
            return self.df.sample(top_n).to_dict(orient="records")

        # get indices of user movies
        indices = self.df[self.df["title"].isin(user_movies)].index

        if len(indices) == 0:
            return self.df.sample(top_n).to_dict(orient="records")

        # compute similarity ONLY WHEN NEEDED
        scores = None

        for idx in indices:
            sim = cosine_similarity(self.matrix[idx], self.matrix).flatten()

            if scores is None:
                scores = sim
            else:
                scores += sim

        # rank movies
        ranked = scores.argsort()[::-1]

        results = []
        seen = set(user_movies)

        for i in ranked:
            title = self.df.iloc[i]["title"]

            if title not in seen:
                results.append(self.df.iloc[i])

            if len(results) == top_n:
                break

        return pd.DataFrame(results).to_dict(orient="records")