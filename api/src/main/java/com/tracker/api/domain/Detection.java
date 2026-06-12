package com.tracker.api.domain;

import jakarta.persistence.*;
import lombok.Getter;
import java.time.Instant;

@Entity
@Table(name = "detections")
@Getter
public class Detection {

    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "post_id", nullable = false)
    private Post post;

    // 필드명 'illegal' + @Column(name="is_illegal") → Lombok이 isIllegal() getter 생성
    @Column(name = "is_illegal", nullable = false)
    private boolean illegal;

    @Column(length = 50)
    private String type;

    @Column(nullable = false, length = 2)
    private String tier;

    @Column(nullable = false)
    private double confidence;

    @Column(columnDefinition = "TEXT")
    private String reason;

    @Column(name = "translated_text", columnDefinition = "TEXT")
    private String translatedText;

    // V11 마이그레이션으로 TEXT 전환됨 (Bedrock ARN > 100자)
    @Column(name = "model_version", nullable = false, columnDefinition = "text")
    private String modelVersion;

    @Column(name = "detected_at", nullable = false)
    private Instant detectedAt;
}
