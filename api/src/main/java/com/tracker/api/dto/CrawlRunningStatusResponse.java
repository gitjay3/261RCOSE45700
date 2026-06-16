package com.tracker.api.dto;

public record CrawlRunningStatusResponse(
        boolean running,
        // "manual" | "schedule" | null(트리거 종류를 알 수 없는 레거시 값)
        String trigger
) {}
