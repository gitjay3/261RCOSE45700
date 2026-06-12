package com.tracker.api.repository;

import com.tracker.api.domain.AgentRun;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;

public interface AgentRunRepository extends JpaRepository<AgentRun, Long> {
    List<AgentRun> findByDetectionIdOrderByCreatedAtAsc(Long detectionId);
}
