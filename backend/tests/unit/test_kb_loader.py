from knowledge.kb_loader import compute_freshness_score, compute_content_hash, validate_entry, load_from_dicts


def test_freshness_score_recent_publication():
    score = compute_freshness_score(2025, 2026)
    assert score > 0.8


def test_freshness_score_over_5_years_decay():
    score = compute_freshness_score(2019, 2026)
    assert score < 0.5


def test_freshness_score_very_old():
    score = compute_freshness_score(1990, 2026)
    assert score == 0.0


def test_content_hash_same_input_produces_same_hash():
    h1 = compute_content_hash("同一段内容")
    h2 = compute_content_hash("同一段内容")
    assert h1 == h2


def test_content_hash_different_input_produces_different_hash():
    h1 = compute_content_hash("内容A")
    h2 = compute_content_hash("内容B")
    assert h1 != h2


def test_validate_entry_rejects_missing_required_fields():
    assert validate_entry({"title": "", "source": "s", "source_type": "guideline", "publish_year": 2023, "content": "text"}) is False
    assert validate_entry({"title": "T", "source": "s", "source_type": "guideline", "publish_year": 2023, "content": "text"}) is True


def test_load_from_dicts_deduplicates_by_content_hash():
    entries = [
        {"title": "T1", "source": "S1", "source_type": "guideline", "publish_year": 2023, "content": "identical"},
        {"title": "T2", "source": "S2", "source_type": "review", "publish_year": 2022, "content": "identical"},
    ]
    result = load_from_dicts(entries)
    assert len(result) == 1


def test_load_from_dicts_sets_authority_default_by_source_type():
    entries = [
        {"title": "G", "source": "S", "source_type": "guideline", "publish_year": 2023, "content": "c1"},
        {"title": "T", "source": "S", "source_type": "textbook", "publish_year": 2022, "content": "c2"},
        {"title": "C", "source": "S", "source_type": "case_report", "publish_year": 2021, "content": "c3"},
    ]
    result = load_from_dicts(entries)
    assert result[0]["authority_score"] == 0.9
    assert result[1]["authority_score"] == 0.6
    assert result[2]["authority_score"] == 0.2
