import joblib
import os
from sklearn.metrics.pairwise import cosine_similarity


class MovieRecommender:

    def __init__(self):

        model_path = "model"

        self.df = joblib.load(
            os.path.join(model_path, "movies_df.pkl")
        )

        self.vectorizer = joblib.load(
            os.path.join(model_path, "vectorizer.pkl")
        )

        self.matrix = joblib.load(
            os.path.join(model_path, "tfidf_matrix.pkl")
        )


    # -----------------------------------
    # Recommend movies for a user
    # -----------------------------------
    def recommend_for_user(self, user_movies=None, top_n=10):

        if not user_movies:
            return self._fallback(top_n)


        movie_indices = []


        for movie in user_movies:

            if movie is None:
                continue

            movie = str(movie).lower().strip()


            result = self.df[
                self.df["title_norm"] == movie
            ]


            if not result.empty:
                movie_indices.append(
                    result.index[0]
                )


        # If user movies are not found
        if len(movie_indices) == 0:
            return self._fallback(top_n)



        # Calculate similarity
        similarity = cosine_similarity(
            self.matrix[movie_indices],
            self.matrix
        )


        # Average similarity score
        scores = similarity.mean(axis=0)


        ranked_movies = scores.argsort()[::-1]


        watched = set(
            [
                str(movie).lower().strip()
                for movie in user_movies
            ]
        )


        recommendations = []


        for index in ranked_movies:


            movie = self.df.iloc[index]


            if movie["title"].lower().strip() in watched:
                continue



            recommendations.append({

                "id": int(movie["id"]),

                "title": str(movie["title"]),

                "genres":
                    str(movie.get("genres", "")),

                "overview":
                    str(movie.get("overview", "")),

                "poster":
                    movie.get("poster", None),

                "vote_average":
                    float(movie.get(
                        "vote_average",
                        0
                    )),

                "popularity":
                    float(movie.get(
                        "popularity",
                        0
                    )),

                "release_date":
                    str(movie.get(
                        "release_date",
                        ""
                    )),

                "language":
                    str(movie.get(
                        "original_language",
                        ""
                    ))

            })



            if len(recommendations) >= top_n:
                break



        return recommendations



    # -----------------------------------
    # Recommend based on one movie
    # -----------------------------------
    def recommend(self, movie_title, top_n=10):

        return self.recommend_for_user(
            [
                movie_title
            ],
            top_n
        )



    # -----------------------------------
    # Popular movies fallback
    # -----------------------------------
    def _fallback(self, top_n):


        if "popularity" in self.df.columns:


            movies = (
                self.df
                .sort_values(
                    "popularity",
                    ascending=False
                )
                .head(top_n)
            )


        else:

            movies = self.df.head(top_n)



        result = []


        for _, movie in movies.iterrows():

            result.append({

                "id": int(movie["id"]),

                "title":
                    str(movie["title"]),

                "genres":
                    str(movie.get(
                        "genres",
                        ""
                    )),

                "overview":
                    str(movie.get(
                        "overview",
                        ""
                    )),

                "vote_average":
                    float(movie.get(
                        "vote_average",
                        0
                    )),

                "popularity":
                    float(movie.get(
                        "popularity",
                        0
                    ))

            })


        return result