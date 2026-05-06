package com.tracker.api.exception;

public class DetectionNotFoundException extends RuntimeException {

    public DetectionNotFoundException(Long id) {
        super("탐지 결과를 찾을 수 없습니다: id=" + id);
    }
}
