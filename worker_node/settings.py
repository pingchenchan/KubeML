import os

REDIS_HOSTS = os.getenv('REDIS_HOSTS', 'localhost').split(',')
KAFKA_SERVER = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092').split(',')
WORKER_ID=os.getenv('WORKER_ID')
