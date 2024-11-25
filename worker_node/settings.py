import os

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
KAFKA_SERVER = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092').split(',')
WORKER_ID=os.getenv('WORKER_ID')
