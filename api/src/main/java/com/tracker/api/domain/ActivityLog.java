package com.tracker.api.domain;

import jakarta.persistence.*;
import lombok.Getter;
import java.time.Instant;

@Entity
@Table(name = "activity_log")
@Getter
public class ActivityLog {

    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "event_type", nullable = false, length = 50)
    private String eventType;

    @Column(nullable = false, columnDefinition = "TEXT")
    private String message;

    @Column(name = "occurred_at", nullable = false)
    private Instant occurredAt;

    protected ActivityLog() {}

    public ActivityLog(String eventType, String message) {
        this.eventType = eventType;
        this.message = message;
        this.occurredAt = Instant.now();
    }
}
