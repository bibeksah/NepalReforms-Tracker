import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from tracker.agents.policy_categories import classify_policy_category


def test_classify_policy_category_normalizes_known_alias():
    result = classify_policy_category(raw_category="Federalism and Local Governance")

    assert result.slug == "federalism_local_governance"
    assert result.display_name == "Federalism & Local Governance"
    assert result.source == "normalized"


def test_classify_policy_category_infers_from_text_keywords():
    result = classify_policy_category(
        title="Expand irrigation canals and fertilizer access",
        summary="Support farmers and crop productivity in every district.",
    )

    assert result.slug == "agriculture"
    assert result.display_name == "Agriculture"
    assert result.source == "inferred"


def test_classify_policy_category_falls_back_to_other():
    result = classify_policy_category(title="Build a future-ready nation")

    assert result.slug == "other"
    assert result.display_name == "Other"
    assert result.source == "fallback"
