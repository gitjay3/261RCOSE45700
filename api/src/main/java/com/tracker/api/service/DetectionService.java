package com.tracker.api.service;

import com.tracker.api.dto.AgentRunResponse;
import com.tracker.api.dto.DetectionListResponse;
import com.tracker.api.dto.DetectionResponse;
import com.tracker.api.exception.DetectionNotFoundException;
import com.tracker.api.exception.InvalidFilterParamException;
import com.tracker.api.repository.AgentRunRepository;
import com.tracker.api.repository.DetectionRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.List;

@Service
@RequiredArgsConstructor
public class DetectionService {

    private static final int MIN_RANGE_DAYS = 1;
    private static final int MAX_RANGE_DAYS = 365;

    private final DetectionRepository detectionRepository;
    private final AgentRunRepository agentRunRepository;

    @Transactional(readOnly = true)
    public DetectionListResponse getDetections(
            LocalDate date, String range, String site, String type, String lang, String tier, int page, int size) {

        Instant fromTime = resolveFromTime(date, range);
        Instant toTime   = date != null ? date.plusDays(1).atStartOfDay(ZoneOffset.UTC).toInstant() : null;

        // 빈 문자열은 null로 변환 (JPQL IS NULL 조건 올바르게 동작)
        String siteParam = StringUtils.hasText(site) ? site : null;
        String typeParam = StringUtils.hasText(type) ? type : null;
        String langParam = StringUtils.hasText(lang) ? lang : null;
        String tierParam = StringUtils.hasText(tier) ? tier : null;

        var pageable = PageRequest.of(
                page,
                size,
                Sort.by(
                        Sort.Order.desc("detectedAt"),
                        Sort.Order.desc("id")));

        Page<com.tracker.api.domain.Detection> resultPage =
                detectionRepository.findFiltered(fromTime, toTime, siteParam, typeParam, langParam, tierParam, pageable);

        var content = resultPage.getContent().stream()
                .map(DetectionResponse::from)
                .toList();

        return new DetectionListResponse(content, page, size, resultPage.getTotalElements());
    }

    private Instant resolveFromTime(LocalDate date, String range) {
        if (date != null) {
            return date.atStartOfDay(ZoneOffset.UTC).toInstant();
        }
        if (!StringUtils.hasText(range)) {
            return null;
        }

        LocalDate today = LocalDate.now(ZoneOffset.UTC);
        int days = parseRangeDays(range);
        return today.minusDays(days - 1L).atStartOfDay(ZoneOffset.UTC).toInstant();
    }

    private int parseRangeDays(String range) {
        String normalized = range.trim().toLowerCase();
        String rawDays = normalized.endsWith("d")
                ? normalized.substring(0, normalized.length() - 1)
                : normalized;

        try {
            int days = Integer.parseInt(rawDays);
            if (days >= MIN_RANGE_DAYS && days <= MAX_RANGE_DAYS) {
                return days;
            }
        } catch (NumberFormatException ignored) {
            // fall through to consistent API error
        }

        throw new InvalidFilterParamException("range는 1d~365d 형식만 허용됩니다.");
    }

    @Transactional(readOnly = true)
    public DetectionResponse getDetectionById(Long id) {
        return detectionRepository.findByIdFetched(id)
                .map(DetectionResponse::from)
                .orElseThrow(() -> new DetectionNotFoundException(id));
    }

    @Transactional(readOnly = true)
    public List<AgentRunResponse> getAgentRuns(Long detectionId) {
        if (!detectionRepository.existsById(detectionId)) {
            throw new DetectionNotFoundException(detectionId);
        }
        return agentRunRepository.findByDetectionIdOrderByCreatedAtAsc(detectionId)
                .stream()
                .map(AgentRunResponse::from)
                .toList();
    }

}
