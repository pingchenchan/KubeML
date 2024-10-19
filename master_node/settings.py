import os


CASSANDRA_HOSTS = os.getenv('CASSANDRA_HOST', 'localhost').split(',')
CASSANDRA_KEYSPACE = 'my_dataset_keyspace'
KAFKA_SERVER = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')# **Initialize Kafka Producer and Consumer (Non-blocking)**
CHUNK_SIZE = 4 * 1024 * 1024