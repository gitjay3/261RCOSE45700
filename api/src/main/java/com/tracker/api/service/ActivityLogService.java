package com.tracker.api.service;

import com.tracker.api.domain.ActivityLog;
import com.tracker.api.dto.ActivityLogEntry;
import com.tracker.api.repository.ActivityLogRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import java.util.List;

@Service
@RequiredArgsConstructor
public class ActivityLogService {

    private final ActivityLogRepository repository;

    public void log(String eventType, String message) {
        repository.save(new ActivityLog(eventType, message));
    }

    public List<ActivityLogEntry> getRecent() {
        return repository.findTop20ByOrderByOccurredAtDesc()
                .stream()
                .map(a -> new ActivityLogEntry(a.getId(), a.getEventType(), a.getMessage(), a.getOccurredAt()))
                .toList();
    }
}
