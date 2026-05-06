package com.tracker.api.service;

import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class CrawlTriggerService {

    private static final String CRAWL_TRIGGER_CHANNEL = "crawl:trigger";

    private final StringRedisTemplate stringRedisTemplate;

    public void trigger(String correlationId) {
        // Redis PUBLISH may return 0 when no crawler is subscribed; Story 4.2 treats the command as accepted.
        stringRedisTemplate.convertAndSend(CRAWL_TRIGGER_CHANNEL, correlationId);
    }
}
