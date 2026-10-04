"""
Unit tests for DivarParser and AdClassifier using real recorded fixtures.
"""
import json
from pathlib import Path

from divar_bot.divar.classifier import AdClassifier
from divar_bot.divar.parser import DivarParser
from divar_bot.models import AdCategory, ClassifierResult

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def test_parse_listing_widgets():
    fixture_path = FIXTURES_DIR / "postlist_search.json"
    assert fixture_path.exists(), "postlist_search.json fixture missing"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    widgets = data.get("list_widgets", [])
    assert len(widgets) > 0

    parsed = []
    for w in widgets:
        if w.get("widget_type") == "POST_ROW":
            summary = DivarParser.parse_listing_widget(w)
            if summary:
                parsed.append(summary)

    assert len(parsed) >= 20
    assert all(p["token"] for p in parsed)
    assert any("گلستان" in (p["bottom_desc"] or "") for p in parsed)


def test_parse_detail_sell():
    fixture_path = FIXTURES_DIR / "detail_ga-m0OiH.json"
    assert fixture_path.exists(), "detail_ga-m0OiH.json fixture missing"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))

    ad = DivarParser.parse_detail("ga-m0OiH", data)
    assert ad.token == "ga-m0OiH"
    assert ad.ad_category == AdCategory.SELL
    assert ad.total_price == 10200000512
    assert ad.area_m2 == 120.0
    assert ad.rooms == 3
    assert ad.year_built == 1388
    assert ad.has_elevator is True
    assert ad.has_parking is True
    assert ad.has_storage is True
    assert ad.floor == 1
    assert ad.total_floors == 5


def test_parse_detail_rent():
    fixture_path = FIXTURES_DIR / "detail_gaC7Lwp7.json"
    assert fixture_path.exists(), "detail_gaC7Lwp7.json fixture missing"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))

    ad = DivarParser.parse_detail("gaC7Lwp7", data)
    assert ad.token == "gaC7Lwp7"
    assert ad.area_m2 == 154.0
    assert ad.rooms == 1
    assert ad.year_built == 1402
    assert ad.mortgage == 2500000000
    assert ad.monthly_rent == 1000
    assert ad.convertible is False
    assert ad.has_elevator is True
    assert ad.has_parking is True
    assert ad.has_storage is True


def test_classifier_personal_ad():
    classifier = AdClassifier()
    fixture_path = FIXTURES_DIR / "detail_ga-m0OiH.json"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))

    result, reason = classifier.classify(data)
    assert result == ClassifierResult.PERSONAL
    assert "personal" in reason.lower()


def test_classifier_agency_with_ref():
    classifier = AdClassifier()
    fake_agency_data = {
        "webengage": {
            "business_type": "premium-panel",
            "business_ref": "agency_12345",
        },
        "seo": {"title": "فروش آپارتمان"},
        "sections": [],
    }

    result, reason = classifier.classify(fake_agency_data)
    assert result == ClassifierResult.AGENCY
    assert "premium-panel" in reason or "business_ref" in reason


def test_classifier_keyword_match():
    classifier = AdClassifier()
    fake_data = {
        "webengage": {"business_type": "personal", "business_ref": ""},
        "seo": {"title": "فروش واحد توسط مشاور املاک مهر"},
        "sections": [],
    }

    result, reason = classifier.classify(fake_data)
    assert result == ClassifierResult.AGENCY
    assert "املاک" in reason or "مشاور" in reason
