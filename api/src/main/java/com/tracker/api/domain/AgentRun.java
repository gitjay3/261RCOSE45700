package com.tracker.api.domain;

import com.fasterxml.jackson.databind.JsonNode;
import jakarta.persistence.*;
import lombok.Getter;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;
import java.math.BigDecimal;
import java.time.Instant;

@Entity
@Table(name = "agent_runs")
@Getter
public class AgentRun {

    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "detection_id")
    private Long detectionId;

    @Column(name = "post_id", nullable = false)
    private Long postId;

    @Column(nullable = false, length = 20)
    private String stage;

    @Column(length = 50)
    private String model;

    @Column(name = "input_tokens", nullable = false)
    private int inputTokens;

    @Column(name = "output_tokens", nullable = false)
    private int outputTokens;

    @Column(name = "cost_usd", nullable = false, precision = 10, scale = 6)
    private BigDecimal costUsd;

    @Column(name = "latency_ms")
    private Integer latencyMs;

    // JSONB 컬럼 — Hibernate 6 built-in JSON 지원: PostgreSQL JSONB, H2 VARCHAR 모두 호환
    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "output")
    private JsonNode output;

    @Column(name = "correlation_id", length = 100)
    private String correlationId;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;
}
