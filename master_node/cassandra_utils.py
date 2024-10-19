import gzip
import pickle
import uuid
import asyncio
from collections import defaultdict
from cassandra.cluster import Cluster, Session
from cassandra.query import PreparedStatement, TraceUnavailable
from cassandra import ConsistencyLevel
from cassandra.cluster import Session, Cluster
from cassandra.query import PreparedStatement
from cassandra import ConsistencyLevel
from settings import CASSANDRA_HOSTS, CASSANDRA_KEYSPACE, CHUNK_SIZE



# Call the connection function at startup
def connect_to_cassandra():
    try:
        cluster = Cluster(CASSANDRA_HOSTS)
        session = cluster.connect()

        # Create keyspace if it does not exist (using parameterized query)
        query = f"""
            CREATE KEYSPACE IF NOT EXISTS {CASSANDRA_KEYSPACE}
            WITH replication = {{'class': 'SimpleStrategy', 'replication_factor': 1}};
        """
        session.execute(query)

        # Switch to the specified keyspace
        session.set_keyspace(CASSANDRA_KEYSPACE)
        print(f"Connected to Cassandra keyspace: {CASSANDRA_KEYSPACE}")
        return session

    except Exception as e:
        raise Exception(f"Failed to connect to Cassandra: {e}")

    
def setup_dataset_table(session: Session):
    session.execute("""
        CREATE TABLE IF NOT EXISTS dataset_data (
            dataset_name text,
            partition_id int,
            chunk_id uuid,
            chunk blob,
            PRIMARY KEY ((dataset_name, partition_id), chunk_id)
        );
    """)
    
    session.execute("""
        CREATE TABLE IF NOT EXISTS dataset_metadata (
            dataset_name text,
            partition_id int,
            PRIMARY KEY (dataset_name, partition_id)
        );
    """)



def chunk_data(data, chunk_size=CHUNK_SIZE):
    data_bytes = pickle.dumps(data)
    total_size = len(data_bytes)
    num_chunks = (total_size + chunk_size - 1) // chunk_size

    for i in range(num_chunks):
        yield i, data_bytes[i * chunk_size:(i + 1) * chunk_size]


def prepare_statements(session: Session):
    write_stmt = session.prepare("""
        INSERT INTO dataset_data (dataset_name, partition_id, chunk_id, chunk)
        VALUES (?, ?, ?, ?);
    """)
    update_stmt = session.prepare("""
        INSERT INTO dataset_metadata (dataset_name, partition_id)
        VALUES (?, ?)
        IF NOT EXISTS;
    """)
    return write_stmt, update_stmt
chunk_distribution = defaultdict(int) 
async def store_chunked_data(session: Session, dataset_name: str, data):
    write_stmt, update_stmt = prepare_statements(session)

    tasks = []
    for partition_id, chunk in chunk_data(data):
        compressed_chunk = gzip.compress(chunk)

        tasks.append(write_chunk(session, write_stmt, dataset_name, partition_id, compressed_chunk))
        tasks.append(update_metadata(session, update_stmt, dataset_name, partition_id))

    await asyncio.gather(*tasks)
    print(f"All chunks for {dataset_name} stored.")

async def write_chunk(session: Session, stmt: PreparedStatement, dataset_name: str, partition_id: int, chunk: bytes):
    bound_stmt = stmt.bind((dataset_name, partition_id, uuid.uuid4(), chunk))
    bound_stmt.consistency_level = ConsistencyLevel.LOCAL_QUORUM
    session.execute(bound_stmt)
    # result = session.execute(bound_stmt, trace=True)

    # # Retrieve and print trace details
    # try:
    #     trace = result.get_query_trace()
    #     if trace is not None:
    #         # print(f"Trace details for storing chunk in partition {partition_id} for {dataset_name}:")
    #         for event in trace.events:
    #             chunk_distribution[event.source] += 1
    #     for node, count in chunk_distribution.items():
    #         print(f"Node {node}: {count} chunks")
    # except TraceUnavailable:
    #     print("Trace information is unavailable.")

async def update_metadata(session: Session, stmt: PreparedStatement, dataset_name: str, partition_id: int):
    bound_stmt = stmt.bind((dataset_name, partition_id))
    bound_stmt.consistency_level = ConsistencyLevel.LOCAL_QUORUM
    # session.execute(bound_stmt)
    session.execute(bound_stmt)


