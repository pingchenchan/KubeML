import base64
import uuid
import numpy as np
import logging
import json
import pickle
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
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

##  Redis connection
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
redis_client = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=False)


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Kafka setup
producer = AIOKafkaProducer(
    bootstrap_servers=KAFKA_SERVER,
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

async def get_consumer():
    consumer = AIOKafkaConsumer(
        'mlp', 'lstm', 'cnn',
        bootstrap_servers=KAFKA_SERVER,
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        group_id="worker-node-group",
        auto_offset_reset='earliest'
    )
    await consumer.start()
    return consumer

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
    

async def send_log_to_kafka(log_message: str):
    """Send logs to the Kafka topic asynchronously."""
    try:
        await producer.send('training-log', log_message)
        logging.info(f'Sent log to Kafka: {log_message}')
    except Exception as e:
        logging.error(f'Failed to send log to Kafka: {e}')
    

# **Train Model Function**
async def train_model(task_type: str, model: Sequential):
    session = get_cassandra_session()
    X_train, y_train =await fetch_mnist_data(session, "train")
    X_test, y_test = await fetch_mnist_data(session, "test")

    if task_type == 'lstm':
        X_train, X_test = X_train.reshape(-1, 28, 28), X_test.reshape(-1, 28, 28)
    elif task_type == 'cnn':
        X_train, X_test = X_train.reshape(-1, 28, 28, 1), X_test.reshape(-1, 28, 28, 1)

    logging.info(f"Training {task_type} model...")
    await send_log_to_kafka(f"Training {task_type} model...")
    model.fit(X_train, y_train, epochs=5, batch_size=128, verbose=1)
    loss, accuracy = model.evaluate(X_test, y_test)
    
    logging.info(f"{task_type} training complete. Accuracy: {accuracy}, Loss: {loss}")
    await send_log_to_kafka(f"{task_type} training complete. Accuracy: {accuracy}, Loss: {loss}")

    # Publish result to Kafka
    result = {"task_type": task_type, "accuracy": accuracy, "loss": loss}
    await producer.send_and_wait('training-results', result)

# **Startup Event to Subscribe Kafka Topics**
@app.on_event("startup")
async def start_kafka_listener():
    consumer = await get_consumer()
    logging.info("Kafka listener started...")
    try:
        async for message in consumer:
            task = message.value
            task_type = task['task_type']
            logging.info(f"Received task: {task_type}")

            if task_type == 'mlp':
                await train_model(task_type, build_mlp_model((28, 28)))
            elif task_type == 'lstm':
                await train_model(task_type, build_lstm_model((28, 28)))
            elif task_type == 'cnn':
                await train_model(task_type, build_cnn_model((28, 28, 1)))

    except Exception as e:
        logging.error(f"Kafka listener error: {e}")
    finally:
        await consumer.stop()
        
# **Fetch MNIST data from Cassandra with logging**
async def fetch_mnist_data(session: Session, dataset_type: str):
    try:
        cache_key = f"mnist_data_{dataset_type}"

        # Check if data is cached in Redis
        cached_data = redis_client.get(cache_key)
        if cached_data:
            message = f"Fetching {dataset_type} data from Redis cache..."
            logging.info(message)
            await send_log_to_kafka(message)
            features, labels = pickle.loads(cached_data)  # Deserialize with pickle
            return np.array(features), np.array(labels)

        message = f"Fetching {dataset_type} data from Cassandra..."
        logging.info(message)
        await send_log_to_kafka(message)
        query = SimpleStatement(
            "SELECT features, label FROM mnist_data WHERE dataset_type = %s ALLOW FILTERING"
        )
        rows = session.execute(query, (dataset_type,))

        features, labels = [], []
        for i, row in enumerate(rows):
            features.append(np.array(row.features, dtype=np.float32).reshape(28, 28))
            labels.append(np.array(row.label, dtype=np.float32))
            if i % 1000 == 0:
                log_message = f"Fetched {dataset_type} row {i} from Cassandra..."
                logging.info(log_message)
                await send_log_to_kafka(log_message)  

        # Serialize data with pickle and store it in Redis
        redis_client.set(cache_key, pickle.dumps((features, labels)), ex=3600)
        message = f"Saved {dataset_type} data to Redis cache..."
        logging.info(message )
        await send_log_to_kafka(message)

        return np.array(features), np.array(labels)

    except Exception as e:
        error_message = f"Failed to fetch MNIST data: {e}"
        logging.error(error_message)
        await send_log_to_kafka(error_message)
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