# Distributed Machine Learning Training System with Monitoring

Table of content
- [Distributed Machine Learning Training System with Monitoring](#distributed-machine-learning-training-system-with-monitoring)
    - [Overview](#overview)
    - [Architecture Introduction](#architecture-introduction)
    - [Setup: Running the System with docker-compose](#setup-running-the-system-with-docker-compose)
    - [Design Considerations](#design-considerations)
    - [Core Features](#core-features)
    - [Ports and Service Access](#ports-and-service-access)
    - [API Endpoints and Workflow](#api-endpoints-and-workflow)

Detailed usage of each service
- [Cassandra Usage in this System: Architecture and Best Practices](docs/Cassandra.md)
- [Kafka Usage in this System: Architecture and Best Practices](docs/kafka.md)
- [Redis Usage in this System: Architecture and Best Practices](docs/Redis.md)

### Overview

This platform provides parallel machine learning training services with real-time feedback. It focuses on training deep learning models on the MNIST dataset using three common architectures: MLP, CNN, and LSTM. The system distributes workloads across multiple worker nodes and streams real-time logs to the frontend, offering users immediate insight into the training process.

### Architecture Introduction

This parallel training platform leverages Cassandra for scalable data storage, Redis for fast caching, and Kafka for real-time monitoring. The system ensures fault tolerance through replication and scalability via distributed worker nodes. With real-time feedback through SSE and continuous monitoring using Prometheus and Grafana, the platform offers a seamless user experience. This architecture is optimized to handle large-scale, parallel machine learning tasks efficiently, making it reliable, scalable, and user-friendly.

### Setup: Running the System with docker-compose

To deploy the entire machine learning platform, use the following command to build and start all services:

```bash
docker-compose up --build
```

This command ensures that each container is built from the specified Dockerfiles and started in the correct order, following the dependencies defined in the docker-compose.yml file.


### Design Considerations

This system is designed to address key scenarios:

- **Parallel Model Training for Scalability:** The platform distributes workloads across multiple worker nodes to handle large datasets and reduce training time.

- **Real-time Feedback for Enhanced User Experience:** Kafka streams logs and updates in real-time to provide instant feedback to users via Server-Sent Events (SSE).

- **Optimized Data Management for Performance:** Redis caching reduces the load on Cassandra, ensuring faster data access and smoother user interactions.

- **High Availability and Fault Tolerance:** Cassandra's replication guarantees data availability, ensuring the system remains operational during node failures.

- **omprehensive System Monitoring:** Prometheus and Grafana monitor system health and resource usage, ensuring reliability and early detection of issues.

### Core Features

**Model Selection and Training Task Initiation:** Provides a user-friendly interface built with React for deep learning model selection and real-time log viewing.
- **Technology Stack:** React, TypeScript, MUI
- **Functionality:**
  - Users select models (MLP, CNN, LSTM) and initiate training.
  - Real-time logs are streamed via SSE to keep users informed.


**Task Coordination and Orchestration:** The master node receives user requests, stores data in Cassandra, and distributes tasks to worker nodes through Kafka.
- **Technology Stack:** FastAPI, Cassandra driver, Kafka
- **Process:**
  - Receives user requests and stores dataset metadata in Cassandra.
  - Publishes training tasks to Kafka topics for consumption by worker nodes.
- **Best Practices:** 
  - **Task Decoupling:** Use Kafka topics to decouple task coordination
  -  **Asynchronous Processing:** Handle requests asynchronously in FastAPI 

**Task Distribution and Real-time Logging:** Kafka handles task distribution between the master and worker nodes and provides real-time log streaming to the frontend.
- **Technology Stack:** Kafka
- **Process:**
  - Tasks are published to Kafka topics for asynchronous consumption by worker nodes.
  - Training logs are streamed back to the frontend via SSE to provide real-time feedback.
- **Best Practices:**
  - **Partitioning Strategy:** Use Kafka partitions to ensure parallel consumption by multiple worker nodes.
  - **Real-time Feedback:** Use Server-Sent Events (SSE) for continuous log streaming to keep users engaged.


**High Availability Data Storage:** Cassandra stores datasets and metadata, ensuring fast read and write operations for training tasks.

- **Technology Stack:** Cassandra
- **Process:**
  - Datasets are chunked into 5MB pieces, compressed, and stored.
  - Metadata is maintained to facilitate efficient data retrieval.
- **Best Practices:**
  - **Replication for Availability:** Use a replication factor of 2 to ensure data availability even during node failures.
  - **Consistency Level Configuration:** Use LOCAL_QUORUM for a balance between performance and consistency.
  - **Compression for Efficiency:** Store datasets in compressed 5MB chunks to improve storage efficiency.
**Parallel Model Training:** Worker nodes retrieve tasks from Kafka, access data from Cassandra or Redis, and perform model training in parallel.
- **Technology Stack:** FastAPI, TensorFlow, Kafka driver, Redis
- **Process:**
  - Each worker node first attempts to fetch data from Redis. If the data is not available, it reads from Cassandra and caches the data in Redis.
  - Trained models and results are sent back to Kafka for real-time monitoring.
- **Best Practices:**
  - **Parallelism and Load Distribution:** Distribute tasks across multiple worker nodes to maximize training throughput.
  - **Caching for Performance:** Use Redis caching to reduce repeated access to Cassandra and improve performance.
  - **Real-time Monitoring:** Send periodic updates during training to Kafka to track task progress.

**In-memory Caching Layer:** Redis stores frequently accessed datasets, reducing the load on Cassandra and improving data retrieval times.

- **Technology Stack:** Redis
- **Process:**
  - Redis caches datasets for fast access during model training.
  - LRU eviction policy ensures optimal memory usage.
- **Best Practices:**
  - **Caching of Datasets:** Redis serves as an in-memory cache for datasets (e.g., MNIST) used during model training, avoiding repeated access to Cassandra and improving performance.

**System Monitoring and Visualization**: Prometheus collects system metrics, and Grafana visualizes resource usage and training progress.
- **Technology Stack:** Prometheus, Grafana
- **Process:**
  - Nodes expose `/metrics` endpoints for Prometheus to gather performance data.
  - Grafana displays metrics and triggers alerts for any potential bottlenecks or failures.
- **Best Practices:**
  - **Alerting and Thresholds**: Set alerts in Grafana for critical system metrics such as CPU or memory spikes.



### Ports and Service Access
Once the system is up, you can access the various services through the following ports:

- Frontend: http://localhost:3001
  - User interface for selecting models and viewing real-time logs.
- Master Node: http://localhost:5000/docs
  - REST API for task management and data coordination.
- Worker Node 1: http://localhost:8000/docs
  - API to monitor individual worker status.
- Worker Node 2: http://localhost:9001/docs
  - API to monitor individual worker status.
- Kafka Management (Kafdrop): http://localhost:9000
  - Monitor Kafka topics and messages.
- Prometheus: http://localhost:9090
  - Monitor system metrics and alerts.
- Grafana: http://localhost:3000
  - Visualize metrics and dashboards.
- Redis: Exposed at localhost:6379 (no web interface).
- Kafka Brokers: Exposed at localhost:6379 (no web interface).
  - Kafka Broker 1: localhost:9092
  - Kafka Broker 2: localhost:9093
  - Kafka Broker 3: localhost:9094
- Cassandra Nodes:
  - Node 1: localhost:9042
  - Node 2: localhost:9142
- Redis Exporter: http://localhost:9121
  - Monitor Redis metrics.
- Kafka Exporter: http://localhost:9308
  - Monitor Kafka metrics.
- cAdvisor: http://localhost:8080
  - Monitor container resource usage.


### API Endpoints and Workflow

Here are the core API endpoints exposed by the master and worker nodes:

**Logs and Status**

```GET /logs/stream``` 
- Streams real-time logs from Kafka to the frontend.

```GET /kafka-status```
- Returns the status of Kafka brokers to ensure connectivity.

**Task Management**

```POST /send_task/{task_type}```
- Sends a training task of the specified type (MLP, CNN, LSTM) to Kafka.

```GET /test-producer```
- Tests the Kafka producer by sending a dummy message.

**Data Management**

```POST /store_mnist_dataset_to_cassandra```
- Stores the MNIST dataset in Cassandra.

```GET /store_data_from_cassandra_to_redis```
- Fetches MNIST data from Cassandra, caches it in Redis, and returns the result.

**Health Check**

```GET /health```
- Checks the health status of the master node.