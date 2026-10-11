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


def test_parse_detail_with_phone_numbers():
    fake_data = {
        "webengage": {
            "city": "ahvaz",
            "district": "golestan",
            "category": "apartment-sell",
            "price": 2000000000,
        },
        "seo": {
            "title": "فروش واحد ۹۰ متری (تماس: 09161234567)",
        },
        "sections": [
            {
                "section_name": "DESCRIPTION",
                "widgets": [
                    {
                        "widget_type": "DESCRIPTION_ROW",
                        "data": {
                            "text": "واحد فوق العاده شیک. مالک مستقیم: ۰۹۱۲۳۴۵۶۷۸۹ و واتساپ: +989169998877",
                        },
                    }
                ],
            },
            {
                "section_name": "LIST_DATA",
                "widgets": [
                    {
                        "widget_type": "UNEXPANDABLE_ROW",
                        "data": {
                            "title": "تلفن دفتر هماهنگی",
                            "value": "061-33731122",
                        },
                    }
                ],
            },
        ],
    }

    ad = DivarParser.parse_detail("phone_test_1", fake_data, extra_phones=["09351112233"])
    assert ad.token == "phone_test_1"
    # Extra phone + title phone + description phones + widget phone
    assert "09351112233" in ad.contact_phones
    assert "09161234567" in ad.contact_phones
    assert "09123456789" in ad.contact_phones
    assert "09169998877" in ad.contact_phones
    assert "06133731122" in ad.contact_phones
    assert ad.contact_phone == "09351112233"  # First in list


def test_extract_phones_from_contact():
    contact_json = {
        "widgets": [
            {
                "widget_type": "UNEXPANDABLE_ROW",
                "data": {"title": "شماره تلفن", "value": "۰۹۱۶۱۲۳۴۵۶۷"},
            }
        ],
        "phone": "09161234567",
    }
    phones = DivarParser.extract_phones_from_contact(contact_json)
    assert phones == ["09161234567"]
    assert DivarParser.extract_phones_from_contact({}) == []


def test_classifier_personal_disclaimer_not_flagged_as_agency():
    """Ensure private landlord disclaimers ('املاک تماس نگیرد') are NOT falsely flagged as agency."""
    classifier = AdClassifier()

    disclaimer_samples = [
        "واحد خیلی لوکس خیابان اصفهان ... املاک تماس نگیره فقط رهن کامل ممنونم",
        "ادرس گلستان خیابان اقبال نبش دماوند همکار بنگاهی لطفا تماس نفرمایید",
        "رهن کامل آپارتمان ۹۰ متری، لطفا مشاورین املاک تماس نگیرند",
        "واحد ۷۵ متری کلید اول، بدون واسطه املاک، مستقیم با مالک",
        "رهن و اجاره شخصی، همکاری با املاک نداریم",
    ]

    for desc in disclaimer_samples:
        data = {
            "webengage": {"business_type": "personal"},
            "seo": {"title": "رهن و اجاره آپارتمان"},
            "sections": [
                {
                    "section_name": "DESCRIPTION",
                    "widgets": [
                        {"widget_type": "DESCRIPTION_ROW", "data": {"text": desc}}
                    ],
                }
            ],
        }
        res, reason = classifier.classify(data)
        assert res == ClassifierResult.PERSONAL, f"Failed on disclaimer: '{desc}' -> {reason}"


def test_classifier_agency_with_disclaimer_still_flagged():
    """Ensure agency ads that include both disclaimers and agency markers are still flagged as AGENCY."""
    classifier = AdClassifier()

    agency_samples = [
        "با املاک همکاری نمیشود چون خودم مشاوراملاکم",
        "با املاک همکاری نمیشود. آدرس دفتر املاک بنیامین خیابان اردیبهشت",
        "رهن کامل آپارتمان، املاک تماس نگیرد. مشاور شما در دپارتمان املاک ناصری",
    ]

    for desc in agency_samples:
        data = {
            "webengage": {"business_type": "personal"},
            "seo": {"title": "رهن آپارتمان"},
            "sections": [
                {
                    "section_name": "DESCRIPTION",
                    "widgets": [
                        {"widget_type": "DESCRIPTION_ROW", "data": {"text": desc}}
                    ],
                }
            ],
        }
        res, reason = classifier.classify(data)
        assert res == ClassifierResult.AGENCY, f"Should be AGENCY for: '{desc}'"


def test_parse_rent_without_hamza_and_various_labels():
    """Ensure mortgage/rent amounts are extracted properly regardless of hamza or label variations."""
    fake_data = {
        "webengage": {"category": "apartment-rent"},
        "seo": {"title": "رهن و اجاره واحد ۸۰ متری"},
        "sections": [
            {
                "section_name": "LIST_DATA",
                "widgets": [
                    {
                        "widget_type": "UNEXPANDABLE_ROW",
                        "data": {"title": "ودیعه (قرض‌الحسنه)", "value": "۴۰۰,۰۰۰,۰۰۰ تومان"},
                    },
                    {
                        "widget_type": "UNEXPANDABLE_ROW",
                        "data": {"title": "اجاره ماهانه", "value": "۱۲,۰۰۰,۰۰۰ تومان"},  # without hamza
                    },
                    {
                        "widget_type": "UNEXPANDABLE_ROW",
                        "data": {"title": "ودیعه و اجاره", "value": "قابل تبدیل"},
                    },
                ],
            }
        ],
    }

    ad = DivarParser.parse_detail("rent_test_1", fake_data)
    assert ad.ad_category == AdCategory.RENT
    assert ad.mortgage == 400000000
    assert ad.monthly_rent == 12000000
    assert ad.convertible is True

