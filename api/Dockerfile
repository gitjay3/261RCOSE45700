# syntax=docker/dockerfile:1.7
# API — Spring Boot 3.5 / Java 21 (Temurin)
# Story 5.2: BuildKit multi-stage with registry cache mode=max.

# ---------- builder ----------
FROM eclipse-temurin:21-jdk-noble AS builder

WORKDIR /workspace

# Copy gradle wrapper + build descriptors first for cache reuse.
COPY api/gradlew api/gradlew.bat api/settings.gradle api/build.gradle ./
COPY api/gradle ./gradle

RUN chmod +x ./gradlew && ./gradlew --no-daemon --version

# Copy sources and build the boot jar (skip tests — CI ran them already).
COPY api/src ./src
RUN ./gradlew bootJar --no-daemon -x test

# ---------- runtime ----------
FROM eclipse-temurin:21-jre-noble AS runtime

ENV JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=75"

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl tini \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --create-home --uid 1001 appuser

WORKDIR /app

COPY --from=builder /workspace/build/libs/*.jar /app/app.jar

# /run/secrets/<name> → upper-case env var; AC #12 (secrets mount, no direct env injection).
COPY infra/docker-secret-shim.sh /usr/local/bin/secret-shim
RUN chmod +x /usr/local/bin/secret-shim

USER appuser
EXPOSE 8080

# Spring Boot Actuator readiness probe — DataSource 포함, DB DOWN 시 503 반환.
# (default /actuator/health는 ping만 집계해 DB 단절도 UP으로 보고하는 footgun.)
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -fsS http://localhost:8080/actuator/health/readiness || exit 1

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/secret-shim"]
CMD ["java", "-jar", "/app/app.jar"]
