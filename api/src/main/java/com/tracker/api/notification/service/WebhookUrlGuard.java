package com.tracker.api.notification.service;

import com.tracker.api.exception.UnsafeWebhookUrlException;
import org.springframework.stereotype.Component;

import java.net.InetAddress;
import java.net.URI;
import java.net.URISyntaxException;
import java.net.UnknownHostException;
import java.util.Set;

/**
 * 웹훅 URL의 SSRF 위험을 차단하는 가드. detection/src/agents/link_fetch_guard.py와 동일한 위협모델
 * (사설/loopback/link-local/메타데이터/CGNAT 차단, DNS 해석 후 검증)을 Java 쪽에도 적용한다.
 *
 * 채널 등록 시점(NotificationChannelService)과 실제 전송 직전(AbstractWebhookAdapter) 양쪽에서
 * 호출해, DNS rebinding(등록 시 통과한 호스트가 전송 시점에 다른 IP로 풀리는 공격)을 완화한다.
 */
@Component
public class WebhookUrlGuard {

    private static final Set<String> ALLOWED_SCHEMES = Set.of("http", "https");

    public void validate(String webhookUrl) {
        URI uri;
        try {
            uri = new URI(webhookUrl);
        } catch (URISyntaxException e) {
            throw new UnsafeWebhookUrlException("올바르지 않은 웹훅 URL입니다: " + webhookUrl);
        }

        String scheme = uri.getScheme() == null ? "" : uri.getScheme().toLowerCase();
        if (!ALLOWED_SCHEMES.contains(scheme)) {
            throw new UnsafeWebhookUrlException("허용되지 않은 스킴입니다: " + scheme);
        }

        String host = uri.getHost();
        if (host == null || host.isBlank()) {
            throw new UnsafeWebhookUrlException("웹훅 URL에 호스트가 없습니다: " + webhookUrl);
        }

        InetAddress[] resolved;
        try {
            resolved = InetAddress.getAllByName(host);
        } catch (UnknownHostException e) {
            throw new UnsafeWebhookUrlException("웹훅 호스트를 해석할 수 없습니다: " + host);
        }
        if (resolved.length == 0) {
            throw new UnsafeWebhookUrlException("웹훅 호스트를 해석할 수 없습니다: " + host);
        }

        for (InetAddress address : resolved) {
            if (isBlockedAddress(address)) {
                throw new UnsafeWebhookUrlException(
                        "웹훅 호스트가 내부/사설 네트워크로 해석됩니다: " + host + " -> " + address.getHostAddress());
            }
        }
    }

    private boolean isBlockedAddress(InetAddress address) {
        if (address.isLoopbackAddress()
                || address.isLinkLocalAddress()       // 169.254.0.0/16 — AWS 메타데이터 169.254.169.254 포함
                || address.isSiteLocalAddress()        // 10/8, 172.16/12, 192.168/16
                || address.isMulticastAddress()
                || address.isAnyLocalAddress()) {
            return true;
        }
        byte[] bytes = address.getAddress();
        // CGNAT 100.64.0.0/10 (RFC 6598) — Java InetAddress에 전용 판정 메서드가 없어 수동 체크.
        if (bytes.length == 4 && (bytes[0] & 0xFF) == 100 && (bytes[1] & 0xFF) >= 64 && (bytes[1] & 0xFF) <= 127) {
            return true;
        }
        // IPv6 Unique Local Address fc00::/7 — 사설 IPv6.
        if (bytes.length == 16 && (bytes[0] & 0xFE) == 0xFC) {
            return true;
        }
        return false;
    }
}
