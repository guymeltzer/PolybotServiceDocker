# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory to /app
WORKDIR /app

# Copy the requirements.txt file to the container
COPY requirements.txt /app/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r /app/requirements.txt

# Install AWS CLI
RUN apt-get update && apt-get install -y \
    unzip \
    curl \
    && curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" \
    && unzip awscliv2.zip \
    && ./aws/install \
    && rm -rf awscliv2.zip

# Copy the current directory contents into the container at /app
COPY . /app

# Expose port 8443
EXPOSE 8443

# Define environment variables for your bot service
ENV TELEGRAM_TOKEN=${TELEGRAM_TOKEN}
ENV TELEGRAM_APP_URL=${TELEGRAM_APP_URL}
ENV BUCKET_NAME=${BUCKET_NAME}
ENV AWS_ACCESS_KEY=${AWS_ACCESS_KEY}
ENV AWS_SECRET_KEY=${AWS_SECRET_KEY}

# Run app.py when the container launches
CMD ["python", "app.py"]
