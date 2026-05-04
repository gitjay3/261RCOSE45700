variable "name_prefix" {
  description = "Secret name prefix (e.g., tracker/dev)."
  type        = string
}

variable "recovery_window_in_days" {
  description = "삭제 시 복구 가능 기간 (dev=7 권장). 0은 즉시 영구삭제."
  type        = number
  default     = 7
}

variable "tags" {
  description = "Common tags."
  type        = map(string)
  default     = {}
}
