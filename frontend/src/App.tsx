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
  // CircularProgress,
  ThemeProvider,
  IconButton,
  Slide,
  useScrollTrigger,
  ButtonGroup,
  Alert,
  Snackbar,
} from '@mui/material';
import theme from './theme';
import DeleteIcon from '@mui/icons-material/Delete';
import CloudUploadIcon from '@mui/icons-material/CloudDownload'
const App: React.FC = () => {
  const [loadingLogs, setLoadingLogs] = useState<string[]>([]);
  const [trainingLogs, setTrainingLogs] = useState<string[]>([]);
  const [trainingResults, setTrainingResults] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [isTraining, setIsTraining] = useState<boolean>(false);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');
  const [snackbarSeverity, setSnackbarSeverity] = useState<'success' | 'error'>('success');
  
  const API_BASE_URL = 'http://localhost:5000';

  useEffect(() => {
    const eventSource = new EventSource(`${API_BASE_URL}/logs/stream`);

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log('Received data:', data);

      switch (data.log_type) {
        case 'loading':
          addLog(setLoadingLogs, data.message);
          break;
        case 'training':
          const trainingMessage =
            data.epoch !== undefined
              ? `${data.worker_id}:Epoch ${data.epoch}: Accuracy - ${data.accuracy }, Loss - ${data.loss }`
              : data.message;
          addLog(setTrainingLogs, trainingMessage);
          break;
        case 'result':
          showSnackbar(`${data.task_type} model training successfully completed`, 'success');  
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

  const showSnackbar = (message: string, severity: 'success' | 'error' = 'success') => {
    setSnackbarMessage(message);
    setSnackbarSeverity(severity);
    setSnackbarOpen(true);
  };
  
  const handleSnackbarClose = () => {
    setSnackbarOpen(false);
  };
  
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
      showSnackbar('Downloading MNIST data...', 'success');
      await axios.post(`${API_BASE_URL}/store_mnist_dataset_to_cassandra`);
      showSnackbar('MNIST data downloaded and stored in Cassandra.', 'success');
    } catch (error) {
      showSnackbar('Failed to download MNIST data.', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleRedis = async () => {
    setLoading(true);
    try {
      await axios.get(`${API_BASE_URL}/store_data_from_cassandra_to_redis`);
      showSnackbar('Data loaded into Redis successfully.', 'success');
    } catch (error) {
      console.error('Failed to load data into Redis.', error);
      showSnackbar('Failed to load data into Redis.', 'error');
    } finally {
      setLoading(false);
    }
  };
  const handleTraining = async (taskType: string) => {
    setIsTraining(true);
    try {
      await axios.post(`${API_BASE_URL}/send_task/${taskType}`);
      showSnackbar(`${taskType} training started.`, 'success');
    } catch (error) {
      console.error(`Failed to start ${taskType} training.`, error);
      showSnackbar(`Failed to start ${taskType} training.`, 'error');
    } finally {
      setIsTraining(false);
    }
  };

  const clearLogs = (setter: React.Dispatch<React.SetStateAction<string[]>>) => {
    setter([]);
  };

  return (
    <ThemeProvider theme={theme}>
          <Snackbar
          open={snackbarOpen}
          autoHideDuration={6000}
          onClose={handleSnackbarClose}
          anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
        >
          <Alert onClose={handleSnackbarClose} severity={snackbarSeverity} sx={{ width: '100%' }}>
            {snackbarMessage}
          </Alert>
        </Snackbar>

      <CssBaseline />
      <Container maxWidth="lg">
        <Slide appear={false} direction="down" in={!useScrollTrigger()}>
          <AppBar position="sticky" elevation={4}>
            <Toolbar>
              <Typography variant="h5" sx={{ flexGrow: 1 }}>
              Distributed Machine Learning Training System 
              </Typography>
            </Toolbar>
          </AppBar>
        </Slide>

        <Grid container spacing={4} sx={{ mt: 4, mb: 4 }}>
          <Grid item xs={12}>
            <Box display="flex" justifyContent="center" gap={2}>

            <ButtonGroup variant="outlined" aria-label="Basic button group" >
              <Button
                onClick={handleDownload}
                disabled={loading || isTraining}
                startIcon={<CloudUploadIcon />}
                color="primary"
              >
                Load Data to Cassandra
              </Button>
              <Button
startIcon={<CloudUploadIcon />}
                onClick={handleRedis}
                disabled={loading || isTraining}
              >
                Load Data to Redis
              </Button>
              </ButtonGroup>

              <ButtonGroup aria-label="Basic button group"  >
              <Button

                onClick={() => handleTraining('mlp')}
                disabled={loading || isTraining}
              >
                Train MLP
              </Button>
              <Button

                onClick={() => handleTraining('lstm')}
                disabled={loading || isTraining}
              >
                Train LSTM
              </Button>
              <Button

                onClick={() => handleTraining('cnn')}
                disabled={loading || isTraining}
              >
                Train CNN
              </Button>
              </ButtonGroup>


            </Box>
          </Grid>

          <Grid item xs={12} md={6}>
            <Box display="flex" justifyContent="space-between" alignItems="center">
            <Typography variant="h6">Loading Logs</Typography>
                <IconButton onClick={() => clearLogs(setLoadingLogs)} size="small">
                  <DeleteIcon />
                </IconButton>
          </Box>
            <Paper elevation={3} sx={{  mt:2, p: 1,  overflowY: 'auto',height: '30vh'  }}>
              <Box display="flex" justifyContent="space-between" alignItems="center"  >
               
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
          <Box display="flex" justifyContent="space-between" alignItems="center">
          <Typography variant="h6">Training Logs</Typography>
            < IconButton onClick={() => clearLogs(setTrainingLogs)} size="small">
                  <DeleteIcon />
                </IconButton>  
                
                </Box>
            <Paper elevation={3} sx={{ mt:2, p: 1, overflowY: 'auto',height: '30vh' }}>
              <Box display="flex" justifyContent="space-between" alignItems="center" >

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
          <Box display="flex" justifyContent="space-between" alignItems="center">
          <Typography variant="h6">Training Results</Typography>
 </Box>
         
            <Paper elevation={3} sx={{mt:2, p: 3 }}>
             
              {/* {loading ? (
                <CircularProgress />
              ) : ( */}
                <List>
                  {trainingResults.map((result, index) => (
                    <ListItem key={index}>
                      <ListItemText
                        primary={`${result.worker_id}: ${result.task_type}: Accuracy - ${result.accuracy }, Loss - ${result.loss }`}
                      />
                    </ListItem>
                  ))}
                </List>
              {/* )} */}
            </Paper>
          </Grid>
        </Grid>

      </Container>
    </ThemeProvider>
  );
};

export default App;
