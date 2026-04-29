REDIS_MQ_DB: int = 0
REDIS_DEDUP_DB: int = 1
REDIS_RATELIMIT_DB: int = 2
REDIS_CACHE_DB: int = 3

REDIS_KEY_POSTS_QUEUE: str = "posts:queue"
REDIS_KEY_POSTS_PROCESSING: str = "posts:processing"
REDIS_KEY_POSTS_DLQ: str = "posts:dlq"
REDIS_KEY_POSTS_CORRUPT: str = "posts:corrupt"
REDIS_KEY_POSTS_DEDUP: str = "posts:dedup"

REDIS_KEY_VARCO_RATE_LIMIT_TRANSLATE: str = "varco:rate_limit:translate"
REDIS_KEY_VARCO_RATE_LIMIT_CLASSIFY: str = "varco:rate_limit:classify"

REDIS_CHANNEL_CRAWL_TRIGGER: str = "crawl:trigger"
