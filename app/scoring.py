# app/scoring.py
from typing import List, Dict

from sklearn.feature_extraction.text import TfidfVectorizer


# Ключевые слова и их веса (можно расширять)
KEYWORD_WEIGHTS: Dict[str, float] = {
    "gpt": 3.0,
    "openai": 3.0,
    "chatgpt": 3.0,
    "midjourney": 2.5,
    "diffusion": 2.0,
    "neural": 2.0,
    "нейросеть": 2.5,
    "нейросети": 2.5,
    "python": 2.5,
    "fastapi": 2.0,
    "django": 2.0,
    "data": 1.5,
    "big data": 2.0,
    "spark": 2.0,
    "kafka": 2.0,
    "security": 1.5,
    "vulnerability": 1.5,
}


def compute_tfidf_scores(texts: List[str]) -> List[float]:
    """
    На вход: список текстов (title+summary+content).
    На выход: список скоров одинаковой длины.
    """
    if not texts:
        return []

    # Простейшая очистка: lower + оставляем как есть
    corpus = [t.lower() for t in texts]

    vectorizer = TfidfVectorizer()
    X = vectorizer.fit_transform(corpus)
    vocab = vectorizer.vocabulary_

    # Индексы ключевых слов, которые реально есть в словаре
    keyword_indices = {}
    for kw, weight in KEYWORD_WEIGHTS.items():
        token = kw.lower()
        if token in vocab:
            keyword_indices[vocab[token]] = weight

    scores: List[float] = []
    for i in range(X.shape[0]):
        row = X.getrow(i)
        score = 0.0

        for col_idx, weight in keyword_indices.items():
            val = row[0, col_idx]
            if val > 0:
                score += val * weight

        # fallback: если ни одного ключевого слова не нашли — берём норму документа
        if score == 0.0:
            score = float(row.power(2).sum()) ** 0.5

        scores.append(score)

    return scores
