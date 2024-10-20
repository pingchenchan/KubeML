import logging
import pickle
import redis
import os
from settings import REDIS_HOST
##  Redis connection
redis_client = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=False)

def cache_to_redis(key, value):
    redis_client.set(key,  pickle.dumps(value))
    message = f"Saved {key} data to Redis cache..."
    logging.info(message )
    
def get_from_redis(key):
    value = redis_client.get(key)
    if value:
        message = f"Success get {key} data to Redis cache..."
        logging.info(message )
        return pickle.loads(value)
    return None
    