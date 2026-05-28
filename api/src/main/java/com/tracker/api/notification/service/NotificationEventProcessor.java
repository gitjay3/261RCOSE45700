package com.tracker.api.notification.service;

import com.tracker.api.domain.Detection;
import com.tracker.api.notification.domain.*;
import com.tracker.api.notification.repository.NotificationDeliveryRepository;
import com.tracker.api.notification.repository.NotificationEventRepository;
import com.tracker.api.notification.repository.NotificationRuleRepository;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

import java.time.Instant;
import java.util.List;

@Service
@RequiredArgsConstructor
@ConditionalOnProperty(name = "tracker.notifications.scheduler.enabled", havingValue = "true", matchIfMissing = true)
public class NotificationEventProcessor {

    private static final Logger log = LoggerFactory.getLogger(NotificationEventProcessor.class);

    private final NotificationEventRepository eventRepository;
    private final NotificationRuleRepository ruleRepository;
    private final NotificationDeliveryRepository deliveryRepository;
    private final NotificationRuleEvaluator ruleEvaluator;
    private final NotificationChannelService channelService;
    private final TransactionTemplate transactionTemplate;

    @Value("${tracker.notifications.batch-size:10}")
    private int batchSize;

    @Value("${tracker.notifications.max-attempts:3}")
    private int maxAttempts;

    @Value("${tracker.notifications.processing-timeout-seconds:120}")
    private int processingTimeoutSeconds;

    @Scheduled(fixedDelayString = "${tracker.notifications.poll-delay-ms:5000}")
    public void processPendingEvents() {
        List<Long> ids = claimPendingEvents();
        for (Long id : ids) {
            try {
                processEvent(id);
            } catch (Exception e) {
                log.warn("notification event 처리 실패: id={}", id, e);
                markFailed(id, e.getMessage());
            }
        }
    }

    private List<Long> claimPendingEvents() {
        return transactionTemplate.execute(status -> {
            List<Long> ids = eventRepository.findPendingIdsForUpdate(
                    batchSize, maxAttempts, processingTimeoutSeconds);
            if (!ids.isEmpty()) {
                eventRepository.markClaimed(ids, NotificationEventStatus.PROCESSING, Instant.now());
            }
            return ids;
        });
    }

    private void processEvent(Long id) {
        NotificationWork work = loadWork(id);
        if (work == null) {
            return;
        }

        List<DeliveryAttempt> attempts = work.rules().stream()
                .map(rule -> new DeliveryAttempt(
                        rule.ruleId(),
                        channelService.adapterFor(rule.type()).send(work.detection(), rule.config())))
                .toList();

        saveResults(id, attempts);
    }

    private NotificationWork loadWork(Long id) {
        return transactionTemplate.execute(status -> {
            NotificationEvent event = eventRepository.findByIdFetched(id)
                    .orElseThrow(() -> new IllegalStateException("notification event 없음: " + id));
            Detection detection = event.getDetection();
            if (detection == null || !detection.isIllegal()) {
                finish(event, NotificationEventStatus.SKIPPED, null);
                return null;
            }

            List<NotificationRule> rules = ruleRepository.findEnabledRules(event.getEventType());
            List<NotificationRule> matchedRules = rules.stream()
                    .filter(rule -> ruleEvaluator.matches(rule, detection))
                    .toList();

            if (matchedRules.isEmpty()) {
                finish(event, NotificationEventStatus.SKIPPED, null);
                return null;
            }

            List<MatchedRule> matched = matchedRules.stream()
                    .map(rule -> new MatchedRule(
                            rule.getId(),
                            rule.getChannel().getType(),
                            channelService.readConfig(rule.getChannel())))
                    .toList();
            return new NotificationWork(detection, matched);
        });
    }

    private void saveResults(Long eventId, List<DeliveryAttempt> attempts) {
        transactionTemplate.executeWithoutResult(status -> {
            NotificationEvent event = eventRepository.findByIdFetched(eventId)
                    .orElseThrow(() -> new IllegalStateException("notification event 없음: " + eventId));
            boolean anySuccess = false;
            String lastError = null;
            for (DeliveryAttempt attempt : attempts) {
                NotificationRule rule = ruleRepository.findById(attempt.ruleId())
                        .orElseThrow(() -> new IllegalStateException("notification rule 없음: " + attempt.ruleId()));
                saveDelivery(event, rule, attempt.result());
                if (attempt.result().success()) {
                    anySuccess = true;
                    rule.getChannel().setLastSuccessAt(Instant.now());
                } else {
                    lastError = attempt.result().errorMessage();
                    rule.getChannel().setLastFailureAt(Instant.now());
                }
            }

            if (anySuccess) {
                finish(event, NotificationEventStatus.COMPLETED, null);
            } else if (event.getAttempts() >= maxAttempts) {
                finish(event, NotificationEventStatus.FAILED, lastError);
            } else {
                event.setStatus(NotificationEventStatus.PENDING);
                event.setLastError(lastError);
            }
        });
    }

    private void markFailed(Long id, String error) {
        transactionTemplate.executeWithoutResult(status -> eventRepository.findById(id).ifPresent(event -> {
            event.setStatus(event.getAttempts() >= maxAttempts
                    ? NotificationEventStatus.FAILED
                    : NotificationEventStatus.PENDING);
            event.setLastError(error);
        }));
    }

    private void saveDelivery(NotificationEvent event, NotificationRule rule, NotificationSendResult result) {
        NotificationDelivery delivery = new NotificationDelivery();
        delivery.setEvent(event);
        delivery.setDetection(event.getDetection());
        delivery.setRule(rule);
        delivery.setChannel(rule.getChannel());
        delivery.setStatus(result.success()
                ? NotificationDeliveryStatus.SUCCESS
                : NotificationDeliveryStatus.FAILED);
        delivery.setResponseCode(result.responseCode());
        delivery.setErrorMessage(result.errorMessage());
        delivery.setAttemptedAt(Instant.now());
        delivery.setSentAt(result.success() ? Instant.now() : null);
        deliveryRepository.save(delivery);
    }

    private void finish(NotificationEvent event, NotificationEventStatus status, String error) {
        event.setStatus(status);
        event.setLastError(error);
        event.setProcessedAt(Instant.now());
    }

    private record NotificationWork(
            Detection detection,
            List<MatchedRule> rules
    ) {
    }

    private record MatchedRule(
            Long ruleId,
            NotificationChannelType type,
            WebhookConfig config
    ) {
    }

    private record DeliveryAttempt(
            Long ruleId,
            NotificationSendResult result
    ) {
    }
}
