import telebot # Import telebot library
from loguru import logger # Import loguru for structured logging.
import os  # Import os module to interact with the OS
import time  # Import time module for timing
import requests  # Import requests library to make HTTP requests
from telebot.types import InputFile # Import InputFile for sending files using telebot
import boto3 # Import boto3 to interact with AWS.

class ObjectDetectionBot:  # Define the bot class
    def __init__(self, token, telegram_chat_url, s3_bucket_name, s3_client):
        self.telegram_bot_client = telebot.TeleBot(token)  # Initialize the telegram bot client
        self.s3_bucket_name = s3_bucket_name # Set S3 bucket name
        self.s3_client = s3_client # Initialize s3 client

        self.s3_client = boto3.client('s3', region_name='eu-north-1') # Create S3 client with region

        # Get the NGROK URL from environment variables
        ngrok_url = os.getenv('TELEGRAM_APP_URL') # Load NGROK url from env.

        if not ngrok_url: # Check if NGROK url is loaded.
            raise ValueError("NGROK URL (TELEGRAM_APP_URL) is missing in the .env file")  # Raise exception if not set

        # Remove any existing webhooks and set a new webhook URL
        self.telegram_bot_client.remove_webhook()  # Remove any existing webhook in telegram.
        time.sleep(0.5) # Sleep to give time for telegram to delete previous webhook
        self.telegram_bot_client.set_webhook(url=f'{ngrok_url}/{token}/', timeout=60)  # Set webhook for this bot instance.

        logger.info(f'Telegram Bot information\n\n{self.telegram_bot_client.get_me()}')  # Log bot info

    def send_text(self, chat_id, text):
        self.telegram_bot_client.send_message(chat_id, text) # Send a text message to specified chat id.

    def send_text_with_quote(self, chat_id, text, quoted_msg_id):
        self.telegram_bot_client.send_message(chat_id, text, reply_to_message_id=quoted_msg_id)  # Send a message to chat, quoting a specific message ID

    def is_current_msg_photo(self, msg):
        return 'photo' in msg # Check if message contains a photo

    def download_user_photo(self, msg):
        """Downloads the photos that are sent to the Bot to the local file system."""
        if not self.is_current_msg_photo(msg):  # Check that message contains a photo
            raise RuntimeError(f'Message content of type "photo" expected')  # Raise runtime error if message is not a photo.

        file_info = self.telegram_bot_client.get_file(msg['photo'][-1]['file_id']) # Get file information from telegram bot
        data = self.telegram_bot_client.download_file(file_info.file_path) # download file
        folder_name = 'photos' # Local folder to store downloaded photos.

        if not os.path.exists(folder_name): # Check if the folder exists
            os.makedirs(folder_name) # If folder does not exist, create it.

        file_path = os.path.join(folder_name, file_info.file_path.split('/')[-1]) # Generate a local file path.
        with open(file_path, 'wb') as photo: # open file in write binary mode
            photo.write(data) # Write data to the file

        return file_path # return file_path

    def send_photo(self, chat_id, img_path):
        if not os.path.exists(img_path): # Check if image path exists
            raise RuntimeError("Image path doesn't exist") # Raise error if it doesn't exist

        self.telegram_bot_client.send_photo(chat_id, InputFile(img_path)) # Send photo to chat.

    def upload_to_s3(self, file_path):
        """Uploads the downloaded image to S3."""
        s3_key = os.path.basename(file_path)  # Use the image filename as the S3 key.
        self.s3_client.upload_file(file_path, self.s3_bucket_name, s3_key) # upload to s3
        s3_url = f'https://{self.s3_bucket_name}.s3.amazonaws.com/{s3_key}' # generate the url
        return s3_url # return url

    def get_yolo5_results(self, img_name):
        """Sends an HTTP request to the yolo5 service and returns the predictions."""
        try:  # Begin try block to catch errors.
            # Log the image name being sent to YOLOv5
            logger.info(f'Sending imgName to YOLOv5 service: {img_name}')  # Log the imgname
            # Send the HTTP request to the YOLOv5 service
            logger.debug(f'Preparing to send POST request to http://yolov5:8081/predict with payload: {{"imgName": "{img_name}"}}') # Log debug message
            response = requests.post(  # Make post request to yolo5 service
                "http://yolov5:8081/predict",
                json={"imgName": img_name}  # Send imgName as part of the request payload
            )
            # Log the HTTP response status code
            logger.debug(f'Response status code from YOLOv5 service: {response.status_code}')  # Log http status code
            # Ensure the response is successful
            response.raise_for_status()  # Raise an exception if the status code was not OK.
            # Log the successful response data
            logger.info(f'Received response from YOLOv5 service: {response.json()}')  # Log the JSON response
            return response.json()  # Return the JSON response from YOLOv5

        except requests.exceptions.RequestException as e:  # Catch any requests errors
            logger.error(f"Error contacting YOLOv5 microservice: {e}") # Log the error message
            logger.debug(f'Error details: {e.__class__} - {str(e)}')  # log debug message
            return None  # Return None in case of errors.

    def handle_message(self, msg):
        """Main message handler for the bot."""
        logger.info(f'Incoming message: {msg}')  # Log the message object
        chat_id = msg['chat']['id']  # Get the chat ID from message

        if self.is_current_msg_photo(msg):  # Check if message is a photo
            try:  # Begin try block to catch errors.
                # Step 1: Download the user's photo
                logger.info('Step 1: Downloading user photo')  # Log step 1 message.
                photo_path = self.download_user_photo(msg)  # Download the photo
                logger.info(f'Photo downloaded to: {photo_path}')  # Log the downloaded photo path

                # Step 2: Upload the image to S3
                logger.info('Step 2: Uploading photo to S3')  # Log step 2 message.
                image_url = self.upload_to_s3(photo_path)  # Upload to s3.
                logger.info(f'Photo uploaded to S3: {image_url}')  # Log s3 path.
                self.send_text(chat_id, "Image uploaded to S3. Processing...")  # Inform user that processing has began.

                # Step 3: Get the image filename (imgName) to pass to YOLOv5
                img_name = os.path.basename(photo_path)  # Get the file name from the path.
                logger.info(f'Image name for YOLOv5: {img_name}')  # log image name for debugging.

                # Step 4: Send the image to the YOLOv5 service
                logger.info('Step 4: Sending image to YOLOv5 service')  # Log step 4 message
                yolo_results = self.get_yolo5_results(img_name)  # send image to yolo.
                logger.info(f'YOLOv5 results: {yolo_results}')  # Log results from YOLOv5.

                if yolo_results:  # Check if results were returned
                    # Step 5: Send the prediction results back to the user
                    logger.info('Step 5: Sending prediction results to user')  # Log step 5 message
                    if 'predictions' in yolo_results and yolo_results[
                        'predictions']:  # Check if predictions were found.
                        detected_objects = [label['class'] for label in
                                            yolo_results['predictions']]  # Extract all objects in the result.
                        if detected_objects:  # Check if objects were detected.
                            results_text = f"Detected objects: {', '.join(detected_objects)}"  # Generate result string.
                        else:
                            results_text = "No objects detected."  # Set message to no objects detected if no labels were detected
                        self.send_text(chat_id, results_text)  # Send results to user.
                    else:
                        logger.error('YOLOv5 service returned no predictions')  # Log the error
                        self.send_text(chat_id, "There was an error processing the image.")
                else:  # If Yolo return a non expected result
                    logger.error('YOLOv5 service returned no results or incorrect response format')  # Log the error
                    self.send_text(chat_id, "There was an error processing the image.")

            except Exception as e:  # Catch any unhandled errors.
                logger.error(f"Error processing image: {e}")  # Log the error message
                self.send_text(chat_id, "There was an error processing the image.")  # Send error message to user.
        else:  # If message does not contain a photo.
            logger.info('Message does not contain a photo')  # Log that the user did not send photo.
            self.send_text(chat_id, "Please send a photo with a valid caption.")  # Ask the user to send a photo.