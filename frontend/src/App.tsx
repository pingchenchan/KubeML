import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import usePersistentWebSocket from './usePersistentWebSocket';

const App: React.FC = () => {
  const [trainingResults, setTrainingResults] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [isTraining, setIsTraining] = useState<boolean>(false);
  const [logMessages, setLogMessages] = useState<string>('');
  const [trainingLogs, setTrainingLogs] = useState<string>('');

  const API_BASE_URL = 'http://localhost:5000';

  const handleLogMessage = (data: string) => {
    console.log("Log message received:", data);
    setLogMessages( data);
  };

  const handleTrainingLog = (data: string) => {
    console.log("Training log received:", data);
    setTrainingLogs(data)
  };

  usePersistentWebSocket('ws://localhost:5000/ws/logs', handleLogMessage);
  usePersistentWebSocket('ws://localhost:5000/ws/training-logs', handleTrainingLog);



 
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
        {logMessages? (
          <ul>
            {logMessages}
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
            {trainingLogs}
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
