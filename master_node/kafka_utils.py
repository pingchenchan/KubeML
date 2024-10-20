import asyncio
import json
import logging
import threading
from confluent_kafka import Producer, Consumer, KafkaException, KafkaError
from confluent_kafka.admin import AdminClient, NewTopic
from http.client import HTTPException
from settings import KAFKA_SERVER


def create_kafka_topics():
    """檢查並創建 Kafka 主題。"""
    admin_client = AdminClient({'bootstrap.servers': KAFKA_SERVER})
    topics = ['task', 'training_log']
    existing_topics = admin_client.list_topics().topics

    new_topics = [
        NewTopic(topic, num_partitions=1, replication_factor=1)
        for topic in topics if topic not in existing_topics
    ]

    if new_topics:
        futures = admin_client.create_topics(new_topics)
        for topic, future in futures.items():
            try:
                future.result()  # 阻塞等待主題創建完成
                print(f"Created topic: {topic}")
            except Exception as e:
                print(f"Failed to create topic {topic}: {e}")

# 在程式啟動時呼叫
create_kafka_topics()

# 配置 Kafka Producer
producer = Producer({'bootstrap.servers': KAFKA_SERVER})

def delivery_report(err, msg):
    """Callback function to confirm message delivery."""
    if err is not None:
        logging.error(f"Message delivery failed: {err}")
    else:
        logging.info(f"Message delivered to {msg.topic()} [{msg.partition()}]")

def send_to_kafka(topic, message):
    """同步發送單個 Kafka 消息。"""
    try:
        producer.produce(topic, json.dumps(message).encode('utf-8'), callback=delivery_report)
        producer.flush()  # 確保消息送出
        logging.info(f"Sent message to Kafka topic: {topic}")
    except KafkaException as e:
        logging.error(f"Failed to send message: {e}")
        raise HTTPException(status_code=500, detail="Kafka send failed")

def send_to_kafka_batch(topic, messages):
    """同步批次發送多個 Kafka 消息。"""
    try:
        for message in messages:
            producer.produce(topic, json.dumps(message).encode('utf-8'), callback=delivery_report)
        producer.flush()  # 確保所有消息都送出
        logging.info(f"Sent {len(messages)} messages to Kafka topic: {topic}")
    except KafkaException as e:
        logging.error(f"Failed to send batch: {e}")
        raise HTTPException(status_code=500, detail="Kafka batch send failed")


def start_kafka_consumer():
    """在獨立執行緒中啟動 Kafka 消費者"""
    try:
        consumer = Consumer({
            'bootstrap.servers': KAFKA_SERVER,
            'group.id': 'log-consumer-group0',
            'auto.offset.reset': 'earliest',
            'group.instance.id': 'log-consumer-instance-1', 
        })

        consumer.subscribe(['training_log'])

        # 在新執行緒中運行 Kafka 消費者的同步消費邏輯
        thread = threading.Thread(target=consume_loop, args=(consumer,))
        thread.daemon = True  # 設置為守護執行緒，主程式結束時自動退出
        thread.start()
        logging.info("Kafka consumer thread started.")
    except Exception as e:
        logging.error(f"Failed to start Kafka consumer: {e}")
        
message_queue = asyncio.Queue()
def consume_loop(consumer):
    """Kafka 消費者的同步消費迴圈"""
    try:
        while True:
            msg = consumer.poll(1.0)  # 每秒輪詢一次消息
            if msg is None:
                continue

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    logging.info(f"Reached end of partition: {msg.topic()} [{msg.partition()}] at offset {msg.offset()}")
                else:
                    logging.error(f"Consumer error: {msg.error()}")
                continue

            # 解碼並處理消息
            log_message = json.loads(msg.value().decode('utf-8'))
            logging.info(f"Received Kafka message: {log_message}")

            try:
                consumer.commit(asynchronous=False)
                logging.info(f"Consumer committed offset: {msg.offset()}")
            except KafkaException as e:
                logging.error(f"Failed to commit offset: {e}")

            # 將消息放入消息佇列或共享變數中，以供 SSE 端點讀取
            asyncio.run(message_queue.put(log_message))
            logging.info(f"Message added to message_queue: {message_queue}")

    except KafkaException as e:
        logging.error(f"Kafka consumer error: {e}")
    finally:
        consumer.close()
        logging.info("Kafka consumer closed.")
        
        