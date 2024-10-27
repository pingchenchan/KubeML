import asyncio
import json
import logging
import threading
from confluent_kafka import Producer, Consumer, KafkaException, KafkaError
from confluent_kafka.admin import AdminClient, NewTopic
from http.client import HTTPException
from settings import KAFKA_SERVER


def create_kafka_topics():
    admin_client = AdminClient({'bootstrap.servers': ','.join(KAFKA_SERVER)})
    logging.info("Creating Kafka topics, servers are: " + ','.join(KAFKA_SERVER))

    topics = [
        {'name': 'task', 'partitions': 3, 'replication_factor': 3},
        {'name': 'training_log', 'partitions': 2, 'replication_factor': 2},
        {'name': 'load_data', 'partitions': 2, 'replication_factor': 1}
    ]
    
    try:
        # Fetch existing topics to avoid recreating them
        existing_topics = admin_client.list_topics(timeout=10).topics
        print(f"Existing topics: {list(existing_topics.keys())}")
    except Exception as e:
        print(f"Error fetching existing topics: {e}")
        return  # Exit if Kafka connection fails
    
    new_topics = [
        NewTopic(topic['name'], 
                 num_partitions=topic['partitions'], 
                 replication_factor=topic['replication_factor'])
        for topic in topics if topic['name'] not in existing_topics
    ]

    if new_topics:
        futures = admin_client.create_topics(new_topics)
        for topic, future in futures.items():
            try:
                future.result()  
                print(f"Created topic: {topic}")
            except Exception as e:
                print(f"Failed to create topic {topic}: {e}")


create_kafka_topics()


producer = Producer({'bootstrap.servers': ','.join(KAFKA_SERVER)})

def delivery_report(err, msg):
    """Callback function to confirm message delivery."""
    if err is not None:
        logging.error(f"Message delivery failed: {err}")
    else:
        logging.info(f"Message delivered to {msg.topic()} [{msg.partition()}]")

def send_to_kafka(topic, message):
    try:
        producer.produce(topic, json.dumps(message).encode('utf-8'), callback=delivery_report)
        producer.flush()
        logging.info(f"Sent message to Kafka topic: {topic}")
    except KafkaException as e:
        logging.error(f"Failed to send message: {e}")
        raise HTTPException(status_code=500, detail="Kafka send failed")

def send_to_kafka_batch(topic, messages):
    try:
        for message in messages:
            producer.produce(topic, json.dumps(message).encode('utf-8'), callback=delivery_report)
        producer.flush()  
        logging.info(f"Sent {len(messages)} messages to Kafka topic: {topic}")
    except KafkaException as e:
        logging.error(f"Failed to send batch: {e}")
        raise HTTPException(status_code=500, detail="Kafka batch send failed")


def start_kafka_consumer():
    try:
        consumer = Consumer({
            'bootstrap.servers': ','.join(KAFKA_SERVER),
            'group.id': 'training-log-consumer-group-1',
            'auto.offset.reset': 'earliest',
            'group.instance.id': 'log-consumer-instance-1', 
        })

        consumer.subscribe(['training_log'])

        thread = threading.Thread(target=consume_loop, args=(consumer,))
        thread.daemon = True 
        thread.start()
        logging.info("Kafka consumer thread started.")
    except Exception as e:
        logging.error(f"Failed to start Kafka consumer: {e}")
        
message_queue = asyncio.Queue()
def consume_loop(consumer):
    try:
        while True:
            msg = consumer.poll(1.0) 
            if msg is None:
                continue

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    logging.info(f"Reached end of partition: {msg.topic()} [{msg.partition()}] at offset {msg.offset()}")
                else:
                    logging.error(f"Consumer error: {msg.error()}")
                continue


            log_message = json.loads(msg.value().decode('utf-8'))
            logging.info(f"Received Kafka message: {log_message}")

            try:
                consumer.commit(asynchronous=False)
                logging.info(f"Consumer committed offset: {msg.offset()}")
            except KafkaException as e:
                logging.error(f"Failed to commit offset: {e}")


            asyncio.run(message_queue.put(log_message))
            logging.info(f"Message added to message_queue: {message_queue}")

    except KafkaException as e:
        logging.error(f"Kafka consumer error: {e}")
    finally:
        consumer.close()
        logging.info("Kafka consumer closed.")
        
        