# Divar Reconnaissance Report (Phase 2)

**Generated:** 2026-10-04 / 2026-10-05  
**Target:** Divar Real-Estate Listings (Ahvaz, Golestan, Personal Only)

---

## 1. robots.txt and Terms of Use
- URL: `https://divar.ir/robots.txt`
- Rule for general web crawlers:
  - Disallowed: `/my-divar/*`, `/new`, `/s/*/*?*q=*`, `/adminbot`
  - Search listing pages (e.g. `/s/ahvaz/real-estate/golestan`) are **allowed**.
- Policy for monitoring:
  - Low frequency (1 request per 60 seconds with jitter).
  - No scraping of phone numbers or contact data.
  - Detail requests are only triggered for newly discovered tokens.

---

## 2. API Endpoints Discovered

### A. Listing Search Endpoint
- **URL:** `POST https://api.divar.ir/v8/postlist/w/search`
- **Method:** `POST`
- **Headers:**
  ```http
  User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36
  Accept: application/json, text/plain, */*
  Accept-Language: fa,en;q=0.9
  x-web-serving-mode: desktop
  Content-Type: application/json
  ```
- **Payload Schema (Protobuf JSON format):**
  ```json
  {
    "city_ids": ["7"],
    "search_data": {
      "form_data": {
        "data": {
          "category": {"str": {"value": "real-estate"}},
          "business-type": {"repeated_string": {"value": ["personal"]}},
          "districts": {"repeated_string": {"value": ["323"]}},
          "bbox": {
            "repeated_float": {
              "value": [
                {"value": 48.6043},
                {"value": 31.2658939},
                {"value": 48.6834793},
                {"value": 31.3184261}
              ]
            }
          }
        }
      }
    }
  }
  ```
  *(Note: Omit `pagination_data` on initial page or use `type.googleapis.com/post_list.PaginationData`)*

- **Response Structure:**
  - `list_widgets`: Array of 24+ widgets. Each post widget has `widget_type == "POST_ROW"`.
  - `data.token`: Unique listing identifier string (e.g., `"gaC7Lwp7"`).
  - `data.title`: Short listing title.
  - `data.image_url`: Thumbnail image URL.
  - `data.bottom_description_text`: Persian neighborhood / time text (e.g., `"در گلستان"`).
  - `data.middle_description_text`: Price preview text.
  - `pagination`: Contains `data.last_post_date` for pagination cursor.

---

### B. Listing Detail Endpoint
- **URL:** `GET https://api.divar.ir/v8/posts-v2/web/{token}`
- **Method:** `GET`
- **Headers:** Same browser headers as above.
- **Response Structure:**
  1. `webengage`: Clean metadata object:
     - `business_type`: `"personal"` or `"premium-panel"`
     - `business_ref`: `""` for personal, or agency identifier string for real-estate offices
     - `category`: e.g. `"apartment-sell"`, `"residential-rent"`, `"suite-apartment"`
     - `price`: Raw integer (Total price in Tomans)
     - `credit`: Raw integer (Mortgage / ودیعه in Tomans)
     - `rent`: Raw integer (Monthly rent / اجاره ماهانه in Tomans)
     - `token`: String token
  2. `sections`: Array of display sections:
     - **Section 1 (TITLE):**
       - `LEGEND_TITLE_ROW`: Full post title.
       - `EXPANDABLE_SECTION`: Contains relative publication time & full location address (e.g. `"۱ ساعت پیش در اهواز، گلستان، خ اصفهان"`).
     - **Section 2 (DESCRIPTION):**
       - `DESCRIPTION_ROW`: Full description text.
     - **Section 3 (IMAGE):**
       - `IMAGE_CAROUSEL` or `IMAGE_SLIDER`: Array of full-size image objects.
     - **Section 4 (LIST_DATA):**
       - `GROUP_INFO_ROW`: Array of key-value pairs (متراژ, ساخت, اتاق).
       - `UNEXPANDABLE_ROW`: Price, floor (`طبقه`), convertibility (`ودیعه و اجاره`).
       - `GROUP_FEATURE_ROW`: Boolean availability of `آسانسور`, `پارکینگ`, `انباری`.
     - **Section 5 (TAGS):**
       - Tags such as `فوری`, `تخفیف‌دار`, `قابل معاوضه`.

---

## 3. Verification of `bbox` Parameter
- Tested listing responses with district-only vs district + bbox:
  - District only: Returns listings within Ahvaz Golestan (district 323).
  - District + bbox: Filters strictly to the bounding box polygon, resulting in slightly different tokens matching user's map viewport.
- **Decision:** `use_bbox: true` is enabled by default in `config.yaml` when bbox is present in the URL.

---

## 4. Verification of Personal vs Agency Filter
- Tested 26 listings with `business-type: personal` vs 26 listings unfiltered:
  - **With filter:** 100% of tested listings had `webengage.business_type == "personal"` and `webengage.business_ref == ""`.
  - **Without filter:** 40% of listings belonged to agencies (`webengage.business_type == "premium-panel"` with a `business_ref` id).
- **Two-layer defense:**
  1. First layer: API query filter `business-type: personal`.
  2. Second layer: Detail verification checking `business_type == "personal"`, `business_ref == ""` and scanning title/description against blacklist keywords (`املاک`, `مشاور`, `بنگاه`, `آژانس`, etc.).

---

## 5. Location ID Resolution
- Fetched `https://map.divarcdn.com/places-web.json` (4037 places across Iran).
- Confirmed IDs:
  - `ahvaz` (City) -> ID `7`
  - `golestan-ahvaz` (District) -> ID `323` (parent: 7)
- The bot includes a built-in resolver that parses `/s/{city}/real-estate/{neighborhood}` into `city_id` and `district_id`.
