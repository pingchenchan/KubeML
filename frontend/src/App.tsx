import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const App: React.FC = () => {
  const [trainingResults, setTrainingResults] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [isTraining, setIsTraining] = useState<boolean>(false); // Track if training is in progress
  const API_BASE_URL = 'http://master-node:5000'; // Use Docker service name

  const fetchResults = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/results`);
      setTrainingResults(response.data.results);
      setLoading(false);
      setIsTraining(false); // Re-enable buttons after receiving results
    } catch (error) {
      console.error('Error fetching results:', error);
      setLoading(false);
      setIsTraining(false);
    }
  };

  const pollResults = useCallback(() => {
    const intervalId = setInterval(async () => {
      console.log("Polling for results...");
      await fetchResults();
    }, 5000); // Poll every 5 seconds

    return () => clearInterval(intervalId); // Clear interval when component unmounts
  }, []);

  const handleDownload = async () => {
    try {
      setLoading(true);
      await axios.post(`${API_BASE_URL}/store_mnist_data`);
      alert('MNIST data downloaded and stored in Cassandra.');
      setLoading(false);
    } catch (error) {
      console.error('Error downloading MNIST:', error);
      alert('Failed to download MNIST data.');
      setLoading(false);
    }
  };

  const handleTraining = async (taskType: string) => {
    try {
      setLoading(true);
      setIsTraining(true); // Disable all buttons during training
      await axios.post(`${API_BASE_URL}/send_task/${taskType}`);
      alert(`${taskType} training started.`);

      // Start polling for results after sending the task
      pollResults();
    } catch (error) {
      console.error(`Error starting ${taskType} training:`, error);
      alert(`Failed to start ${taskType} training.`);
      setLoading(false);
      setIsTraining(false);
    }
  };

  useEffect(() => {
    fetchResults(); // Fetch initial results on component mount
  }, []);

  return (
    <div className="App">
      <h1>Machine Learning Platform</h1>
      <button onClick={handleDownload} disabled={loading || isTraining}>
        Download MNIST Dataset
      </button>
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
    </div>
  );
};

export default App;
