#!/bin/bash


REDIS_NODES=("redis-node6" "redis-node5" "redis-node4" "redis-node3" "redis-node2" "redis-node1")
FAIL_EXPECTED_NODE="redis-node3"  


MASTER_URL="http://localhost:5000"
WORKER_URL="http://localhost:8000"


RED='\e[31m'
GREEN='\e[32m'
RESET='\e[0m'  

log() {
    echo -e "$(date +'%Y-%m-%d %H:%M:%S') - $1"
}

log_success() {
    echo -e "${GREEN}$(date +'%Y-%m-%d %H:%M:%S') - $1${RESET}"
}

log_error() {
    echo -e "${RED}$(date +'%Y-%m-%d %H:%M:%S') - $1${RESET}"
}


check_cluster_health() {
    log "Checking Redis Cluster health..."
    STATE=$(docker exec redis-node1 redis-cli -c CLUSTER INFO | grep "cluster_state" | awk -F':' '{print $2}' | tr -d '[:space:]')

    if [ "$STATE" == "ok" ]; then
        log_success "Redis Cluster is healthy."
        return 0  
    elif [ "$CURRENT_NODE" == "$FAIL_EXPECTED_NODE" ]; then
        log_success "Redis Cluster is expected to be in FAIL state after shutting down ${CURRENT_NODE}."
        return 1  
    else
        log_error "Redis Cluster is in FAIL state unexpectedly. Stopping tests."
        return 2  
    fi
}


write_to_redis() {
    local key=$1
    local value=$2
    log "Writing to Redis: ${key} -> ${value}"

    RESPONSE=$(curl -s -X POST "${MASTER_URL}/cache_to_redis/${key}" \
               -H "Content-Type: application/json" \
               -d "{\"value\": \"${value}\"}")

    if echo "$RESPONSE" | grep -q '"status":"Data cached successfully"'; then
        log_success "Successfully cached ${key} -> ${value} to Redis."
    else
        log_error "Failed to cache ${key} -> ${value}. Response: $RESPONSE"
    fi
}


read_from_redis() {
    local key=$1
    log "Reading from Redis: ${key}..."

    RESPONSE=$(curl -s -X GET "${WORKER_URL}/get_from_redis/${key}")

    VALUE=$(echo "$RESPONSE" | grep -o '"value":"[^"]*"' | awk -F':' '{print $2}' | tr -d '"')

    if [ -n "$VALUE" ]; then
        log_success "Data retrieved successfully: ${key} -> ${VALUE}"
    else
        log_error "Failed to retrieve data for ${key}. Response: $RESPONSE"
    fi
}


shutdown_and_test() {
    for node in "${REDIS_NODES[@]}"; do
        CURRENT_NODE="$node"

        check_cluster_health
        HEALTH_STATUS=$?

        if [ $HEALTH_STATUS -eq 2 ]; then
            log_error "Unexpected FAIL state. Skipping further tests."
            break 
        elif [ $HEALTH_STATUS -eq 1 ]; then
            log_success "Expected FAIL state reached. Skipping further tests."
            break  
        fi

 
        local key="test_key_${node}"
        local value="Test value from ${node}"

        write_to_redis "$key" "$value"
        read_from_redis "$key"

        log "Shutting down ${node}..."
        docker stop "$node" || log_error "Failed to stop ${node}"
        sleep 20  
    done
}


restart_redis_nodes() {
    for node in "${REDIS_NODES[@]}"; do
        log "Restarting ${node}..."
        docker start "$node"
        sleep 5  
    done
}


log "Starting Redis shutdown test..."
shutdown_and_test
log_success "All Redis nodes have been shut down sequentially and tested."

log "Restarting all Redis nodes..."
restart_redis_nodes
log_success "All Redis nodes have been restarted successfully."

log_success "Redis shutdown and recovery test completed."
