package com.tracker.api.exception;

public class UnsafeWebhookUrlException extends RuntimeException {
    public UnsafeWebhookUrlException(String message) {
        super(message);
    }
}
