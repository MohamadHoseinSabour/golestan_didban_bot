# Architecture & Data Flow (Phase 3)

## 1. System Overview

```mermaid
flowchart TD
    User([Divar Website]) -->|Search URL| Config[config.yaml / .env]
    Config --> Monitor[Monitor Engine]
    
    subgraph Divar Module
        URLBuilder[url_builder.py] -->|Protobuf Search Payload| Client[DivarClient]
        Client -->|POST /v8/postlist/w/search| DivarAPI[(Divar API)]
        DivarAPI -->|List Widgets| Client
        Client -->|GET /v8/posts-v2/web/:token| DivarAPI
        DivarAPI -->|Detail JSON| Parser[parser.py]
        Parser -->|Ad Object| Classifier[classifier.py]
    end
    
    subgraph Storage & State
        Storage[(SQLite aiosqlite)] <-->|is_known / mark_seen / mark_notified| Monitor
    end
    
    subgraph Telegram Module
        Classifier -->|Personal Ad| Formatter[formatter.py]
        Formatter -->|HTML Message| Bot[TelegramBot]
        Bot -->|Telegram Bot API| UserTG([Allowed Telegram User])
        UserTG -->|Commands: /status, /pause, ...| Security[security.py]
        Security --> Bot
    end
    
    Monitor --> URLBuilder
    Parser --> Monitor
    Classifier --> Monitor
    Monitor --> Formatter
```

---

## 2. Monitoring Cycle Sequence

```mermaid
sequenceDiagram
    autonumber
    participant M as Monitor
    participant S as SQLite Storage
    participant C as DivarClient
    participant P as Parser & Classifier
    participant T as TelegramBot

    Note over M: Every 60s (± jitter)
    M->>S: start_cycle()
    M->>C: fetch_listings()
    C-->>M: list_widgets (tokens)
    
    loop For each token in listings
        M->>S: is_known(token)
        alt token is already known
            Note over M: Skip (seen / notified)
        else token is new
            M->>S: mark_seen(token)
            M->>C: fetch_detail(token)
            C-->>M: detail_json
            M->>P: parse & classify(detail_json)
            alt Classified as AGENCY
                M->>S: mark_skipped_agency(token, reason)
            else Classified as PERSONAL
                alt Older than MAX_AD_AGE_MINUTES
                    M->>S: mark_skipped_old(token)
                else Valid & Fresh
                    M->>T: send_notification(ad)
                    T-->>M: success (message_id)
                    M->>S: mark_notified(token, message_id)
                end
            end
        end
    end
    
    M->>S: end_cycle(stats)
```

---

## 3. Data Flow & Security
- **Strict Access Control:** Every incoming Telegram update is checked against `ALLOWED_USER_IDS`. Unauthorized users receive zero responses (stealth mode) and are only logged.
- **Fail-safe State Machine:** An ad is only marked `notified` after Telegram confirms HTTP 200 delivery. Failed sends remain pending or are retried next cycle.
- **Circuit Breaker:** If 3 consecutive cycles encounter network/blocking errors, a single health alert is sent to Telegram, suppressing spam until recovered.
