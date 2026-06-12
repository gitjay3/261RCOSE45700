package com.tracker.api.exception;

public class CrawlTriggerUnavailableException extends RuntimeException {

    public CrawlTriggerUnavailableException(String jobId) {
        super("Crawler trigger listener unavailable for job: " + jobId);
    }
}
