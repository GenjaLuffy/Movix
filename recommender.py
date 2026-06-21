import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class MovieRecommender:
    def __init__(self, csv_path):
        self.df = pd.read_csv(csv_path)

        # normalize columns safely
        for col in ['genres', 'keywords', 'cast', 'director', 'title']:
            if col in self.df.columns:
                self.df[col] = self.df[col].fillna('').astype(str)

        self.df['title_norm'] = self.df['title'].str.lower().str.strip()

        # build content "soup"
        self.df['soup'] = (
            self.df.get('genres', '') + " " +
            self.df.get('keywords', '') + " " +
            self.df.get('cast', '') + " " +
            self.df.get('director', '')
        )

        self.vectorizer = TfidfVectorizer(stop_words='english')
        self.matrix = self.vectorizer.fit_transform(self.df['soup'])

        self.similarity = cosine_similarity(self.matrix)

        self.df = self.df.reset_index(drop=True)

    def recommend_for_user(self, user_movies, top_n=10):
        if not user_movies:
            return self._fallback(top_n)

        indices = []

        for title in user_movies:
            title = title.lower().strip()
            match = self.df[self.df['title_norm'] == title]

            if not match.empty:
                indices.append(match.index[0])

        if not indices:
            return self._fallback(top_n)

        scores = self.similarity[indices].mean(axis=0)

        ranked = scores.argsort()[::-1]

        seen = set([m.lower().strip() for m in user_movies])
        results = []

        for i in ranked:
            title = self.df.iloc[i]['title']

            if title.lower().strip() in seen:
                continue

            results.append(self.df.iloc[i].to_dict())

            if len(results) == top_n:
                break

        return results

    def _fallback(self, top_n):
        return (
            self.df.sort_values("popularity", ascending=False)
            .head(top_n)
            .to_dict(orient="records")
        )