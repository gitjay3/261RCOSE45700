package com.tracker.api.dto;

import java.time.Instant;

public record ActivityLogEntry(Long id, String eventType, String message, Instant occurredAt) {}
