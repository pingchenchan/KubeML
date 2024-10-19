import logging
from fastapi import WebSocket, WebSocketDisconnect
from kafka_utils import get_consumer

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logging.info(f"New WebSocket connected: {len(self.active_connections)} active connections")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logging.info(f"WebSocket disconnected: {len(self.active_connections)} active connections")
    async def send_message(self, message: str):
        logging.info(f"Active connections: {len(self.active_connections)}")
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logging.error(f"Failed to send message: {e}")
                self.disconnect(connection)  
                
manager = ConnectionManager()

async def websocket_logs(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logging.info("WebSocket disconnected")

async def websocket_training_logs(websocket: WebSocket):
    await websocket.accept()
    consumer = await get_consumer()
    try:
        while True:
            messages = await consumer.getmany(timeout_ms=1000, max_records=50)
            for tp, msgs in messages.items():
                latest_msg = msgs[-1] if msgs else None
                if latest_msg:
                    log_message = latest_msg.value.get("log", "")
                    await websocket.send_text(log_message)
    except WebSocketDisconnect:
        logging.info("WebSocket disconnected")
    finally:
        await consumer.stop()