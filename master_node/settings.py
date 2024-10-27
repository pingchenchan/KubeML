import os

REDIS_HOSTS = os.getenv('REDIS_HOSTS', 'localhost').split(',')
CASSANDRA_HOSTS = os.getenv('CASSANDRA_HOST', 'localhost').split(',')
CASSANDRA_KEYSPACE = 'my_dataset_keyspace'
KAFKA_SERVER = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092').split(',')
CASSANDRA_CHUNK_SIZE = 4 * 1024 * 1024
CASSANDRA_MAX_BATCH_SIZE_BYTES = 5 * 1024 * 1024