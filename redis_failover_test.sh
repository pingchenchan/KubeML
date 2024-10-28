#!/bin/bash


WAIT_TIME=10

log() {
    echo "$(date +'%Y-%m-%d %H:%M:%S') - $1"
}

check_redis_health() {
    local node=$1
    log "Checking health of $node..."
    docker exec $node redis-cli ping | grep PONG > /dev/null

    if [ $? -eq 0 ]; then
        log "$node is healthy."
        return 0
    else
        log "$node is NOT healthy."
        return 1
    fi
}

simulate_failure() {
    local node=$1
    log "Stopping $node..."
    docker stop $node
    sleep $WAIT_TIME

    log "Checking if $node is down..."
    docker ps | grep $node > /dev/null

    if [ $? -eq 0 ]; then
        log "Test failed. $node is still running."
    else
        log "$node stopped successfully."
    fi
}

restore_node() {
    local node=$1
    log "Starting $node..."
    docker start $node
    sleep $WAIT_TIME

    check_redis_health $node

    if [ $? -eq 0 ]; then
        log "$node restored successfully."
    else
        log "Failed to restore $node."
    fi
}


log "Starting Redis failover test..."
simulate_failure "redis-node1"
restore_node "redis-node1"
log "Redis failover test completed."
