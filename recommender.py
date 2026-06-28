import joblib
from sklearn.metrics.pairwise import cosine_similarity


class MovieRecommender:

    def __init__(self):
        self.df = joblib.load("model/movies_df.pkl")
        self.vectorizer = joblib.load("model/vectorizer.pkl")
        self.matrix = joblib.load("model/tfidf_matrix.pkl")

    def recommend_for_user(self, user_movies=None, top_n=10):

        if user_movies is None:
            user_movies = []

        if len(user_movies) == 0:
            return self._fallback(top_n)

        indices = []

        for movie in user_movies:

            movie = movie.lower().strip()

            match = self.df[self.df["title_norm"] == movie]

            if not match.empty:
                indices.append(match.index[0])

        if len(indices) == 0:
            return self._fallback(top_n)

        similarity = cosine_similarity(
            self.matrix[indices],
            self.matrix
        )

        scores = similarity.mean(axis=0)

        ranked = scores.argsort()[::-1]

        seen = {m.lower().strip() for m in user_movies}

        recommendations = []

        for i in ranked:

            row = self.df.iloc[i]

            if row["title"].lower().strip() in seen:
                continue

            recommendations.append(row.to_dict())

            if len(recommendations) >= top_n:
                break

        return recommendations

    def _fallback(self, top_n):

        if "popularity" in self.df.columns:
            return (
                self.df
                .sort_values("popularity", ascending=False)
                .head(top_n)
                .to_dict("records")
            )

        return self.df.head(top_n).to_dict("records")