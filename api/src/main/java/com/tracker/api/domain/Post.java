package com.tracker.api.domain;

import jakarta.persistence.*;
import lombok.Getter;
import java.time.Instant;

@Entity
@Table(name = "posts")
@Getter
public class Post {

    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "source_id", nullable = false)
    private Source source;

    @Column(name = "post_id_at_source", length = 200)
    private String postIdAtSource;

    private String title;

    @Column(columnDefinition = "TEXT")
    private String body;

    private String author;

    @Column(name = "post_url", nullable = true, length = 1000)
    private String postUrl;

    @Column(length = 10)
    private String language;

    @Column(name = "crawled_at", nullable = false)
    private Instant crawledAt;
}
