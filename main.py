#!/usr/bin/env python3

from flask import Flask, render_template, send_file
import requests
import time
import io
import subprocess
import cv2
import os
import threading
import uuid
from urllib.parse import unquote
import logging
from pathlib import Path
import shutil
import random
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

capture_time = "Never captured"
encode_time = "Never encoded"
upload_time = "Never uploaded"

video_counter = 1  # Track the video counter


def capture_images(num_images, interval):
    global video_counter
    start_time = time.time()  # Start timing the video creation process
    # Create a VideoCapture object to access the camera
    # Use 0 to access the default camera, or change to the appropriate camera index if you have multiple cameras
    cap = cv2.VideoCapture(0)

    # Check if the camera is opened correctly
    if not cap.isOpened():
        print("Failed to open the camera.")
        return

    # Create the "tmp_images" folder if it doesn't exist
    folder_path = "tmp_images"
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    # Calculate the total number of images to capture
    for i in range(num_images):
        # Read a frame from the camera
        ret, frame = cap.read()

        if not ret:
            print("Failed to capture frame from the camera.")
            break

        # Save the frame as an image
        image_path = os.path.join(
            folder_path, f"{video_counter}_image_{i + 1}.jpg")
        cv2.imwrite(image_path, frame)

        # print(f"Photo {i + 1}/{num_images}")

        # Wait for the specified interval
        time.sleep(interval)

    # Release the VideoCapture object
    cap.release()
    end_time = time.time()  # Stop timing the video creation process
    video_creation_duration = end_time - start_time
    global capture_time
    capture_time = f"{video_creation_duration:.2f} seconds"
    # print(f"Capture duration: {video_creation_duration:.2f} seconds")


def create_video():
    # Run ffmpeg command to create an mp4 from the captured images
    global video_counter
    start_time = time.time()  # Start timing the transcoding process
    title = f"videos/1_{str(uuid.uuid4())}_{video_counter}.mp4"
    # -threads 8
    command = f"./ffmpeg -y -r 1 -pattern_type glob -i 'tmp_images/{video_counter}_image_*.jpg' -c:v libx264 -preset superfast " + title
    subprocess.run(command, shell=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)

    video_counter += 1
    end_time = time.time()  # Stop timing the transcoding process
    transcoding_duration = end_time - start_time
    # print(f"Transcoding duration: {transcoding_duration:.2f} seconds")

    global encode_time
    encode_time = f"{transcoding_duration:.2f} seconds"
    return os.path.abspath(title)


def delete_files():
    for filename in Path(".").glob("tmp_images/*.jpg"):
        os.remove(filename)


def copy_images(num_images):

    global video_counter
    start_time = time.time()  # Start timing the video creation process

    # Create the "tmp_images" folder if it doesn't exist
    folder_path = "tmp_images"
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    # Calculate the total number of images to capture
    for i in range(num_images):
        # Read a frame from the camera
        file_name = f"sample_{str(random.randint(1, 35)).zfill(4)}.jpeg"

        # Copy the random image file to the destination folder
        source_path = os.path.join("sample_video", file_name)
        destination_path = os.path.join(
            folder_path, f"{video_counter}_image_{i + 1}.jpg")
        shutil.copyfile(source_path, destination_path)

    # Release the VideoCapture object

    end_time = time.time()  # Stop timing the video creation process
    video_creation_duration = end_time - start_time
    global capture_time
    capture_time = f"{video_creation_duration:.2f} seconds"
    # print(f"Capture duration: {video_creation_duration:.2f} seconds")


app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/scan')
def scan():

    capture_images(num_images=30, interval=.01)

    path = create_video()

    delete_files()

    threading.Thread(target=upload_video, args=([path])).start()

    return send_file(path, mimetype='video/mp4')


@app.route('/scan_demo')
def scan_demo():

    copy_images(num_images=30)

    path = create_video()

    delete_files()

    threading.Thread(target=upload_video, args=([path])).start()

    return send_file(path, mimetype='video/mp4')


@app.route('/stats')
def stats():
    global capture_time
    global encode_time
    global upload_time
    return {
        "capture": capture_time,
        "encode": encode_time,
        "upload": upload_time,
    }


def upload_video(path):

    upload_endpoint = f"https://l10ah500d2.execute-api.us-east-1.amazonaws.com/Demo/infer"
    start_time = time.time()  # Start timing the upload process
    with open(path, 'rb') as video_file:
        headers = {"filename": path.split('/')[-1]}  # Create the header
        response = requests.post(upload_endpoint, data=video_file, headers=headers)
        if response.status_code == 200:
            # print("Video uploaded successfully")
            pass
        else:
            print("Failed to upload video")
    end_time = time.time()  # Stop timing the upload process
    upload_duration = end_time - start_time

    global upload_time
    upload_time = f"{upload_duration:.2f} seconds"
    # print(f"Upload duration: {upload_duration:.2f} seconds")


if __name__ == '__main__':

    folder_path = "videos"
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    # delete old videos
    for filename in Path(".").glob("videos/*.mp4"):
        os.remove(filename)
    # Start the Flask server
    subprocess.Popen(
        '''sleep 2 && osascript <<EOF
        tell application "Safari"
            activate
            delay 1
            tell application "System Events"
                keystroke "n" using {command down, shift down}
            end tell
            delay 1
            set URL of front document to "http://127.0.0.1:5000"
        end tell
        EOF''',
        shell=True
    )
    app.run(debug=False)
