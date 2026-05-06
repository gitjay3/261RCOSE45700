package com.tracker.api.dto;

public record CrawlTriggerResponse(
        String status,
        int estimatedMinutes
) {}
