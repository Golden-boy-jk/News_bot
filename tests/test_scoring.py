from app.scoring import compute_tfidf_scores


def test_compute_tfidf_scores_length():
    texts = [
        "openai gpt chatgpt release",
        "просто какой-то рандомный текст без ключевых слов",
        "midjourney diffusion model update",
    ]
    scores = compute_tfidf_scores(texts)

    assert len(scores) == len(texts)
    # все — числа
    assert all(isinstance(s, float) for s in scores)


def test_compute_tfidf_scores_relevant_higher():
    relevant = "openai gpt chatgpt new model"
    neutral = "какой-то текст про погоду и еду"

    scores = compute_tfidf_scores([relevant, neutral])
    score_relevant, score_neutral = scores

    # релевантный текст должен быть не хуже нейтрального, а чаще всего выше
    assert score_relevant >= score_neutral
