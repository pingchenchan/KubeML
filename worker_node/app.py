import os
from fastapi import FastAPI, HTTPException
import numpy as np
from tensorflow.keras.datasets import mnist
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, Conv2D, MaxPooling2D, Flatten, LSTM
from tensorflow.keras.utils import to_categorical
from tensorflow.keras.optimizers import Adam

app = FastAPI()

# Download and preprocess MNIST dataset
def load_mnist_data():
    (X_train, y_train), (X_test, y_test) = mnist.load_data()

    # Normalize the data
    X_train = X_train.astype('float32') / 255
    X_test = X_test.astype('float32') / 255

    # Reshape for models like CNN that need 3D input
    X_train_cnn = X_train.reshape(-1, 28, 28, 1)
    X_test_cnn = X_test.reshape(-1, 28, 28, 1)

    # Reshape for RNN (LSTM) input: (samples, time steps, features)
    X_train_rnn = X_train.reshape(-1, 28, 28)
    X_test_rnn = X_test.reshape(-1, 28, 28)

    # One-hot encode the labels for classification
    y_train_one_hot = to_categorical(y_train, 10)
    y_test_one_hot = to_categorical(y_test, 10)

    return (X_train, y_train_one_hot, X_test, y_test_one_hot, X_train_cnn, X_test_cnn, X_train_rnn, X_test_rnn, y_train, y_test)

# Multilayer Perceptron (MLP) model
def build_mlp_model(input_shape):
    model = Sequential()
    model.add(LSTM(128, return_sequences=False, input_shape=input_shape))  # Set return_sequences=False for classification
    model.add(Dropout(0.2))
    model.add(Dense(128, activation='relu'))
    model.add(Dropout(0.2))
    model.add(Dense(10, activation='softmax'))
    model.compile(optimizer=Adam(), loss='categorical_crossentropy', metrics=['accuracy'])
    return model

# Convolutional Neural Network (CNN) model
def build_cnn_model(input_shape):
    model = Sequential()
    model.add(Conv2D(32, kernel_size=(3, 3), activation='relu', input_shape=input_shape))
    model.add(MaxPooling2D(pool_size=(2, 2)))
    model.add(Conv2D(64, kernel_size=(3, 3), activation='relu'))
    model.add(MaxPooling2D(pool_size=(2, 2)))
    model.add(Flatten())
    model.add(Dense(128, activation='relu'))
    model.add(Dropout(0.5))
    model.add(Dense(10, activation='softmax'))
    model.compile(optimizer=Adam(), loss='categorical_crossentropy', metrics=['accuracy'])
    return model

# Recurrent Neural Network (RNN) model using LSTM
# def build_rnn_model(input_shape):
#     model = Sequential()
#     model.add(LSTM(128, input_shape=input_shape, return_sequences=False))  # Ensure LSTM does not return sequences
#     model.add(Dropout(0.2))
#     model.add(Dense(128, activation='relu'))
#     model.add(Dropout(0.2))
#     model.add(Dense(10, activation='softmax'))
#     model.compile(optimizer=Adam(), loss='categorical_crossentropy', metrics=['accuracy'])
#     return model

# API endpoint to trigger the MNIST data processing and prediction
@app.post("/process_mnist")
async def process_mnist():
    try:
        # Load MNIST data
        X_train, y_train_one_hot, X_test, y_test_one_hot, X_train_cnn, X_test_cnn, X_train_rnn, X_test_rnn, y_train, y_test = load_mnist_data()

        # Train and evaluate the MLP model
        mlp_model = build_mlp_model((X_train.shape[1],))  # Pass a tuple
        mlp_model.fit(X_train, y_train_one_hot, epochs=5, batch_size=128, verbose=1)
        mlp_loss, mlp_accuracy = mlp_model.evaluate(X_test, y_test_one_hot)

        # Train and evaluate the CNN model
        cnn_model = build_cnn_model(X_train_cnn.shape[1:])  # This is already a tuple
        cnn_model.fit(X_train_cnn, y_train_one_hot, epochs=5, batch_size=128, verbose=1)
        cnn_loss, cnn_accuracy = cnn_model.evaluate(X_test_cnn, y_test_one_hot)

        # Train and evaluate the RNN model
        # rnn_model = build_rnn_model((28, 28,))  # Pass a tuple
        # rnn_model.fit(X_train_rnn, y_train_one_hot, epochs=5, batch_size=128, verbose=1)
        # rnn_loss, rnn_accuracy = rnn_model.evaluate(X_test_rnn, y_test_one_hot)
        return {
            "MLP": {
                "accuracy": mlp_accuracy,
                "loss": mlp_loss,
            },
            "CNN": {
                "accuracy": cnn_accuracy,
                "loss": cnn_loss,
            },
            # "RNN": {
            #     "accuracy": rnn_accuracy,
            #     "loss": rnn_loss,
            # },
        }

    except Exception as e:
        print(f"Failed to process MNIST data: {e}")
        raise HTTPException(status_code=500, detail="Failed to process data")

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "Worker node is running!"}


# import os
# from fastapi import FastAPI, HTTPException
# from cassandra.cluster import Cluster
# import numpy as np
# from sklearn.neighbors import NearestCentroid
# from sklearn.metrics import zero_one_loss, confusion_matrix, ConfusionMatrixDisplay
# from sklearn import svm
# from sklearn.ensemble import RandomForestClassifier
# from sklearn.linear_model import LogisticRegression
# from sklearn.model_selection import train_test_split
# from tensorflow.keras.models import Sequential
# from tensorflow.keras.layers import Dense, Dropout
# from tensorflow.keras.utils import to_categorical
# from tensorflow.keras.optimizers import Adam
# app = FastAPI()
# cassandra_host = os.getenv('CASSANDRA_HOST', 'localhost')

# # Connect to Cassandra
# def connect_to_cassandra():
#     try:
#         cluster = Cluster([cassandra_host]) # Replace with your Cassandra host
#         session = cluster.connect('my_dataset_keyspace')  # Replace with your keyspace
#         return session
#     except Exception as e:
#         print(f"Failed to connect to Cassandra: {e}")
#         raise HTTPException(status_code=500, detail="Database connection failed")

# # Function to read data from Cassandra
# def fetch_data_from_cassandra(session):
#     rows = session.execute("SELECT features, label FROM nyc_housing_data")
#     features = []
#     labels = []
#     for row in rows:
#         features.append(row.features)
#         labels.append(row.label)
#     return np.array(features), np.array(labels)

# # Define the evaluation and statistics function for traditional ML models
# def eval_model(model, X_train, X_test, y_train, y_test):
#     # Fit the model
#     model.fit(X_train, y_train)

#     # Make predictions on the test set
#     y_pred = model.predict(X_test)

#     # Calculate error rate
#     error_rate = zero_one_loss(y_test, y_pred)

#     # Calculate confusion matrix
#     cm = confusion_matrix(y_test, y_pred)

#     # Optionally, plot confusion matrix
#     ConfusionMatrixDisplay(confusion_matrix=cm).plot()

#     return error_rate, cm

# # Define the deep learning model
# def build_deep_learning_model(input_shape, num_classes):
#     model = Sequential()
#     model.add(Dense(256, activation='relu', input_shape=(input_shape,)))
#     model.add(Dropout(0.3))
#     model.add(Dense(128, activation='relu'))
#     model.add(Dropout(0.3))
#     model.add(Dense(64, activation='relu'))
#     model.add(Dense(num_classes, activation='softmax'))
#     optimizer = Adam(learning_rate=0.001)
#     model.compile(optimizer=optimizer, loss='categorical_crossentropy', metrics=['accuracy'])
#     return model

# # Function to evaluate deep learning model
# def eval_deep_learning_model(X_train, X_test, y_train, y_test):
#     num_classes = len(np.unique(y_train))  # Number of unique classes (e.g., 2 if binary classification)
    
#     # Convert labels to one-hot encoding for deep learning
#     y_train_one_hot = to_categorical(y_train, num_classes)
#     y_test_one_hot = to_categorical(y_test, num_classes)

#     # Build the deep learning model
#     model = build_deep_learning_model(X_train.shape[1], num_classes)

#     # Train the model
#     model.fit(X_train, y_train_one_hot, epochs=1000, batch_size=32, verbose=1)

#     # Evaluate the model
#     loss, accuracy = model.evaluate(X_test, y_test_one_hot)

#     # Make predictions
#     y_pred = model.predict(X_test)
#     y_pred_classes = np.argmax(y_pred, axis=1)

#     # Calculate confusion matrix
#     cm = confusion_matrix(y_test, y_pred_classes)

#     return accuracy, cm

# # API endpoint to trigger the data processing and prediction
# @app.post("/process_nyc_housing")
# async def process_nyc_housing():
#     try:
#         session = connect_to_cassandra()
#         # Fetch data from Cassandra
#         X, y = fetch_data_from_cassandra(session)

#         if len(X) == 0 or len(y) == 0:
#             raise HTTPException(status_code=400, detail="No data found")

#         # Split data into training and test sets (80% training, 20% test)
#         X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

#         # Nearest Centroid
#         nc_model = NearestCentroid()
#         nc_err, nc_cm = eval_model(nc_model, X_train, X_test, y_train, y_test)

#         # SVM
#         svm_model = svm.SVC()
#         svm_err, svm_cm = eval_model(svm_model, X_train, X_test, y_train, y_test)

#         # Random Forest
#         rf_model = RandomForestClassifier()
#         rf_err, rf_cm = eval_model(rf_model, X_train, X_test, y_train, y_test)

#         # Logistic Regression
#         lr_model = LogisticRegression()
#         lr_err, lr_cm = eval_model(lr_model, X_train, X_test, y_train, y_test)

#         # Deep Learning Model (Neural Network)
#         dl_accuracy, dl_cm = eval_deep_learning_model(X_train, X_test, y_train, y_test)

#         return {
#             "Nearest Centroid": {
#                 "error_rate": nc_err,
#                 "confusion_matrix": nc_cm.tolist(),
#             },
#             "SVM": {
#                 "error_rate": svm_err,
#                 "confusion_matrix": svm_cm.tolist(),
#             },
#             "Random Forest": {
#                 "error_rate": rf_err,
#                 "confusion_matrix": rf_cm.tolist(),
#             },
#             "Logistic Regression": {
#                 "error_rate": lr_err,
#                 "confusion_matrix": lr_cm.tolist(),
#             },
#             "Deep Learning": {
#                 "accuracy": dl_accuracy,
#                 "confusion_matrix": dl_cm.tolist(),
#             },
#         }

#     except Exception as e:
#         print(f"Failed to process NYC housing data: {e}")
#         raise HTTPException(status_code=500, detail="Failed to process data")

# # Health check endpoint
# @app.get("/health")
# async def health_check():
#     return {"status": "Worker node is running!"}
