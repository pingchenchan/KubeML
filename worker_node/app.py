import base64
import uuid
import numpy as np
import logging
import json
import pickle
from kafka import KafkaConsumer, KafkaProducer
from fastapi import FastAPI, HTTPException, Depends
from cassandra.cluster import Cluster, Session
from cassandra.query import SimpleStatement
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, Conv2D, MaxPooling2D, Flatten, LSTM
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.utils import to_categorical
from fastapi.middleware.cors import CORSMiddleware
import redis
import os
from models import build_mlp_model, build_lstm_model, build_cnn_model

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# Initialize FastAPI app
app = FastAPI()
CASSANDRA_HOST = os.getenv('CASSANDRA_HOST', 'localhost')
KAFKA_SERVER = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
KEYSPACE = "my_dataset_keyspace"
# Add CORS middleware to allow communication with frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can restrict this to specific origins later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Kafka setup
producer = KafkaProducer(
    bootstrap_servers=KAFKA_SERVER,
    retries=5,
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

consumer = KafkaConsumer(
    'mlp', 'lstm', 'cnn',
    bootstrap_servers=KAFKA_SERVER,
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    group_id="worker-node-group",
    auto_offset_reset='earliest'
)

# **Cassandra Connection**
def get_cassandra_session() -> Session:
    try:
        cluster = Cluster([CASSANDRA_HOST])
        session = cluster.connect()
        session.set_keyspace(KEYSPACE)
        logging.info(f"Connected to Cassandra keyspace: {KEYSPACE}")
        return session
    except Exception as e:
        logging.error(f"Cassandra connection failed: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")
    
##  Redis connection
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
redis_client = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=False)


def send_log_to_kafka(log_message: str):
    """Helper function to send logs to the training-log Kafka topic."""
    if isinstance(log_message, bytes):
        log_message = base64.b64encode(log_message).decode('utf-8')

    try:
        producer.send('training-log', value=log_message)
        logging.info(f'Sent log to Kafka: {log_message}')
    except Exception as e:
        logging.error(f'Failed to send log to Kafka: {e}')
    

# **Train Model Function**
def train_model(task_type: str, model: Sequential):
    session = get_cassandra_session()
    X_train, y_train = fetch_mnist_data(session, "train")
    X_test, y_test = fetch_mnist_data(session, "test")

    if task_type == 'lstm':
        X_train, X_test = X_train.reshape(-1, 28, 28), X_test.reshape(-1, 28, 28)
    elif task_type == 'cnn':
        X_train, X_test = X_train.reshape(-1, 28, 28, 1), X_test.reshape(-1, 28, 28, 1)

    logging.info(f"Training {task_type} model...")
    send_log_to_kafka(f"Training {task_type} model...")
    model.fit(X_train, y_train, epochs=5, batch_size=128, verbose=1)
    loss, accuracy = model.evaluate(X_test, y_test)
    logging.info(f"{task_type} training complete. Accuracy: {accuracy}, Loss: {loss}")
    send_log_to_kafka(f"{task_type} training complete. Accuracy: {accuracy}, Loss: {loss}")

    # Publish result to Kafka
    result = {"task_type": task_type, "accuracy": accuracy, "loss": loss}
    
    producer.send('training-results', result)

# **Startup Event to Subscribe Kafka Topics**
@app.on_event("startup")
async def start_kafka_listener():
    logging.info("Kafka listener started...")
    consumer.subscribe(['mlp', 'lstm', 'cnn'])

    while True:
        messages = consumer.poll(timeout_ms=1000)
        if messages:
            for topic_partition, msgs in messages.items():
                for msg in msgs:
                    task = msg.value
                    task_type = task['task_type']
                    logging.info(f"Received task: {task_type}")

                    if task_type == 'mlp':
                        train_model(task_type, build_mlp_model((28, 28)))
                    elif task_type == 'lstm':
                        train_model(task_type, build_lstm_model((28, 28)))
                    elif task_type == 'cnn':
                        train_model(task_type, build_cnn_model((28, 28, 1)))
# **Fetch MNIST data from Cassandra with logging**
def fetch_mnist_data(session: Session, dataset_type: str):
    try:
        cache_key = f"mnist_data_{dataset_type}"

        # Check if data is cached in Redis
        cached_data = redis_client.get(cache_key)
        if cached_data:
            message = f"Fetching {dataset_type} data from Redis cache..."
            logging.info(message)
            send_log_to_kafka(message)
            features, labels = pickle.loads(cached_data)  # Deserialize with pickle
            return np.array(features), np.array(labels)

        message = f"Fetching {dataset_type} data from Cassandra..."
        logging.info(message)
        send_log_to_kafka(message)
        query = SimpleStatement(
            "SELECT features, label FROM mnist_data WHERE dataset_type = %s ALLOW FILTERING"
        )
        rows = session.execute(query, (dataset_type,))

        features, labels = [], []
        for i, row in enumerate(rows):
            features.append(np.array(row.features, dtype=np.float32).reshape(28, 28))
            labels.append(np.array(row.label, dtype=np.float32))
            if i % 1000 == 0:
                log_message = f"Fetched {dataset_type} row {i} / {len(rows)}"
                logging.info(log_message)
                send_log_to_kafka(log_message)  

        # Serialize data with pickle and store it in Redis
        redis_client.set(cache_key, pickle.dumps((features, labels)), ex=3600)
        message = f"Saved {dataset_type} data to Redis cache..."
        logging.info(message )
        send_log_to_kafka(message)

        return np.array(features), np.array(labels)

    except Exception as e:
        error_message = f"Failed to fetch MNIST data: {e}"
        logging.error(error_message)
        send_log_to_kafka(error_message)
        raise HTTPException(status_code=500, detail="Failed to fetch MNIST data")


# **Health Check Endpoint**
@app.get("/health")
async def health_check():
    try:
        session = get_cassandra_session()
        session.execute("SELECT now() FROM system.local")
        redis_client.ping()  # Check Redis connection
        return {"status": "Service running", "db_status": "Cassandra and Redis connected"}
    except Exception as e:
        return {"status": "Service running", "db_status": f"Error: {e}"}