import os
import uuid
import numpy as np
import logging
import json
from kafka import KafkaConsumer, KafkaProducer, TopicPartition
from fastapi import FastAPI, HTTPException, Depends
from cassandra.cluster import Cluster, Session
from cassandra.query import SimpleStatement
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, Conv2D, MaxPooling2D, Flatten, LSTM
from tensorflow.keras.utils import to_categorical
from tensorflow.keras.optimizers import Adam

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# Initialize FastAPI app
app = FastAPI()
CASSANDRA_HOST = os.getenv('CASSANDRA_HOST', 'localhost')
KEYSPACE = "my_dataset_keyspace"

# Kafka configuration
KAFKA_SERVER = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
consumer = KafkaConsumer(
    bootstrap_servers=KAFKA_SERVER,
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    auto_offset_reset='earliest',  # Ensure all messages are processed
    group_id="worker-node-group"  # Ensure multiple workers handle different tasks efficiently
)
producer = KafkaProducer(
    bootstrap_servers=KAFKA_SERVER,
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# **Dependency Injection: Connect to Cassandra**
def get_cassandra_session() -> Session:
    try:
        logging.info("Connecting to Cassandra...")
        cluster = Cluster([CASSANDRA_HOST])
        session = cluster.connect()
        session.set_keyspace(KEYSPACE)
        logging.info("Connected to Cassandra and switched to keyspace: %s", KEYSPACE)
        return session
    except Exception as e:
        logging.error(f"Failed to connect to Cassandra: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")

# **Fetch MNIST data from Cassandra with logging**
def fetch_mnist_data(session: Session, dataset_type: str):
    try:
        logging.info("Fetching %s data from Cassandra...", dataset_type)
        query = SimpleStatement(
            "SELECT features, label FROM mnist_data WHERE dataset_type = %s ALLOW FILTERING"
        )
        rows = session.execute(query, (dataset_type,))

        features, labels = [], []
        for i, row in enumerate(rows):
            features.append(np.array(row.features, dtype=np.float32).reshape(28, 28))
            labels.append(np.array(row.label, dtype=np.float32))
            if i % 1000 == 0:
                logging.info(f"Fetched {i} rows so far...")

        logging.info("Completed fetching %s data. Total rows: %d", dataset_type, len(features))
        return np.array(features), np.array(labels)
    except Exception as e:
        logging.error(f"Failed to fetch MNIST data: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch MNIST data")


@app.get("/test-consumer")
async def test_consumer():
    messages = []
    for message in consumer:
        messages.append(message.value)
        if len(messages) >= 1:
            break
    return {"received_messages": messages}


# **Kafka Task Listener: Consume messages and train models**
@app.on_event("startup")
def start_kafka_listener():
    consumer.subscribe(['mlp', 'lstm', 'cnn'])

    logging.info("Kafka listener started and waiting for messages...")
    for message in consumer:
        task = message.value
        task_type = task['task_type']
        logging.info(f"Received task: {task_type}")

        # Perform appropriate training based on task type
        if task_type == 'mlp':
            train_model(task_type, build_mlp_model((28, 28)))
        elif task_type == 'lstm':
            train_model(task_type, build_lstm_model((28, 28)))
        elif task_type == 'cnn':
            train_model(task_type, build_cnn_model((28, 28, 1)))

# **Model Training Logic with Kafka Result Publishing**
def train_model(task_type, model):
    try:
        session = get_cassandra_session()
        X_train, y_train = fetch_mnist_data(session, "train")
        X_test, y_test = fetch_mnist_data(session, "test")

        # Reshape data based on model type
        if task_type == 'lstm':
            X_train, X_test = X_train.reshape(-1, 28, 28), X_test.reshape(-1, 28, 28)
        elif task_type == 'cnn':
            X_train, X_test = X_train.reshape(-1, 28, 28, 1), X_test.reshape(-1, 28, 28, 1)

        logging.info(f"Training {task_type} model...")
        model.fit(X_train, y_train, epochs=5, batch_size=128, verbose=1)

        loss, accuracy = model.evaluate(X_test, y_test)
        logging.info(f"{task_type} model training complete. Accuracy: {accuracy}, Loss: {loss}")

        # Publish the result to Kafka
        result = {"task_type": task_type, "accuracy": accuracy, "loss": loss}
        producer.send('training-results', result)
        logging.info(f"Sent result to Kafka: {result}")
    except Exception as e:
        logging.error(f"Error in training {task_type} model: {e}")
        raise HTTPException(status_code=500, detail=f"{task_type} Model Error: {e}")

# **Model Builders with Logging**
def build_mlp_model(input_shape):
    logging.info("Building MLP model...")
    model = Sequential([
        Flatten(input_shape=input_shape),
        Dense(128, activation='relu'),
        Dropout(0.2),
        Dense(128, activation='relu'),
        Dropout(0.2),
        Dense(10, activation='softmax')
    ])
    model.compile(optimizer=Adam(), loss='categorical_crossentropy', metrics=['accuracy'])
    return model

def build_lstm_model(input_shape):
    logging.info("Building LSTM model...")
    model = Sequential([
        LSTM(128, input_shape=input_shape, return_sequences=False),
        Dropout(0.2),
        Dense(128, activation='relu'),
        Dropout(0.2),
        Dense(10, activation='softmax')
    ])
    model.compile(optimizer=Adam(), loss='categorical_crossentropy', metrics=['accuracy'])
    return model

def build_cnn_model(input_shape):
    logging.info("Building CNN model...")
    model = Sequential([
        Conv2D(32, (3, 3), activation='relu', input_shape=input_shape),
        MaxPooling2D((2, 2)),
        Conv2D(64, (3, 3), activation='relu'),
        MaxPooling2D((2, 2)),
        Flatten(),
        Dense(128, activation='relu'),
        Dropout(0.5),
        Dense(10, activation='softmax')
    ])
    model.compile(optimizer=Adam(), loss='categorical_crossentropy', metrics=['accuracy'])
    return model

# **API Endpoints**
@app.get("/health")
async def health_check():
    logging.info("Health check requested")
    return {"status": "Service is running!"}
