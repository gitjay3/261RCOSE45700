REDIS_MQ_DB: int = 0
REDIS_DEDUP_DB: int = 1
REDIS_RATELIMIT_DB: int = 2
REDIS_CACHE_DB: int = 3

REDIS_KEY_POSTS_QUEUE: str = "posts:queue"
REDIS_KEY_POSTS_PROCESSING: str = "posts:processing"
REDIS_KEY_POSTS_DLQ: str = "posts:dlq"
REDIS_KEY_POSTS_CORRUPT: str = "posts:corrupt"
REDIS_KEY_POSTS_DEDUP: str = "posts:dedup"

# 2026-05-27 PIVOT — VARCO Translation/LLM 폐기, OpenAI 멀티모달 LLM 단일 호출로 교체.
# varco:rate_limit:classify → llm:rate_limit:classify (Story 3-3).
REDIS_KEY_LLM_RATE_LIMIT_CLASSIFY: str = "llm:rate_limit:classify"

REDIS_CHANNEL_CRAWL_TRIGGER: str = "crawl:trigger"
