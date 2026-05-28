package com.tracker.api.repository;

import com.tracker.api.domain.ActivityLog;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;

public interface ActivityLogRepository extends JpaRepository<ActivityLog, Long> {
    List<ActivityLog> findTop20ByOrderByOccurredAtDesc();
}
