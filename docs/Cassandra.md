# Cassandra Database Setup

## Nodes and Network Topology

The system consists of two Cassandra nodes.
All nodes run using Docker containers and communicate through an internal bridge network.

## Data Center and Rack

This setup disables multi-data center support, using a single data center (dc1) to reduce unnecessary management overhead.
By default, each node belongs to the same rack (rack1), ensuring simplified data synchronization.

## Seed Nodes

When the Cassandra cluster starts, nodes identify cluster members through seed nodes.
We designate two nodes as seed nodes (cassandra-node1 and cassandra-node2) to ensure at least one available node for stable startup.


## Performance and Scalability Considerations

### Replication Factor

Set to 2 to ensure high availability of data. In the event of a single node failure, the other node can still provide read and write services.

### Consistency Level (LOCAL_QUORUM)

Ensures that at least the majority of nodes agree on data read or write operations, balancing data consistency and read performance.
Suitable for applications running within a single data center, ensuring minimized read and write latency.