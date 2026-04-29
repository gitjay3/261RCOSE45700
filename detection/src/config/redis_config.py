from __future__ import annotations

import os

import redis

from shared.config.redis_config import REDIS_MQ_DB, REDIS_RATELIMIT_DB


def get_mq_client() -> redis.Redis:
    url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    return redis.from_url(url, db=REDIS_MQ_DB, decode_responses=True)


def get_rate_limit_client() -> redis.Redis:
    url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    return redis.from_url(url, db=REDIS_RATELIMIT_DB, decode_responses=True)
