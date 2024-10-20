import gzip
import logging
import pickle
import sys
import uuid
from collections import defaultdict
from cassandra.query import PreparedStatement, TraceUnavailable
from cassandra import ConsistencyLevel
from cassandra.cluster import Session, Cluster, Session
from cassandra.query import PreparedStatement, BatchStatement,  SimpleStatement
from fastapi import HTTPException


from settings import CASSANDRA_HOSTS, CASSANDRA_KEYSPACE, CASSANDRA_CHUNK_SIZE, CASSANDRA_MAX_BATCH_SIZE_BYTES 
from kafka_utils import send_to_kafka


# Call the connection function at startup
def connect_to_cassandra():
    try:
        cluster = Cluster(CASSANDRA_HOSTS,protocol_version=5)
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
            chunk_id int,
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

    # do TRUNCATE dataset_data;
    session.execute("TRUNCATE dataset_data;")

    



def chunk_data(data_bytes, chunk_size= CASSANDRA_CHUNK_SIZE):
   
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

async def store_chunked_data(session: Session, dataset_name: str, data):
    write_stmt, update_stmt = prepare_statements(session)

    partition_id = 0  # make sure all data is stored in the same partition
    data_batch = BatchStatement(consistency_level=ConsistencyLevel.LOCAL_QUORUM)
    chunk_distribution = defaultdict(int)

    data_bytes = pickle.dumps(data)  
    
    
    
    total_chunks = (len(data_bytes) + CASSANDRA_CHUNK_SIZE - 1) // CASSANDRA_CHUNK_SIZE

    current_batch_size_bytes = 0  # 當前批次的大小 (bytes)

    for chunk_index, chunk in chunk_data(data_bytes):
        compressed_chunk = gzip.compress(chunk)
        chunk_size_bytes = sys.getsizeof(compressed_chunk)

        # 如果加入當前 chunk 後的大小會超過上限，先執行當前批次
        if current_batch_size_bytes + chunk_size_bytes > CASSANDRA_MAX_BATCH_SIZE_BYTES:
            result =  session.execute(data_batch, trace=True)
            try:
                trace = result.get_query_trace()
                if trace is not None:
                    for event in trace.events:
                        chunk_distribution[event.source] += 1

            except TraceUnavailable:
                print("Trace information is unavailable.")
            print(f"Stored {current_batch_size_bytes / (1024 * 1024):.2f} MB of data for {dataset_name}.")

            send_to_kafka('load_data', {
                'dataset_name': dataset_name,
                'batch_size_mb': current_batch_size_bytes / (1024 * 1024),
                'status': 'loading',
                'total_chunks': total_chunks,
            })

            # 重置批次
            partition_id += 1  
            data_batch = BatchStatement(consistency_level=ConsistencyLevel.LOCAL_QUORUM)
            current_batch_size_bytes = 0
            

        # 將 chunk 加入 data_batch 並更新批次大小
        data_batch.add(write_stmt, (dataset_name, partition_id, chunk_index, compressed_chunk))
        # chunk_distribution[partition_id] += 1
        current_batch_size_bytes += chunk_size_bytes

    # 處理剩餘的 chunk
    if current_batch_size_bytes > 0:
        session.execute(data_batch)
        result =  session.execute(data_batch, trace=True)
        try:
            trace = result.get_query_trace()
            if trace is not None:
                for event in trace.events:
                    chunk_distribution[event.source] += 1

        except TraceUnavailable:
                print("Trace information is unavailable.")
        print(f"2Stored {current_batch_size_bytes / (1024 * 1024)} MB of data for {dataset_name}.")
        send_to_kafka('load_data', {
                'dataset_name': dataset_name,
                'batch_size_mb': current_batch_size_bytes / (1024 * 1024),
                'status': 'loading',
                'total_chunks': total_chunks,
            })


    # 更新 metadata 表
    metadata_batch = BatchStatement(consistency_level=ConsistencyLevel.LOCAL_QUORUM)
    for pid in range(partition_id + 1):  # 遍歷所有 partition_id 並更新 metadata
        metadata_batch.add(update_stmt, (dataset_name, pid))
    session.execute(metadata_batch)

    send_to_kafka('load_data', {
        'dataset_name': dataset_name,
        'status': 'completed',
        'total_chunks': total_chunks,
        'chunk_distribution': dict(chunk_distribution),
    })

    print(f"All chunks for {dataset_name} stored.")

    
async def write_chunk(session: Session, stmt: PreparedStatement, dataset_name: str, partition_id: int, chunk: bytes, chunk_distribution: dict):
    bound_stmt = stmt.bind((dataset_name, partition_id, uuid.uuid4(), chunk))
    bound_stmt.consistency_level = ConsistencyLevel.LOCAL_QUORUM
    # session.execute(bound_stmt)
    result = session.execute(bound_stmt, trace=True)
    
    # # Retrieve and print trace details
    try:
        trace = result.get_query_trace()
        if trace is not None:
            for event in trace.events:
                chunk_distribution[event.source] += 1

    except TraceUnavailable:
        print("Trace information is unavailable.")

async def update_metadata(session: Session, stmt: PreparedStatement, dataset_name: str, partition_id: int):
    bound_stmt = stmt.bind((dataset_name, partition_id))
    bound_stmt.consistency_level = ConsistencyLevel.LOCAL_QUORUM
    # session.execute(bound_stmt)
    session.execute(bound_stmt)


async def fetch_metadata(session: Session, dataset_name: str):
    """Fetch partition IDs from dataset_metadata for a specific dataset."""
    query = """
        SELECT partition_id 
        FROM dataset_metadata 
        WHERE dataset_name = %s;
    """
    statement = SimpleStatement(query)
    rows = session.execute(statement, (dataset_name,))
    print(f'metadata rows: {rows}, dataset_name: {dataset_name}')    
    partition_ids = [row.partition_id for row in rows]
    print(f'partition_ids: {partition_ids}')
    if not partition_ids:
        raise ValueError(f"No partitions found for dataset: {dataset_name}")

    print(f"Found partitions for {dataset_name}: {partition_ids}")
    return partition_ids


async def fetch_mnist_data(session: Session, dataset_name: str):
    """從 dataset_data 讀取所有 chunk，按順序合併，並進行解壓縮和反序列化"""
    try:

    
        partition_ids = await fetch_metadata(session, dataset_name)
        if not partition_ids:
            raise ValueError(f"No data found for dataset: {dataset_name}")


        all_chunks = []
        chunks_ids = []
        for partition_id in partition_ids:
            query = """
                SELECT chunk_id, chunk
                FROM dataset_data
                WHERE dataset_name = %s AND partition_id = %s
                ORDER BY chunk_id ASC;  
            """
            statement = SimpleStatement(query, fetch_size=1000)
            rows = session.execute(statement, (dataset_name, partition_id))

            
            chunks = [row.chunk for row in rows]
            local_chunks_ids = [row.chunk_id for row in rows]
            if not chunks:
                raise ValueError(f"No chunks found for partition {partition_id}")
            chunks_ids.extend(local_chunks_ids)
            all_chunks.extend(chunks)
            
        print(f"Total chunks ids: {chunks_ids}, total partitions: {partition_ids}")


        compressed_data = b"".join(all_chunks) 
        print(f"Total compressed size: {len(compressed_data)} bytes")

        try:
            decompressed_data = gzip.decompress(compressed_data)  
            data = pickle.loads(decompressed_data) 
        except Exception as e:
            logging.error(f"Failed to decompress or deserialize data: {e}")
            raise

        print(f"Loaded data for {dataset_name}. Data shape: {data.shape}")
        return data

    except Exception as e:
        logging.error(f"Failed to fetch data: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch data")


