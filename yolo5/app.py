import time
from pathlib import Path
from flask import Flask, request, jsonify  # Import jsonify for proper JSON responses
from detect import run
import uuid
import yaml
from loguru import logger
import os
import boto3
from pymongo import MongoClient

yolo_endpoint = "http://yolov5:8081/predict"
images_bucket = os.environ['BUCKET_NAME']
mongo_uri = os.environ['MONGO_URI']  # MongoDB connection URI
db_name = os.environ.get('MONGO_DB', 'default_db')  # Default to 'default_db' if no environment variable is set
collection_name = os.environ.get('MONGO_COLLECTION', 'predictions')  # Default collection name
#
s3_client = boto3.client('s3')
mongo_client = MongoClient(mongo_uri)
db = mongo_client[db_name]
collection = db[collection_name]

with open("data/coco128.yaml", "r") as stream:
    names = yaml.safe_load(stream)['names']

app = Flask(__name__)


@app.route('/predict', methods=['POST'])
def predict():
    prediction_id = str(uuid.uuid4())
    logger.info(f'prediction: {prediction_id}. start processing')

    img_name = request.json.get('imgName')  # Changed to get from JSON body instead of query args
    logger.info(f'Received imgName: {img_name}')  # Log received imgName
    if not img_name:
        return jsonify({"error": "Missing imgName parameter"}), 400  # Return 400 if imgName is missing

    original_img_path = f'static/data/{prediction_id}/{img_name}'
    os.makedirs(os.path.dirname(original_img_path), exist_ok=True)

    try:
        # Download image from S3
        s3_client.download_file(images_bucket, img_name, original_img_path)
        logger.info(f'prediction: {prediction_id}/{original_img_path}. Download img completed')
    except Exception as e:
        logger.error(f"Error downloading file from S3: {e}")
        return jsonify({"error": "Failed to download image from S3"}), 500

    run(
        weights='yolov5s.pt',
        data='data/coco128.yaml',
        source=original_img_path,
        project='static/data',
        name=prediction_id,
        save_txt=True
    )

    pred_dir = f'static/data/{prediction_id}2'
    pred_summary_path = Path(f'{pred_dir}/labels/{img_name.split(".")[0]}.txt')
    # Check if directory exists
    if os.path.exists(os.path.dirname(pred_summary_path)):
        logger.info(f'Files in directory: {os.listdir(os.path.dirname(pred_summary_path))}')
    else:
        logger.error(f'Directory does not exist: {os.path.dirname(pred_summary_path)}')
    logger.info(f'YOLOv5 finished. Checking directory: {os.path.dirname(pred_summary_path)}')
    logger.info(f'Files in directory: {os.listdir(os.path.dirname(pred_summary_path))}')

    label_dir = f"static/data/{prediction_id}2/labels"
    os.makedirs(label_dir, exist_ok=True)

    predicted_img_path = Path(f'{pred_dir}/{img_name}')
    predicted_s3_key = f'predictions/{prediction_id}/{img_name}'
    s3_client.upload_file(str(predicted_img_path), images_bucket, predicted_s3_key)

    logger.info(f"Looking for label file at: {pred_summary_path}")
    if pred_summary_path.exists():
        with open(pred_summary_path) as f:
            labels = f.read().splitlines()
            labels = [line.split(' ') for line in labels]
            labels = [{
                'class': names[int(l[0])],
                'cx': float(l[1]),
                'cy': float(l[2]),
                'width': float(l[3]),
                'height': float(l[4]),
            } for l in labels]

        logger.info(f'prediction: {prediction_id}/{original_img_path}. prediction summary:\n\n{labels}')

        # Format the response as needed
        prediction_summary = {
            '_id': str(uuid.uuid4()),  # Unique prediction ID
            'labels': labels,
            'image_paths': {
                'original': original_img_path,
                'predicted': predicted_s3_key
            },
            'prediction_id': prediction_id,
            'time': time.time()
        }

        # Insert summary into MongoDB
        collection.insert_one(prediction_summary)

        json_serializable_summary = {
            **prediction_summary,
            '_id': str(prediction_summary['_id']),  # Convert ObjectId to string
            'time': float(prediction_summary['time'])
        }

        return jsonify({
            'predictions': labels,
            'prediction_id': prediction_id,
            'original_img_path': original_img_path,
            'predicted_img_path': predicted_s3_key
        })
    else:
        logger.error(f'Label file not found at {pred_summary_path}')
        return jsonify({
            'error': 'Prediction result not found',
            'prediction_id': prediction_id,
            'original_img_path': original_img_path
        }), 404


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8081)
