
import logging
from fastapi import FastAPI, HTTPException
from kafka_utils import start_kafka_consumer, send_to_kafka
from fastapi.middleware.cors import CORSMiddleware
from redis_utils import cache_to_redis, get_from_redis, redis_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)


# Initialize FastAPI app
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# **Startup Event to Subscribe Kafka Topics**
@app.on_event("startup")
async def startup_event():
    start_kafka_consumer()
    logging.info("Kafka listener starting...")

# **Health Check Endpoint**
@app.get("/health")
async def health_check():
    try:
        redis_client.ping()  # Check Redis connection
        return {"status": "Service running", "db_status": "Cassandra and Redis connected"}
    except Exception as e:
        return {"status": "Service running", "db_status": f"Error: {e}"}
    
    
@app.post("/test_send_training_log")
async def test_send_training_log():
    try:
        send_to_kafka("training_log", {'log_type': 'testing', 'message': f"Test training_log message sent"})
        logging.info("Test training_log message sent")
        return {"status": "Message sent"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send message: {e}")
    
    
@app.post("/cache_to_redis/{key}")
async def cache_data_to_redis(key: str, value: dict):
    try:
        cache_to_redis(key, value)
        return {"status": "Data cached successfully", "key": key, "value": value}
    except Exception as e:
        logging.error(f"Failed to cache data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cache data: {e}")

@app.get("/get_from_redis/{key}")
async def get_data_from_redis(key: str):
    try:
        value = get_from_redis(key)
        return {"status": "Data fetched successfully", "key": key, "value": value}
    except HTTPException as e:
        raise e
    except Exception as e:
        logging.error(f"Failed to fetch data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch data: {e}")