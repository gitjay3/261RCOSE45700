package com.tracker.api.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record ActivityLogRequest(
        @NotBlank @Size(max = 50) String eventType,
        @NotBlank String message
) {}
