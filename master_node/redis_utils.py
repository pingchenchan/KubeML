from fastapi import HTTPException
import logging
import pickle
from redis.cluster import RedisCluster 
from redis.cluster import ClusterNode
from settings import REDIS_HOSTS

nodes = [
    ClusterNode(host.strip(), 6379 + idx) 
    for idx, host in enumerate(REDIS_HOSTS)
]
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
    
    