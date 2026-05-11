package com.tracker.api.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.tracker.api.dto.StatsResponse;
import com.tracker.api.exception.InvalidFilterParamException;
import com.tracker.api.repository.StatsRepository;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.IntStream;

@Slf4j
@Service
public class StatsService {

    private final StatsRepository statsRepository;
    private final ObjectMapper objectMapper;
    private final StringRedisTemplate cacheRedisTemplate;

    public StatsService(StatsRepository statsRepository,
                        ObjectMapper objectMapper,
                        @Qualifier("cacheRedisTemplate") StringRedisTemplate cacheRedisTemplate) {
        this.statsRepository = statsRepository;
        this.objectMapper = objectMapper;
        this.cacheRedisTemplate = cacheRedisTemplate;
    }

    @Transactional(readOnly = true)
    public StatsResponse getStats(String period) {
        String normalizedPeriod = normalizePeriod(period);
        String cacheKey = buildCacheKey(normalizedPeriod);

        try {
            String cached = cacheRedisTemplate.opsForValue().get(cacheKey);
            if (cached != null) {
                return objectMapper.readValue(cached, StatsResponse.class);
            }
        } catch (Exception e) {
            log.warn("Redis cache read failed for key '{}': {}", cacheKey, e.getMessage());
        }

        StatsResponse response = buildStats(normalizedPeriod, LocalDate.now(ZoneOffset.UTC));

        try {
            String json = objectMapper.writeValueAsString(response);
            cacheRedisTemplate.opsForValue().set(cacheKey, json, Duration.ofSeconds(60));
        } catch (Exception e) {
            log.warn("Redis cache write failed for key '{}': {}", cacheKey, e.getMessage());
        }

        return response;
    }

    StatsResponse buildStats(String period, LocalDate today) {
        long todayCount = statsRepository.countToday(today);
        long yesterdayCount = statsRepository.countYesterday(today);
        long delta = todayCount - yesterdayCount;

        var typeDistribution = statsRepository.findTypeDistributionRaw().stream()
                .filter(row -> row[0] != null)
                .map(row -> new StatsResponse.TypeDistributionItem((String) row[0], ((Number) row[1]).longValue()))
                .toList();

        var siteDistribution = statsRepository.findSiteDistributionRaw().stream()
                .filter(row -> row[0] != null)
                .map(row -> new StatsResponse.SiteDistributionItem((String) row[0], ((Number) row[1]).longValue()))
                .toList();

        var langDistribution = statsRepository.findLangDistributionRaw().stream()
                .filter(row -> row[0] != null)
                .map(row -> new StatsResponse.LangDistributionItem((String) row[0], ((Number) row[1]).longValue()))
                .toList();

        List<StatsResponse.TrendItem> trend = buildTrend(period, today);

        return new StatsResponse(todayCount, delta, typeDistribution, siteDistribution, langDistribution, trend);
    }

    private List<StatsResponse.TrendItem> buildTrend(String period, LocalDate today) {
        if ("weekly".equals(period)) {
            LocalDate fromDate = today.minusDays(6);
            Instant from = fromDate.atStartOfDay().toInstant(ZoneOffset.UTC);
            Instant to = today.plusDays(1).atStartOfDay().toInstant(ZoneOffset.UTC);
            return toTrendItems(statsRepository.findTrendRaw(from, to), fromDate, 7);
        } else if ("monthly".equals(period)) {
            LocalDate fromDate = today.minusDays(29);
            Instant from = fromDate.atStartOfDay().toInstant(ZoneOffset.UTC);
            Instant to = today.plusDays(1).atStartOfDay().toInstant(ZoneOffset.UTC);
            return toTrendItems(statsRepository.findTrendRaw(from, to), fromDate, 30);
        }
        return List.of();
    }

    private List<StatsResponse.TrendItem> toTrendItems(List<Object[]> rows, LocalDate fromDate, int days) {
        Map<String, Long> countsByDate = new HashMap<>();
        for (Object[] row : rows) {
            if (row[0] != null) {
                countsByDate.put(row[0].toString(), ((Number) row[1]).longValue());
            }
        }

        return IntStream.range(0, days)
                .mapToObj(offset -> {
                    String date = fromDate.plusDays(offset).toString();
                    return new StatsResponse.TrendItem(date, countsByDate.getOrDefault(date, 0L));
                })
                .toList();
    }

    private String buildCacheKey(String period) {
        if (period != null) {
            return "cache:detections:stats:" + period;
        }
        return "cache:detections:stats";
    }

    private String normalizePeriod(String period) {
        if (period == null || period.isBlank()) {
            return null;
        }

        String normalized = period.trim();
        if ("weekly".equals(normalized) || "monthly".equals(normalized)) {
            return normalized;
        }

        throw new InvalidFilterParamException("period는 weekly 또는 monthly만 허용됩니다.");
    }
}
