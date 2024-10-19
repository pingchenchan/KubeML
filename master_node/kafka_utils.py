from http.client import HTTPException
import logging
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
import json
from settings import KAFKA_SERVER

producer = AIOKafkaProducer(
    bootstrap_servers=KAFKA_SERVER,
    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
    linger_ms=10,  # Buffer messages for better performance
    compression_type='gzip',  # Reduce network overhead
)

async def get_consumer():
    consumer = AIOKafkaConsumer(
        'training-log',
        bootstrap_servers=KAFKA_SERVER,
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        group_id="websocket-log-group",
        auto_offset_reset='latest',
        # session_timeout_ms=300000,  # Increase session timeout to 30 seconds
        # heartbeat_interval_ms=100000  # Send heartbeats every 10 seconds
    )
    try:
        await consumer.start()
        return consumer
    except Exception as e:
        logging.error(f"Failed to start Kafka consumer: {e}")
        raise HTTPException(status_code=500, detail="Kafka consumer startup failed.")

async def send_to_kafka(topic, message):
    try:
        """Send message to Kafka asynchronously."""
        await producer.send_and_wait(topic, message)
    except Exception as e:
        logging.error(f"Failed to send to Kafka: {e}")
        raise HTTPException(status_code=500, detail="Kafka send failed")
    
async def send_to_kafka_batch(topic, messages):
    try:
        for message in messages:
            await producer.send(topic, message)
        await producer.flush()  # Ensure all messages are sent
        print(f"Sent {len(messages)} messages to Kafka topic {topic}")
    except Exception as e:
        logging.error(f"Failed to send batch to Kafka: {e}")
        raise HTTPException(status_code=500, detail="Kafka batch send failed")
