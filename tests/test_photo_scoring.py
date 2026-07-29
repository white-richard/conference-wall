from confwall.photos import score_pexels_candidate


def test_score_pexels_candidate_high_score():
    photo = {
        "width": 2400,
        "height": 1350,
        "alt": "Las Vegas Nevada USA aerial skyline view",
    }
    score = score_pexels_candidate(photo, city="Las Vegas", country="USA", region="NV")
    assert score == 27


def test_score_pexels_candidate_penalties():
    photo = {
        "width": 1920,
        "height": 1200,
        "alt": "Las Vegas hotel room interior with person eating food near sign",
    }
    score = score_pexels_candidate(photo, city="Las Vegas", country="USA", region="NV")
    # City: +10, ratio >= 1.6 (+2), width >= 1920 (+2) -> 14
    # person (-5), food (-4), interior (-4), hotel room (-4), sign (-3) -> -20
    # Net = -6
    assert score == -6
