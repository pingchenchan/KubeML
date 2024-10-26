import asyncio
import json
import logging
from fastapi import FastAPI,HTTPException
from tensorflow.keras.datasets import mnist
from tensorflow.keras.utils import to_categorical
from fastapi.middleware.cors import CORSMiddleware
from cassandra_utils import connect_to_cassandra, setup_dataset_table,  store_chunked_data
from kafka_utils import  producer, send_to_kafka,start_kafka_consumer, message_queue 
from cassandra_utils import fetch_mnist_data
from redis_utils import cache_to_redis, get_from_redis, redis_client
from fastapi.responses import StreamingResponse
from fastapi import FastAPI

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)


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
    start_kafka_consumer()
    logging.info("Kafka listener starting...")

def event_stream():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    while True:
        message = loop.run_until_complete(message_queue.get())
        yield f"data: {json.dumps(message)}\n\n"
        loop.run_until_complete(message_queue.task_done())

@app.get("/logs/stream")
async def get_logs():
    """SSE 端點，持續發送 Kafka 消息給前端"""
    async def event_stream():
        while True:
            message = await message_queue.get()

            yield f"data: {json.dumps(message)}\n\n"
            message_queue.task_done()  

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.on_event("shutdown")
async def shutdown_event():
    producer.flush()  # Ensure all messages are sent
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
    if task_type not in ["cnn", "lstm", "mlp"]:
        raise HTTPException(status_code=400, detail="Invalid task type")
    try:
        task_message = {"task_type": task_type}
        logging.info(f"Sending task: {task_message}")
        send_to_kafka("task", task_message) 
        return {"message": f"Task {task_type} sent to Kafka"}
    except Exception as e:
        logging.error(f"Failed to send message: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send task {e}")




# Health check endpoint
@app.get("/health")
async def health_check():
    try:
        # Optionally add a check to verify Cassandra connectivity
        session.execute("SELECT now() FROM system.local")
        redis_client.ping()  # Check Redis connection
        return {"status": "FastAPI is running", "db_status": "Cassandra  and Redis is connected"}
    except Exception as e:
        print(f"Health check failed: {e}")
        return {"status": "FastAPI is running", "db_status": "Cassandra connection failed"}


@app.post("/store_mnist_dataset_to_cassandra")
async def store_mnist_data():
    dataset_name = 'mnist'
    try:
        setup_dataset_table(session)
        send_to_kafka("training_log", {"log_type": "loading", "message": f"Fetcing {dataset_name} data..."})
        logging.info(f"Fetcing {dataset_name} data...")
        (X_train, y_train), (X_test, y_test) = mnist.load_data()
        X_train = X_train.astype('float32') / 255
        X_test = X_test.astype('float32') / 255
        y_train = to_categorical(y_train, 10)
        y_test = to_categorical(y_test, 10)
        
        logging.info(f"Dividing {dataset_name} data into chunks...")
        send_to_kafka("training_log", {"log_type": "loading", "message": f"Dividing {dataset_name} data into chunks..."})
        
        await store_chunked_data(session, f"{dataset_name}_X_train", X_train)
        await store_chunked_data(session, f"{dataset_name}_y_train", y_train)
        await store_chunked_data(session, f"{dataset_name}_X_test", X_test)
        await store_chunked_data(session, f"{dataset_name}_y_test", y_test)
        logging.info(f"{dataset_name} data successfully stored.")
        send_to_kafka("training_log", {"log_type": "loading", "message": f"{dataset_name} data successfully stored."})
        return {"status": f"{dataset_name} data successfully stored."}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store dataset: {e}")
    
    
@app.get("/store_data_from_cassandra_to_redis")
async def fetch_mnist_data_from_cassandra():
    dataset_name='mnist'
    try:
        # Check if data is cached in Redis
        if redis_client.exists(dataset_name):
            message = f"Checking Redis cache for {dataset_name} data..."
            send_to_kafka("training_log", {"log_type": "loading", "message": f"{message}"})
            message = f"Succesfully fetched {dataset_name} data from Redis cache."
            send_to_kafka("training_log", {"log_type": "loading", "message": f"{message}"})
            return {'cached': True}
        

        message = f"Data not found in Redis cache. Fetching {dataset_name} data from Cassandra..."
        send_to_kafka("training_log", {"log_type": "loading", "message": f"{message}"})
        logging.info(message)
        message = f"Merge chunks and decode {dataset_name} data..."
        send_to_kafka("training_log", {"log_type": "loading", "message": f"{message}"})
        X_train = await fetch_mnist_data(session, f"{dataset_name}_X_train")
        y_train = await fetch_mnist_data(session, f"{dataset_name}_y_train")
        X_test = await fetch_mnist_data(session, f"{dataset_name}_X_test")
        y_test = await fetch_mnist_data(session, f"{dataset_name}_y_test")
        

        print('X_train.shape', X_train.shape, 'y_train.shape', y_train.shape, 'X_test.shape', X_test.shape, 'y_test.shape', y_test.shape)
        print('type(X_train)', type(X_train))
        cache_to_redis(dataset_name, {"X_train": X_train, "y_train": y_train, "X_test": X_test, "y_test": y_test})
        
        cached_data = get_from_redis(dataset_name)
        if cached_data:
            message = f"Fetching {dataset_name} data from Redis cache..."
            logging.info(message)
            message = f"Decoding and deserializing {dataset_name} data..."
            send_to_kafka("training_log", {"log_type": "loading", "message": f"{message}"})

            X_train = cached_data.get("X_train")
            y_train = cached_data.get("y_train")
            X_test = cached_data.get("X_test")
            y_test = cached_data.get("y_test")

            print('Get from redis X_train.shape', X_train.shape, 'y_train.shape', y_train.shape, 'X_test.shape', X_test.shape, 'y_test.shape', y_test.shape)
            print('type(X_train)', type(X_train))
            message = f"Data successfully stored in Redis cache."
            send_to_kafka("training_log", {"log_type": "loading", "message": f"{message}"})
            return {"status": "Data fetched from Redis cache", "cached": True}
        return {"status": "Data fetched from Cassandra", "cached": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch data: {e}")
    
    
    