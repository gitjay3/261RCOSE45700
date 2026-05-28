package com.tracker.api.controller;

import com.tracker.api.dto.CrawlTriggerResponse;
import com.tracker.api.service.CrawlTriggerService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import java.util.UUID;

@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
@Tag(name = "Crawl", description = "수동 크롤링 트리거")
public class CrawlController {

    private final CrawlTriggerService crawlTriggerService;

    @PostMapping("/crawl/trigger")
    @Operation(summary = "수동 크롤링 트리거", description = "Redis crawl:trigger 채널에 PUBLISH. 완료까지 약 3분 소요.")
    public ResponseEntity<CrawlTriggerResponse> trigger(HttpServletRequest request) {

        String raw = request.getHeader("X-Correlation-ID");
        String correlationId = (raw != null && !raw.isBlank()) ? raw : UUID.randomUUID().toString();

        crawlTriggerService.trigger(correlationId);

        return ResponseEntity.accepted()
                .header("X-Correlation-ID", correlationId)
                .body(new CrawlTriggerResponse("triggered", 3));
    }
}
