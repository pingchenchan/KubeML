import { useEffect, useRef } from 'react';

const usePersistentWebSocket = (url: string, messageHandler: (data: string) => void) => {
  const ws = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<NodeJS.Timeout | null>(null);

  const connectWebSocket = () => {
    console.log('Attempting to connect WebSocket...');
    ws.current = new WebSocket(url);

    ws.current.onopen = () => {
      console.log(`Connected to ${url}`);
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current); // Clear any pending reconnection attempts
        reconnectTimeout.current = null;
      }
    };

    ws.current.onmessage = (event) => {
      console.log(`Received message from ${url}:`, event.data);
      messageHandler(event.data);
    };

    ws.current.onclose = (event) => {
      console.warn(`WebSocket disconnected from ${url}:`, event);
      scheduleReconnect(); // Schedule a reconnection attempt
    };

    ws.current.onerror = (error) => {
      console.error(`WebSocket error from ${url}:`, error);
      scheduleReconnect(); // Attempt reconnection in case of an error
    };
  };

  const scheduleReconnect = () => {
    if (!reconnectTimeout.current) {
      console.log('Scheduling WebSocket reconnection...');
      reconnectTimeout.current = setTimeout(() => {
        connectWebSocket(); // Try to reconnect after 5 seconds
      }, 5000);
    }
  };

  useEffect(() => {
    connectWebSocket(); // Connect WebSocket on component mount

    return () => {
      console.log('Cleaning up WebSocket connection...');
      if (ws.current) {
        ws.current.close(); // Close WebSocket on component unmount
      }
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current); // Clear any pending reconnections
      }
    };
  }, []); // Run only once on mount

  return ws;
};

export default usePersistentWebSocket;
