import flask
from flask import request
import os
import boto3
from bot import ObjectDetectionBot

app = flask.Flask(__name__)


TELEGRAM_APP_URL = os.environ['TELEGRAM_APP_URL']
S3_BUCKET_NAME = os.environ['BUCKET_NAME']  # Make sure the S3 bucket is set as an environment variable

# Initialize the S3 client
s3_client = boto3.client('s3')
secret_file_path = '/run/secrets/telegram_token'
# Read the token from the secret file
with open(secret_file_path, 'r') as file:
    TELEGRAM_TOKEN = file.read().strip()
# Initialize the ObjectDetectionBot with the necessary parameters
bot = ObjectDetectionBot(TELEGRAM_TOKEN, TELEGRAM_APP_URL, S3_BUCKET_NAME, s3_client)

@app.route('/', methods=['GET'])
def index():
    return 'Ok'

@app.route(f'/{TELEGRAM_TOKEN}/', methods=['POST'])
def webhook():
    req = request.get_json()
    bot.handle_message(req['message'])
    return 'Ok'

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8443)