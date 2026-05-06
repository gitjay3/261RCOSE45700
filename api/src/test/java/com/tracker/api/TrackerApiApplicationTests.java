package com.tracker.api;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;

@SpringBootTest
@ActiveProfiles("test")
class TrackerApiApplicationTests {

	@MockitoBean
	StringRedisTemplate stringRedisTemplate;

	@Test
	void contextLoads() {
	}

}
