package com.tracker.api.controller;

import com.tracker.api.dto.DetectionListResponse;
import com.tracker.api.dto.DetectionResponse;
import com.tracker.api.service.DetectionService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.constraints.Min;
import lombok.RequiredArgsConstructor;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;
import java.time.LocalDate;
import java.util.UUID;

@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
@Validated
@Tag(name = "Detections", description = "불법 게시글 탐지 결과 조회")
public class DetectionController {

    private final DetectionService detectionService;

    @GetMapping("/detections")
    @Operation(summary = "탐지 목록 조회", description = "confidence >= 0.70 필터 항상 적용. confidence 내림차순 정렬.")
    public ResponseEntity<DetectionListResponse> getDetections(
            @RequestParam(required = false)
            @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate date,
            @RequestParam(required = false) String site,
            @RequestParam(required = false) String type,
            @RequestParam(required = false) String lang,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) int size,
            HttpServletRequest request) {

        var result = detectionService.getDetections(date, site, type, lang, page, size);

        String correlationId = request.getHeader("X-Correlation-ID");
        if (correlationId == null || correlationId.isBlank()) {
            correlationId = UUID.randomUUID().toString();
        }

        return ResponseEntity.ok()
                .header("X-Correlation-ID", correlationId)
                .body(result);
    }

    @GetMapping("/detections/{id}")
    @Operation(summary = "탐지 상세 조회", description = "지정된 ID의 탐지 결과 상세 정보 반환. 존재하지 않으면 404.")
    public ResponseEntity<DetectionResponse> getDetection(
            @PathVariable Long id,
            HttpServletRequest request) {

        var result = detectionService.getDetectionById(id);

        String correlationId = request.getHeader("X-Correlation-ID");
        if (correlationId == null || correlationId.isBlank()) {
            correlationId = UUID.randomUUID().toString();
        }

        return ResponseEntity.ok()
                .header("X-Correlation-ID", correlationId)
                .body(result);
    }
}
