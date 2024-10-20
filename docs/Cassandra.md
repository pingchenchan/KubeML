# Cassandra Database Setup

## Nodes and Network Topology

The system consists of two Cassandra nodes running as Docker containers. They communicate through an internal bridge network.

## Data Center and Rack

To reduce management overhead, multi-data center support is disabled. A single data center (dc1) is used, and all nodes belong to the same rack (rack1) for simplified data synchronization.

## Seed Nodes

During cluster startup, nodes identify other cluster members through seed nodes. In this setup, cassandra-node1 and cassandra-node2 are designated as seed nodes to ensure at least one available node for stable startup.

## Performance and Scalability Considerations

### Replication Factor

The replication factor is set to 2 to ensure high availability of data. If one node fails, the other node can still provide read and write services.

### Consistency Level (LOCAL_QUORUM)

The consistency level is set to LOCAL_QUORUM, which ensures that the majority of nodes agree on data read or write operations. This balances data consistency and read performance, making it suitable for applications running within a single data center and minimizing read and write latency.

### Batch Operations within the Same Partition

To avoid cross-partition limitations, it is recommended to execute batches within the same partition. This involves reading data, splitting it into chunks, compressing them, and uploading them in sizes of 5kb or less.

### Kafka Integration for Status Updates

Kafka is integrated with Cassandra to provide real-time feedback on the write progress:

- Batch Completion Updates: Kafka sends progress updates every time a batch is executed, allowing the system to track loading progress.
- Completion Notification: A final Kafka message signals the completion of the data storage process.

Benefits of Kafka Integration:
- Real-time Visibility: Users can monitor the data load process in real-time.
- Failure Detection: Immediate feedback is provided if a batch operation encounters issues.
- Scalability: Kafka ensures seamless communication across distributed systems.
