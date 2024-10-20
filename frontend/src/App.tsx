import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  AppBar,
  Toolbar,
  Typography,
  Container,
  Box,
  Button,
  List,
  ListItem,
  ListItemText,
  Paper,
  CssBaseline,
  Grid,
  CircularProgress,
  ThemeProvider,
  IconButton,
  Slide,
  useScrollTrigger,
} from '@mui/material';
import theme from './theme';
import DeleteIcon from '@mui/icons-material/Delete';

const App: React.FC = () => {
  const [loadingLogs, setLoadingLogs] = useState<string[]>([]);
  const [trainingLogs, setTrainingLogs] = useState<string[]>([]);
  const [trainingResults, setTrainingResults] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [isTraining, setIsTraining] = useState<boolean>(false);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const API_BASE_URL = 'http://localhost:5000';

  useEffect(() => {
    const eventSource = new EventSource(`${API_BASE_URL}/logs/stream`);

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);

      switch (data.log_type) {
        case 'loading':
          addLog(setLoadingLogs, data.message);
          break;
        case 'training':
          const trainingMessage =
            data.epoch !== undefined
              ? `Epoch ${data.epoch}: Accuracy - ${data.accuracy}, Loss - ${data.loss}`
              : data.message;
          addLog(setTrainingLogs, trainingMessage);
          break;
        case 'result':
          setTrainingResults((prevResults) => [...prevResults, data]);
          break;
        default:
          console.warn('Unknown log type:', data.log_type);
      }
    };

    eventSource.onerror = (error) => {
      console.error('SSE connection error:', error);
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, []);

  const addLog = (
    setter: React.Dispatch<React.SetStateAction<string[]>>,
    message: string
  ) => {
    setter((prevLogs) => {
      const newLogs = [...prevLogs, message];
      if (newLogs.length > 100) newLogs.shift();
      return newLogs;
    });

    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleDownload = async () => {
    setLoading(true);
    try {
      await axios.post(`${API_BASE_URL}/store_mnist_dataset_to_cassandra`);
      alert('MNIST data downloaded and stored in Cassandra.');
    } catch (error) {
      console.error('Failed to download MNIST data.', error);
    } finally {
      setLoading(false);
    }
  };

  const handleRedis = async () => {
    setLoading(true);
    try {
      await axios.get(`${API_BASE_URL}/store_data_from_cassandra_to_redis`);
      alert('Data loaded into Redis successfully.');
    } catch (error) {
      console.error('Failed to load data into Redis.', error);
    } finally {
      setLoading(false);
    }
  };

  const handleTraining = async (taskType: string) => {
    setIsTraining(true);
    try {
      await axios.post(`${API_BASE_URL}/send_task/${taskType}`);
      alert(`${taskType} training started.`);
    } catch (error) {
      console.error(`Failed to start ${taskType} training.`, error);
    } finally {
      setIsTraining(false);
    }
  };

  const clearLogs = (setter: React.Dispatch<React.SetStateAction<string[]>>) => {
    setter([]);
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Container maxWidth="lg">
        <Slide appear={false} direction="down" in={!useScrollTrigger()}>
          <AppBar position="sticky" elevation={4}>
            <Toolbar>
              <Typography variant="h5" sx={{ flexGrow: 1 }}>
                Machine Learning Dashboard
              </Typography>
            </Toolbar>
          </AppBar>
        </Slide>

        <Grid container spacing={4} sx={{ mt: 4, mb: 4 }}>
          <Grid item xs={12}>
            <Box display="flex" justifyContent="center" gap={2}>
              <Button
                variant="contained"
                onClick={handleDownload}
                disabled={loading || isTraining}
              >
                Download Dataset
              </Button>
              <Button
                variant="contained"
                onClick={handleRedis}
                disabled={loading || isTraining}
              >
                Load Data to Redis
              </Button>
              <Button
                variant="contained"
                onClick={() => handleTraining('mlp')}
                disabled={loading || isTraining}
              >
                Train MLP
              </Button>
              <Button
                variant="contained"
                onClick={() => handleTraining('lstm')}
                disabled={loading || isTraining}
              >
                Train LSTM
              </Button>
              <Button
                variant="contained"
                onClick={() => handleTraining('cnn')}
                disabled={loading || isTraining}
              >
                Train CNN
              </Button>
            </Box>
          </Grid>

          <Grid item xs={12} md={6}>
            <Paper elevation={3} sx={{ p: 2, maxHeight: 300, overflowY: 'auto' }}>
              <Box display="flex" justifyContent="space-between" alignItems="center">
                <Typography variant="h6">Loading Logs</Typography>
                <IconButton onClick={() => clearLogs(setLoadingLogs)} size="small">
                  <DeleteIcon />
                </IconButton>
              </Box>
              <List>
                {loadingLogs.map((log, index) => (
                  <ListItem key={index}>
                    <ListItemText primary={log} />
                  </ListItem>
                ))}
                <div ref={logsEndRef} />
              </List>
            </Paper>
          </Grid>

          <Grid item xs={12} md={6}>
            <Paper elevation={3} sx={{ p: 2, maxHeight: 300, overflowY: 'auto' }}>
              <Box display="flex" justifyContent="space-between" alignItems="center">
                <Typography variant="h6">Training Logs</Typography>
                <IconButton onClick={() => clearLogs(setTrainingLogs)} size="small">
                  <DeleteIcon />
                </IconButton>
              </Box>
              <List>
                {trainingLogs.map((log, index) => (
                  <ListItem key={index}>
                    <ListItemText primary={log} />
                  </ListItem>
                ))}
                <div ref={logsEndRef} />
              </List>
            </Paper>
          </Grid>

          <Grid item xs={12}>
            <Paper elevation={3} sx={{ p: 3 }}>
              <Typography variant="h6">Training Results</Typography>
              {loading ? (
                <CircularProgress />
              ) : (
                <List>
                  {trainingResults.map((result, index) => (
                    <ListItem key={index}>
                      <ListItemText
                        primary={`${result.task_type}: Accuracy - ${result.accuracy}, Loss - ${result.loss}`}
                      />
                    </ListItem>
                  ))}
                </List>
              )}
            </Paper>
          </Grid>
        </Grid>
      </Container>
    </ThemeProvider>
  );
};

export default App;
