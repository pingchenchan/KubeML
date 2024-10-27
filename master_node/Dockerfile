# Use a slim Python image
FROM python:3.9-slim

# Install curl (for health checks) and clean up
RUN apt-get update && apt-get install -y curl && apt-get clean

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port for the FastAPI app
EXPOSE 5000

# Run the FastAPI application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5000", "--reload"]
