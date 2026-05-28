CREATE TABLE activity_log (
    id          BIGSERIAL PRIMARY KEY,
    event_type  VARCHAR(50)  NOT NULL,
    message     TEXT         NOT NULL,
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_activity_log_occurred_at ON activity_log (occurred_at DESC);
