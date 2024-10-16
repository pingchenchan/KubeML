from fastapi import FastAPI, WebSocket, HTTPException
from cassandra.cluster import Cluster
from cassandra.query import BatchStatement, SimpleStatement
import requests
import numpy as np
from io import StringIO
import os
import uuid

app = FastAPI()

# Connect to Cassandra during application startup
cassandra_host = os.getenv('CASSANDRA_HOST', 'localhost')

def connect_to_cassandra():
    try:
        # Initialize Cassandra connection
        cluster = Cluster([cassandra_host])
        session = cluster.connect()

        # Create keyspace if it does not exist
        session.execute("""
            CREATE KEYSPACE IF NOT EXISTS my_dataset_keyspace
            WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};
        """)

        # Switch to the specified keyspace
        session.set_keyspace('my_dataset_keyspace')

        print("Connected to Cassandra and set up keyspace.")
        return session
    except Exception as e:
        print(f"Failed to connect to Cassandra: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")

# Call the connection function at startup
session = connect_to_cassandra()

# Health check endpoint
@app.get("/health")
async def health_check():
    try:
        # Optionally add a check to verify Cassandra connectivity
        session.execute("SELECT now() FROM system.local")
        return {"status": "FastAPI is running", "db_status": "Cassandra is connected"}
    except Exception as e:
        print(f"Health check failed: {e}")
        return {"status": "FastAPI is running", "db_status": "Cassandra connection failed"}

# Function to download the NYC housing dataset
def download_data():
    url = 'https://ics.uci.edu/~ihler/classes/cs273/data/nyc_housing.txt'

    try:
        response = requests.get(url)
        response.raise_for_status()  # Check if the request was successful

        datafile = StringIO(response.text)
        data = np.genfromtxt(datafile, delimiter=',', missing_values='', filling_values=np.nan)

        if data is None or data.size == 0:
            raise ValueError("Downloaded dataset is empty or could not be parsed.")

        features, labels = data[:, :-1], data[:, -1]
    except requests.RequestException as req_err:
        print(f"Request error: {req_err}")
        raise HTTPException(status_code=500, detail="Failed to download dataset.")
    except Exception as parse_err:
        print(f"Data parsing error: {parse_err}")
        raise HTTPException(status_code=500, detail="Failed to parse dataset.")

    return features, labels

# Insert NYC housing data, create the table if it does not exist
@app.post("/insert_nyc_housing")
async def insert_nyc_housing():
    # Create table if not exists
    try:
        session.execute("""
            CREATE TABLE IF NOT EXISTS nyc_housing_data (
                row_id UUID PRIMARY KEY,
                features list<float>,
                label float
            );
        """)
    except Exception as e:
        print(f"Failed to create table: {e}")
        raise HTTPException(status_code=500, detail="Failed to create table")

    try:
        # Download the NYC housing dataset
        features, labels = download_data()
    except Exception as e:
        print(f"Failed to download NYC housing data: {e}")
        raise HTTPException(status_code=500, detail="NYC housing data download failed")

    try:
        # Process the data in smaller batches to avoid the "Batch too large" error
        batch_size = 100  # Define your batch size here
        total_rows = len(features)

        for i in range(0, total_rows, batch_size):
            batch = BatchStatement()
            batch_features = features[i:i + batch_size]
            batch_labels = labels[i:i + batch_size]

            for feature, label in zip(batch_features, batch_labels):
                row_id = uuid.uuid4()

                # Check if data with the same features already exists
                existing = session.execute(SimpleStatement("""
                    SELECT row_id FROM nyc_housing_data WHERE features = %s ALLOW FILTERING;
                """, fetch_size=1), (feature.tolist(),))

                if existing.one():
                    print(f"Data already exists, skipping row: {feature.tolist()}")
                    continue

                # Prepare the batch insert statement
                batch.add(session.prepare("""
                    INSERT INTO nyc_housing_data (row_id, features, label)
                    VALUES (?, ?, ?)
                """), (row_id, feature.tolist(), label))

            # Execute the batch
            session.execute(batch)
            print(f"Inserted batch {i//batch_size + 1}/{(total_rows//batch_size) + 1}")
    except Exception as e:
        print(f"Failed to insert NYC housing data: {e}")
        raise HTTPException(status_code=500, detail="NYC housing data insertion failed")

    return {"status": "success"}

# Query NYC housing data for machine learning
@app.get("/get_nyc_housing_data")
async def get_nyc_housing_data():
    try:
        # Query all data points for machine learning
        rows = session.execute("SELECT * FROM nyc_housing_data")

        features = []
        labels = []

        # Convert rows to feature and label arrays
        for row in rows:
            features.append(row.features)
            labels.append(row.label)

        return {"features": features, "labels": labels}

    except Exception as e:
        print(f"Failed to retrieve NYC housing data: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve data")
