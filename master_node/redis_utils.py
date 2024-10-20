from fastapi import HTTPException
import logging
import pickle
import redis

from settings import REDIS_HOST
##  Redis connection


redis_client = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=False)


def cache_to_redis(key, value):
    redis_client.set(key,  pickle.dumps(value))
    message = f"Saved {key} data to Redis cache..."
    logging.info(message)
    
def get_from_redis(key):
    value = redis_client.get(key)
    if value:
        return pickle.loads(value)
    raise HTTPException(status_code=500, detail="Failed to fetch data from Redis cache.")  # Raise the HTTPException when value is not found
    
    