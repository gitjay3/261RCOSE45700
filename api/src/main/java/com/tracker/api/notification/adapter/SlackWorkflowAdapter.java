package com.tracker.api.notification.adapter;

import com.tracker.api.domain.Detection;
import com.tracker.api.notification.domain.NotificationChannelType;
import com.tracker.api.notification.service.NotificationTemplateRenderer;
import com.tracker.api.notification.service.WebhookUrlGuard;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.util.Map;

@Component
public class SlackWorkflowAdapter extends AbstractWebhookAdapter {

    public SlackWorkflowAdapter(
            RestClient.Builder builder, NotificationTemplateRenderer renderer, WebhookUrlGuard webhookUrlGuard) {
        super(builder, renderer, webhookUrlGuard);
    }

    @Override
    public NotificationChannelType type() {
        return NotificationChannelType.SLACK_WORKFLOW;
    }

    @Override
    protected Map<String, Object> payload(Detection detection, String text) {
        return Map.of(
                "text", text,
                "detection_id", detection.getId(),
                "site_name", detection.getPost().getSource().getSiteName(),
                "type", detection.getType(),
                "tier", detection.getTier(),
                "confidence", String.format("%.2f", detection.getConfidence())
        );
    }
}
