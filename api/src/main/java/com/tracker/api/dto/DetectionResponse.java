package com.tracker.api.dto;

import com.tracker.api.domain.Detection;

public record DetectionResponse(
        Long id,
        boolean isIllegal,
        String type,
        String tier,
        double confidence,
        String reason,
        String rawText,
        String translatedText,
        String postUrl,
        String siteName,
        String language,
        String detectedAt
) {
    public static DetectionResponse from(Detection d) {
        return new DetectionResponse(
                d.getId(),
                d.isIllegal(),
                d.getType(),
                d.getTier(),
                d.getConfidence(),
                d.getReason(),
                d.getPost().getBody(),
                d.getTranslatedText(),
                d.getPost().getPostUrl(),
                d.getPost().getSource().getSiteName(),
                d.getPost().getLanguage(),
                d.getDetectedAt().toString()
        );
    }
}
