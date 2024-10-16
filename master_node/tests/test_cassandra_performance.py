import unittest
import time
import uuid
import numpy as np
from cassandra.cluster import Cluster
from cassandra.query import BatchStatement

class TestCassandraPerformance(unittest.TestCase):

    def setUp(self):
        # Connect to Cassandra
        self.cluster = Cluster(['localhost'])  # replace with your Cassandra host
        self.session = self.cluster.connect('my_dataset_keyspace')  # replace with your keyspace

    def tearDown(self):
        # Clean up inserted test data
        self.session.execute("DELETE FROM nyc_housing_data WHERE row_id IN (%s)" % ','.join(str(row_id) for row_id in self.inserted_ids))

        # Close the connection
        self.cluster.shutdown()

    def test_insert_and_query_performance(self):
        # Generate some random data
        features = np.random.rand(10000, 10)  # 10000 data points, each with 10 features
        labels = np.random.rand(10000)
        self.inserted_ids = []

        # Batch insert the data
        start_time = time.time()
        batch = BatchStatement()
        for feature, label in zip(features, labels):
            row_id = uuid.uuid4()
            self.inserted_ids.append(row_id)
            batch.add(self.session.prepare("""
                INSERT INTO nyc_housing_data (row_id, features, label)
                VALUES (?, ?, ?)
            """), (row_id, feature.tolist(), label))
            
            # Execute the batch in chunks
            if len(batch) >= 100:  # Batch size of 100
                self.session.execute(batch)
                batch.clear()

        # Execute remaining batch
        if len(batch) > 0:
            self.session.execute(batch)

        insert_time = time.time() - start_time

        # Query the data
        start_time = time.time()
        rows = self.session.execute("SELECT * FROM nyc_housing_data LIMIT 10000")
        query_time = time.time() - start_time

        # Check the performance
        self.assertLess(insert_time, 10, f"Inserting 10000 rows took too long: {insert_time:.2f} seconds")
        self.assertLess(query_time, 5, f"Querying 10000 rows took too long: {query_time:.2f} seconds")

if __name__ == '__main__':
    unittest.main()
