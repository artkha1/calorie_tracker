from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# TODO: take into account nutrients too?

SIMILARITY_THRESHOLD = 0.75


def deduplicate_foods(foods: list[dict]) -> list[dict]:
    """
    Given a list of food dicts, remove near-duplicates using TF-IDF cosine
    similarity on food descriptions. For each group of similar foods, keeps
    the one with the most complete nutrient data.

    Example: "Chicken, broiled", "Chicken, broiled, skin removed", 
             "Chicken, broiled (USDA)" would collapse to one result.
    """
    if len(foods) <= 1:
        return foods

    descriptions = [f["name"].lower() for f in foods]

    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(descriptions)
    sim_matrix = cosine_similarity(tfidf_matrix)

    # Greedily cluster: assign each food to the first sufficiently similar food
    # that came before it (i.e. keep the earlier/more complete representative)
    assigned = [-1] * len(foods)
    cluster_rep = []  # index of the representative for each cluster

    for i in range(len(foods)):
        if assigned[i] != -1:
            continue  # already assigned to a cluster

        # Start a new cluster with i as representative
        assigned[i] = i
        cluster_rep.append(i)

        for j in range(i + 1, len(foods)):
            if assigned[j] == -1 and sim_matrix[i][j] >= SIMILARITY_THRESHOLD:
                assigned[j] = i  # assign j to cluster i

    # For each cluster, pick the food with the most non-None nutrient values
    clusters = {}
    for food_idx, rep_idx in enumerate(assigned):
        clusters.setdefault(rep_idx, []).append(food_idx)

    result = []
    for rep_idx, members in clusters.items():
        best = max(members, key=lambda idx: sum(
            1 for v in foods[idx].values() if v is not None
        ))
        result.append(foods[best])

    return result