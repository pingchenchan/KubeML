import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const App: React.FC = () => {
  const [trainingResults, setTrainingResults] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [isTraining, setIsTraining] = useState<boolean>(false);
  const [logMessages, setLogMessages] = useState<string[]>([]);
  const [trainingLogs, setTrainingLogs] = useState<string[]>([]);

  const API_BASE_URL = 'http://localhost:5000';

  // WebSocket 初始化，監聽 `logs` 與 `training-logs`
  useEffect(() => {
    const connectWebSocket = (url: string, messageHandler: (data: string) => void) => {
      const ws = new WebSocket(url);

      ws.onopen = () => console.log(`Connected to ${url}`);
      ws.onmessage = (event) => {
        console.log(`Received message from ${url}:`, event.data);
        messageHandler(event.data);
      };
      ws.onclose = () => console.log(`WebSocket disconnected from ${url}`);
      ws.onerror = (error) => console.error(`WebSocket error from ${url}:`, error);

      return ws;
    };

    const logWs = connectWebSocket(
      'ws://localhost:5000/ws/logs',
      (data) => setLogMessages((prev) => [...prev, data])
    );

    const trainingLogsWs = connectWebSocket(
      'ws://localhost:5000/ws/training-logs',
      (data) => setTrainingLogs((prev) => [...prev, data])
    );

    return () => {
      logWs.close();
      trainingLogsWs.close();
    };
  }, []);

  // 獲取訓練結果
  const fetchResults = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/results`);
      setTrainingResults(response.data.results);
      setLoading(false);
      setIsTraining(false);
    } catch (error) {
      console.error('Error fetching results:', error);
      setLoading(false);
      setIsTraining(false);
    }
  };

  const pollResults = useCallback(() => {
    const intervalId = setInterval(fetchResults, 5000);
    return () => clearInterval(intervalId);
  }, []);

  const handleTask = async (
    action: () => Promise<void>,
    successMessage: string,
    errorMessage: string
  ) => {
    try {
      setLoading(true);
      await action();
      alert(successMessage);
    } catch (error) {
      console.error(errorMessage, error);
      alert(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = () =>
    handleTask(
      () => axios.post(`${API_BASE_URL}/store_mnist_data`),
      'MNIST data downloaded and stored in Cassandra.',
      'Failed to download MNIST data.'
    );

  const handleTestProducer = () =>
    handleTask(
      () => axios.get(`${API_BASE_URL}/test-producer`),
      'Test producer executed.',
      'Failed to execute test producer.'
    );

  const handleTraining = async (taskType: string) => {
    setIsTraining(true);
    await handleTask(
      () => axios.post(`${API_BASE_URL}/send_task/${taskType}`),
      `${taskType} training started.`,
      `Failed to start ${taskType} training.`
    );
    pollResults();
  };

  useEffect(() => {
    fetchResults();
  }, []);

  return (
    <div className="App">
      <h1>Machine Learning Platform</h1>

      <section>
        <h2>Insertion Logs</h2>
        {logMessages.length ? (
          <ul>
            {logMessages.map((msg, index) => (
              <li key={index}>{msg}</li>
            ))}
          </ul>
        ) : (
          <p>No insertion logs available.</p>
        )}
      </section>

      <div>
        <button onClick={handleDownload} disabled={loading || isTraining}>
          Download MNIST Dataset
        </button>
        <button onClick={handleTestProducer}>Test Producer</button>
      </div>

      <div>
        <button onClick={() => handleTraining('mlp')} disabled={loading || isTraining}>
          Train MLP
        </button>
        <button onClick={() => handleTraining('lstm')} disabled={loading || isTraining}>
          Train LSTM
        </button>
        <button onClick={() => handleTraining('cnn')} disabled={loading || isTraining}>
          Train CNN
        </button>
      </div>

      <section>
        <h2>Training Logs</h2>
        {trainingLogs.length ? (
          <ul>
            {trainingLogs.map((log, index) => (
              <li key={index}>{log}</li>
            ))}
          </ul>
        ) : (
          <p>No training logs available.</p>
        )}
      </section>

      <section>
        <h2>Training Results</h2>
        {loading ? (
          <p>Loading...</p>
        ) : (
          <ul>
            {trainingResults.map((result, index) => (
              <li key={index}>
                {result.task_type}: Accuracy - {result.accuracy}, Loss - {result.loss}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
};

export default App;
