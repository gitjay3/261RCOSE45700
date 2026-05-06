package com.tracker.api.service;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.redis.core.StringRedisTemplate;

import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class CrawlTriggerServiceTest {

    @Mock
    StringRedisTemplate stringRedisTemplate;

    @Test
    void trigger_publishesCorrelationIdToCrawlTriggerChannel() {
        var service = new CrawlTriggerService(stringRedisTemplate);

        service.trigger("cid-1234");

        verify(stringRedisTemplate).convertAndSend("crawl:trigger", "cid-1234");
    }

    @Test
    void trigger_acceptsZeroSubscribersAsPublishCommandAccepted() {
        var service = new CrawlTriggerService(stringRedisTemplate);
        when(stringRedisTemplate.convertAndSend("crawl:trigger", "cid-0000")).thenReturn(0L);

        service.trigger("cid-0000");

        verify(stringRedisTemplate).convertAndSend("crawl:trigger", "cid-0000");
    }
}
