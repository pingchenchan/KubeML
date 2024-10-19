import logging
from fastapi import FastAPI,HTTPException
from tensorflow.keras.datasets import mnist
from tensorflow.keras.utils import to_categorical
from fastapi.middleware.cors import CORSMiddleware
from cassandra_utils import connect_to_cassandra, setup_dataset_table,  store_chunked_data
from websocket_utils import websocket_logs, websocket_training_logs
from kafka_utils import get_consumer, producer, send_to_kafka

app = FastAPI()
session = connect_to_cassandra()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
    


@app.on_event("startup")
async def startup_event():
    await producer.start()
    print("Kafka Producer started")


@app.on_event("shutdown")
async def shutdown_event():
    await producer.flush()  # Ensure all messages are sent
    await producer.stop()
    print("Kafka Producer stopped gracefully")
    


@app.get("/test-producer")
async def test_producer():

    test_message = {"task_type": "mlp", "data": "Hello from Master"}
    await producer.send('test-topic', test_message)
    return {"status": "Message sent", "message": test_message}


@app.get("/kafka-status")
async def kafka_status():
    try:
        metadata = await producer.client.cluster_metadata()
        if metadata.brokers:
            return {"status": "Kafka is reachable"}
        else:
            raise Exception("No Kafka brokers available")
    except Exception as e:
        logging.error(f"Kafka connection error: {e}")
        raise HTTPException(status_code=500, detail="Kafka is not reachable")



@app.post("/send_task/{task_type}")
async def send_task(task_type: str):
    if task_type not in ["mlp", "lstm", "cnn"]:
        raise HTTPException(status_code=400, detail="Invalid task type")
    try:
        task_message = {"task_type": task_type}
        logging.info(f"Sending task: {task_message}")
        await send_to_kafka(task_type, task_message) 
        return {"message": f"Task {task_type} sent to Kafka"}
    except Exception as e:
        logging.error(f"Failed to send message: {e}")
        raise HTTPException(status_code=500, detail="Failed to send task")



async def get_results():
    consumer = await get_consumer()
    results = []

    try:
        while True:
            messages = await consumer.getmany(timeout_ms=1000, max_records=50)
            for tp, msgs in messages.items():
                for msg in msgs:
                    results.append(msg.value)
                    print(f"Received result: {msg.value}")

            # Commit offsets to avoid duplicate processing
            await consumer.commit()
            if not messages:
                break
    except Exception as e:
        logging.error(f"Error consuming messages: {e}")
    finally:
        await consumer.stop()

    return {"results": results}





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

        
# WebSocket routes
app.add_websocket_route("/ws/logs", websocket_logs)
app.add_websocket_route("/ws/training-logs", websocket_training_logs)


@app.post("/store_mnist_blob_data")
async def store_mnist_data(dataset_name):
    try:
        setup_dataset_table(session)
        (X_train, y_train), (X_test, y_test) = mnist.load_data()
        X_train = X_train.astype('float32') / 255
        X_test = X_test.astype('float32') / 255
        y_train = to_categorical(y_train, 10)
        y_test = to_categorical(y_test, 10)


        await store_chunked_data(session, f"{dataset_name}_X_train", X_train)
        await store_chunked_data(session, f"{dataset_name}_y_train", y_train)
        await store_chunked_data(session, f"{dataset_name}_X_test", X_test)
        await store_chunked_data(session, f"{dataset_name}_y_test", y_test)

        return {"status": f"{dataset_name} data successfully stored."}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store dataset: {e}")