from fastapi import HTTPException
import logging
import pickle
from redis import Redis
from redis.cluster import RedisCluster 
from redis.cluster import ClusterNode
from settings import REDIS_HOST

nodes = [ClusterNode('redis-node1', 6379), ClusterNode('redis-node2', 6380), ClusterNode('redis-node3', 6381), ClusterNode('redis-node4', 6382), ClusterNode('redis-node5', 6383), ClusterNode('redis-node6', 6384)]
try:
    redis_client = RedisCluster(
        startup_nodes=nodes,
    )
    logging.info("Successfully connected to Redis Cluster.")
except Exception as e:
    logging.error(f"Cannot connect to Redis Cluster: {e}")
    raise HTTPException(status_code=500, detail="Redis Cluster connection failed.")


def cache_to_redis(key, value):
    redis_client.set(key,  pickle.dumps(value))
    message = f"Saved {key} data to Redis cache..."
    logging.info(message)
    
def get_from_redis(key):
    value = redis_client.get(key)
    if value:
        return pickle.loads(value)
    raise HTTPException(status_code=500, detail="Failed to fetch data from Redis cache.")  # Raise the HTTPException when value is not found
    
    