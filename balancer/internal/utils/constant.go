package utils

const X_PROCESS_TIME = "X-Process-Time"
const X_INSTANCE_ID = "X-Instance-Id"
const X_PROCESS_PID = "X-Process-PID"
const X_PARENT_PROCESS_PID = "X-Parent-Process-PID"
const X_REQUEST_ID = "X-Request-Id"
const PROCESS_TIME_HEADER_NAME = "X-Balancer-Process-Time"


var RATE_LIMIT_HEADERS []string = []string{"X-Ratelimit-Limit", "X-Ratelimit-Remaining", "X-Ratelimit-Reset","Retry-After"}