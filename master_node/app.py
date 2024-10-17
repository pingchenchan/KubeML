from fastapi import FastAPI, WebSocket, HTTPException, WebSocketDisconnect
from cassandra.cluster import Cluster
from cassandra.query import BatchStatement, SimpleStatement
from tensorflow.keras.datasets import mnist
from tensorflow.keras.utils import to_categorical
import json
import numpy as np
from kafka import KafkaProducer,KafkaConsumer
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid
import asyncio

app = FastAPI()

# Kafka configuration
KAFKA_SERVER = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
producer = KafkaProducer(bootstrap_servers=KAFKA_SERVER,
                         value_serializer=lambda v: json.dumps(v).encode('utf-8'))


# Add CORS middleware to allow communication with frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can restrict this to specific origins later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
    
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_message(self, message: str):
        print(f'Active connections: {len(self.active_connections)}')  # Debugging
        for connection in self.active_connections:
            print('sending message', message)
            await connection.send_text(message)

manager = ConnectionManager()


@app.get("/test-producer")
async def test_producer():
    test_message = {"task_type": "mlp", "data": "Hello from Master"}
    producer.send('test-topic', test_message)
    return {"status": "Message sent", "message": test_message}

@app.post("/send_task/{task_type}")
async def send_task(task_type: str):
    if task_type not in ["mlp", "lstm", "cnn"]:
        raise HTTPException(status_code=400, detail="Invalid task type")

    # Prepare task message
    task_message = {"task_type": task_type}
    producer.send(task_type, task_message)

    return {"message": f"Task {task_type} sent to Kafka"}

@app.get("/results")
async def get_results():
    consumer = KafkaConsumer(
        'training-results',
        bootstrap_servers=KAFKA_SERVER,
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        auto_offset_reset='earliest',  # Optional: start reading from earliest messages
        group_id="master-consumer-group"  # Ensure consumer works in group mode
    )
    
    results = []
    while True:
        message = consumer.poll(timeout_ms=1000)  # Non-blocking polling
        if not message:
            break
        for partition in message.values():
            for msg in partition:
                result = msg.value
                results.append(result)
                print(f"Received result: {result}")

    consumer.close()
    return {"results": results}


# Connect to Cassandra during application startup
cassandra_host = os.getenv('CASSANDRA_HOST', 'localhost')

def connect_to_cassandra():
    try:
        # Initialize Cassandra connection
        cluster = Cluster([cassandra_host])
        session = cluster.connect()

        # Create keyspace if it does not exist
        session.execute("""
            CREATE KEYSPACE IF NOT EXISTS my_dataset_keyspace
            WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};
        """)

        # Switch to the specified keyspace
        session.set_keyspace('my_dataset_keyspace')

        print("Connected to Cassandra and set up keyspace.")

        return session
    except Exception as e:
        print(f"Failed to connect to Cassandra: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")

# Call the connection function at startup
session = connect_to_cassandra()

# Health check endpoint
@app.get("/health")
async def health_check():
    try:
        # Optionally add a check to verify Cassandra connectivity
        session.execute("SELECT now() FROM system.local")
        return {"status": "FastAPI is running", "db_status": "Cassandra is connected"}
    except Exception as e:
        print(f"Health check failed: {e}")
        return {"status": "FastAPI is running", "db_status": "Cassandra connection failed"}

# **Function to download and preprocess MNIST dataset**
def download_and_preprocess_mnist():
    (X_train, y_train), (X_test, y_test) = mnist.load_data()

    # Normalize pixel values to the range [0, 1]
    X_train = X_train.astype('float32') / 255
    X_test = X_test.astype('float32') / 255

    # One-hot encode labels
    y_train = to_categorical(y_train, 10)
    y_test = to_categorical(y_test, 10)

    return X_train, y_train, X_test, y_test

# Store data in batches using a PreparedStatement
# Store data using a PreparedStatement
async  def insert_data(dataset_type, features, labels):
    total_rows = features.shape[0]

    for i in range(total_rows):
        feature = features[i]
        label = labels[i]
        row_id = uuid.uuid4()

        # Prepare and execute each insert
        session.execute(session.prepare("""
            INSERT INTO mnist_data (row_id, dataset_type, features, label)
            VALUES (?, ?, ?, ?)
        """), (row_id, dataset_type, feature.flatten().tolist(), label.tolist()))


        message = f"Inserted row {i + 1} / {total_rows}"
        print(message) 
        await manager.send_message(message) 


# **API to store MNIST data in Cassandra**
@app.post("/store_mnist_data")
async def store_mnist_data():
    message = f"Inserted row {123}"
    print(message) 
    await manager.send_message(message) 
    try:
        # Create table if it doesn't exist
        session.execute("""
            CREATE TABLE IF NOT EXISTS mnist_data (
                row_id UUID PRIMARY KEY,
                dataset_type text,
                features list<float>,
                label list<float>
            );
        """)

        # Download and preprocess MNIST data
        X_train, y_train, X_test, y_test = download_and_preprocess_mnist()

        # Insert both train and test datasets
        insert_data('train', X_train, y_train)
        insert_data('test', X_test, y_test)

        return {"status": "MNIST data successfully stored in Cassandra"}
    except Exception as e:
        print(f"Failed to store MNIST data: {e}")
        raise HTTPException(status_code=500, detail="Failed to store MNIST data")
    
    
# **API to fetch MNIST data from Cassandra**
@app.get("/get_mnist_data/{dataset_type}")
async def get_mnist_data(dataset_type: str):
    try:
        if dataset_type not in ['train', 'test']:
            raise HTTPException(status_code=400, detail="Invalid dataset type. Choose 'train' or 'test'.")

        # Query data from Cassandra
        rows = session.execute(f"SELECT features, label FROM mnist_data WHERE dataset_type = '{dataset_type}' ALLOW FILTERING")

        features = []
        labels = []

        # Collect features and labels
        for row in rows:
            features.append(np.array(row.features, dtype=np.float32).reshape(28, 28))
            labels.append(np.array(row.label, dtype=np.float32))

        # Convert to numpy arrays
        features = np.array(features)
        labels = np.array(labels)

        return {"features": features.tolist(), "labels": labels.tolist()}
    except Exception as e:
        print(f"Failed to retrieve MNIST data: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve MNIST data")
    

@app.websocket("/ws/timer")
async def websocket_timer(websocket: WebSocket):
    await websocket.accept()
    counter = 0  
    try:
        while True:
            await websocket.send_text(str(counter))  
            counter += 1
            await asyncio.sleep(1) 
    except Exception as e:
        print(f"WebSocket disconnected: {e}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await websocket.close()
        
@app.websocket("/ws/logs")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print("WebSocket disconnected")
        
@app.websocket("/ws/training-logs")
async def websocket_training_logs(websocket: WebSocket):
    await websocket.accept()
    consumer = KafkaConsumer(
        'training-log',
        bootstrap_servers=KAFKA_SERVER,
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        group_id="websocket-log-group",
        auto_offset_reset='earliest'
    )

    try:
        for message in consumer:
            log_message = message.value["log"]
            await websocket.send_text(log_message)

    except WebSocketDisconnect:
        logging.info("WebSocket disconnected")
        consumer.close()