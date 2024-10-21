import asyncio
import json
import logging
import threading
from confluent_kafka import Producer, Consumer, KafkaException,KafkaError
from http.client import HTTPException
from redis_utils import get_from_redis
from settings import KAFKA_SERVER, WORKER_ID
from models import build_cnn_model, build_lstm_model, build_mlp_model
from tensorflow.keras.models import Sequential
from tensorflow.keras.callbacks import Callback
import tensorflow.keras.backend as K
import gc

producer = Producer({'bootstrap.servers': ','.join(KAFKA_SERVER)})

async def train_model(task_type: str, model: Sequential):
    dataset_name = 'mnist'
    try:
        logging.info(f"Fetching data from Redis for {dataset_name}")
        cached_data = get_from_redis(dataset_name)
        if cached_data:
            logging.info(f"Fetched data from Redis for {dataset_name}")
            
            X_train = cached_data.get("X_train")
            y_train = cached_data.get("y_train")
            X_test = cached_data.get("X_test")
            y_test = cached_data.get("y_test")

            logging.info(
                f"Get from redis X_train.shape: {X_train.shape}, y_train.shape: {y_train.shape}, X_test.shape: {X_test.shape}, y_test.shape: {y_test.shape}"
            )
            
            logging.info(f'type(X_train): {type(X_train)}')
            
        else:
            logging.error(f"No data found in Redis for {dataset_name}")
            raise ValueError(f"No data found in Redis cache for {dataset_name}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch data: {e}")


    if task_type == 'lstm':
        X_train, X_test = X_train.reshape(-1, 28, 28), X_test.reshape(-1, 28, 28)
    elif task_type == 'cnn':
        X_train, X_test = X_train.reshape(-1, 28, 28, 1), X_test.reshape(-1, 28, 28, 1)

    logging.info(f"Training {task_type} model...")
    send_to_kafka('training_log',{'log_type': 'training', 'message': f"{WORKER_ID} is training {task_type} model..."})
    
    kafka_callback = KafkaCallback(task_type)
    model.fit(X_train, y_train, epochs=5, batch_size=128, verbose=1, callbacks=[kafka_callback])
    loss, accuracy = model.evaluate(X_test, y_test)
    
    logging.info(f"{task_type} training complete. Accuracy: {accuracy:.3f}, Loss: {loss:.3f}")
    # Publish result to Kafka
    result = {
        'worker_id': WORKER_ID,
        'log_type': 'result',
        'task_type': task_type,
        'accuracy': f"{accuracy:.3f}",
        'loss': f"{loss:.3f}"
    }
    send_to_kafka('training_log', result)
    
    del X_train, y_train, X_test, y_test, model  
    clear_session() 
    force_gc() 

class KafkaCallback(Callback):
    def __init__(self, task_type):
        super().__init__()
        self.task_type = task_type

    def on_epoch_end(self, epoch, logs=None):
        message = {
            "task_type": self.task_type,
            "epoch": epoch,
            "accuracy": f"{logs.get('accuracy'):.3f}" if logs.get("accuracy") is not None else None,
            "loss": f"{logs.get('loss'):.3f}" if logs.get("loss") is not None else None,
            'log_type': 'training',
            'worker_id': WORKER_ID
        }
        
        
        send_to_kafka('training_log', message)


async def handle_task(task):
    """處理 Kafka 消息中的任務"""
    try:
        if task is None or 'task_type' not in task:
            raise ValueError("Invalid task received: task is None or missing 'task_type'")
        
        task_type = task['task_type']
        logging.info(f"Received task: {task_type}")

        # 根據 task_type 執行不同模型的訓練
        if task_type == 'mlp':
            await train_model(task_type, build_mlp_model((28, 28)))
        elif task_type == 'lstm':
            await train_model(task_type, build_lstm_model((28, 28)))
        elif task_type == 'cnn':
            await train_model(task_type, build_cnn_model((28, 28, 1)))
    except Exception as e:
        logging.error(f"Task execution error: {e}")

def consume_loop(consumer):
    """Kafka 消費者的同步消費迴圈"""
    try:
        while True:
            msg = consumer.poll(timeout=1.0)  # 每秒輪詢一次消息
            if msg is None:
                # logging.info("No message received in this poll.")
                continue

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    logging.info(f"Reached end of partition: {msg.topic()} [{msg.partition()}] at offset {msg.offset()}")
                else:
                    logging.error(f"Consumer error: {msg.error()}")
                continue
            
            logging.info(f"Message received from topic {msg.topic()}: {msg.value().decode('utf-8')}")
            try:
                consumer.commit(asynchronous=False)
                logging.info(f"Cosumer committed offset: {msg.offset()}")
            except KafkaException as e:
                logging.error(f"Failed to commit offset: {e}")
            
            try:
                task = json.loads(msg.value().decode('utf-8'))
                asyncio.run(handle_task(task))
            except json.JSONDecodeError as e:
                logging.error(f"Failed to decode JSON message: {e}")
            task = json.loads(msg.value().decode('utf-8'))




    except KafkaException as e:
        logging.error(f"Kafka consumer error: {e}")
    except KeyboardInterrupt:
        logging.info("Kafka consumer stopped by user.")
    finally:
        consumer.close()
        logging.info("Kafka consumer closed.")


def start_kafka_consumer():
    try:
        consumer = Consumer({
            'bootstrap.servers': ','.join(KAFKA_SERVER),
            'group.id': 'task-consumer-group-1',
            'auto.offset.reset': 'earliest'
        })
        consumer.subscribe(["task"])

        logging.info("Kafka consumer subscribed to topics: ['task']")
        

        thread = threading.Thread(target=consume_loop, args=(consumer,))
        thread.daemon = True
        thread.start()
        logging.info("Kafka listener thread started...")
    except Exception as e:
        logging.error(f"Failed to start Kafka consumer: {e}")
    


def send_to_kafka(topic, message):
    """同步發送 Kafka 消息。"""
    try:
        producer.produce(
            topic=topic,
            value=json.dumps(message).encode('utf-8'),
            callback=delivery_report
        )
        producer.flush()  # 確保消息送出
        logging.info(f"Sent message to Kafka topic {topic} with message: {message}")
    except KafkaException as e:
        logging.error(f"Failed to send message to Kafka: {e}")
        raise HTTPException(status_code=500, detail="Kafka send failed")

def delivery_report(err, msg):
    """Kafka Producer 回呼函數，在消息成功傳遞時呼叫。"""
    if err is not None:
        logging.error(f"Message delivery failed: {err}")
    else:
        logging.info(f"Message delivered to {msg.topic()} [{msg.partition()}]")
def clear_session():
    K.clear_session()
    logging.info("TensorFlow session cleared to release memory.")

def force_gc():
    gc.collect()
    logging.info("Garbage collection executed.")