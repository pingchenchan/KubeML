#!/bin/bash

# 設定 API 端點
MASTER_URL="http://localhost:5000"
WORKER1_URL="http://localhost:8000"
WORKER2_URL="http://localhost:9001"

# 測試用的 key 和 value
TEST_KEY="test_key"
TEST_VALUE="Hello, Redis!"

# 顏色設置
RED='\e[31m'
GREEN='\e[32m'
YELLOW='\e[33m'
RESET='\e[0m'  # 重置顏色

log() {
    echo -e "$(date +'%Y-%m-%d %H:%M:%S') - $1"
}

log_success() {
    echo -e "${GREEN}$(date +'%Y-%m-%d %H:%M:%S') - $1${RESET}"
}

log_error() {
    echo -e "${RED}$(date +'%Y-%m-%d %H:%M:%S') - $1${RESET}"
}

# 在 Master Node 上寫入資料
write_to_redis() {
    log "Writing to Redis on Master Node..."
    curl -X POST "${MASTER_URL}/cache_to_redis/${TEST_KEY}" \
         -H "Content-Type: application/json" \
         -d "{\"value\": \"${TEST_VALUE}\"}"
    
    if [ $? -eq 0 ]; then
        log_success "Successfully cached data to Redis on Master Node."
    else
        log_error "Failed to cache data to Redis on Master Node."
        exit 1
    fi
}

# 在 Worker Node 上讀取資料並解析 JSON
read_from_redis() {
    local worker_url=$1
    local worker_name=$2

    log "Reading from Redis on ${worker_name}..."
    RESPONSE=$(curl -s -X GET "${worker_url}/get_from_redis/${TEST_KEY}")

    # 使用 grep 和 awk 解析 JSON 響應中的 value
    VALUE=$(echo "$RESPONSE" | grep -o '"value":"[^"]*"' | awk -F':' '{print $2}' | tr -d '"')

    if [ "$VALUE" == "$TEST_VALUE" ]; then
        log_success "Data retrieved successfully from ${worker_name} and matches: $VALUE"
    else
        log_error "Data mismatch on ${worker_name}! Expected: $TEST_VALUE, Got: $VALUE"
        exit 1
    fi
}

# 執行測試
log "Starting multi-worker API Test..."
write_to_redis
read_from_redis "${WORKER1_URL}" "worker-node1"
read_from_redis "${WORKER2_URL}" "worker-node2"
log_success "Multi-worker API Test completed successfully."
