package com.tracker.api.dto;

import com.fasterxml.jackson.databind.JsonNode;
import com.tracker.api.domain.AgentRun;
import java.math.BigDecimal;

public record AgentRunResponse(
        Long id,
        String stage,
        String model,
        int inputTokens,
        int outputTokens,
        BigDecimal costUsd,
        Integer latencyMs,
        JsonNode output
) {
    public static AgentRunResponse from(AgentRun r) {
        return new AgentRunResponse(
                r.getId(), r.getStage(), r.getModel(),
                r.getInputTokens(), r.getOutputTokens(),
                r.getCostUsd(), r.getLatencyMs(), r.getOutput()
        );
    }
}
