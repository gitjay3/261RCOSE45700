package com.tracker.api.controller;

import com.tracker.api.dto.ActivityLogEntry;
import com.tracker.api.dto.ActivityLogRequest;
import com.tracker.api.service.ActivityLogService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.List;

@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
@Tag(name = "Activity", description = "사용자 활동 로그")
public class ActivityController {

    private final ActivityLogService activityLogService;

    @GetMapping("/activity")
    @Operation(summary = "최근 활동 조회", description = "최근 20건의 활동 로그를 최신순으로 반환.")
    public ResponseEntity<List<ActivityLogEntry>> getActivity() {
        return ResponseEntity.ok(activityLogService.getRecent());
    }

    @PostMapping("/activity")
    @Operation(summary = "활동 기록", description = "클라이언트 측 이벤트(크롤링 완료 등)를 기록.")
    public ResponseEntity<Void> logActivity(@Valid @RequestBody ActivityLogRequest request) {
        activityLogService.log(request.eventType(), request.message());
        return ResponseEntity.noContent().build();
    }
}
