#!/usr/bin/env python3

from flask import Flask, render_template, send_file, Response
import requests
import time
import io
import subprocess
import cv2
import os
import threading
from urllib.parse import unquote
import logging
from pathlib import Path
import shutil
import random
import sys
from collections import deque
from PIL import Image
import base64
import uuid
from threading import Thread, Lock
import threading
import pyperclip

log = logging.getLogger('werkzeug')
log.setLevel(logging.FATAL)


UPLOAD_BATCH_SIZE = 20
DEMO_COLLECTION_DELAY = 1
CAPTURE_HISTORY_LENGTH = 3 * UPLOAD_BATCH_SIZE
SCAN_SIZE = 22000
FILE_COLLECTION_HISTORY = 7
FIRST_FILES_TO_KEEP = 5
THREAD_COUNT = 6
DOWNLOAD_TIMEOUT = 26


scan_hash = 0 
video_paths = []
inference_paths = []
paused = True
running = False
capture_speed = "Waiting"
capture_speed_history = deque(maxlen=CAPTURE_HISTORY_LENGTH)
encoding_speed = "Waiting"
encoding_speed_history = deque(maxlen=CAPTURE_HISTORY_LENGTH)
upload_speed = "Waiting"
upload_speed_history = deque(maxlen=CAPTURE_HISTORY_LENGTH)
client_speed = "Waiting"
inference_speed = "Waiting"
inference_speed_history = deque(maxlen=CAPTURE_HISTORY_LENGTH)
pipeline_speed = "Waiting"
images_captured = 0
images_encoded = 0
images_uploaded = 0
images_processed = 0
percent_images_captured = "0%"
percent_images_encoded = "0%"
percent_images_uploaded = "0%"
percent_images_processed = "0%"
captured_images_to_upload = {}
live_scan_table = []
batch_counter = 0
results_table = []
pending_results_tracker = []

capture_lock = Lock()
batch_num_lock = Lock()

def capture_images(num_images, interval):

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
    # print(f"Capture duration: {video_creation_duration:.2f} seconds")


def create_video(batch_num, row, my_hash):
    if my_hash != scan_hash:
        return
    global images_encoded
    global percent_images_encoded
    # Run ffmpeg command to create an mp4 from the captured images
    
    # global captured_images_to_upload
    # if "row" not in captured_images_to_upload:
    #     captured_images_to_upload["row"] = 0
    #     captured_images_to_upload["status"] = "encoding"
    # else:
    #     captured_images_to_upload["next_status"] = "encoding"

    global live_scan_table
    live_scan_table[row]["status"] = "encoding"

    global results_table
    results_table[batch_num]["status"] = "Encoding"

    start_time = time.time()  # Start timing the transcoding process
    title = f"videos/1_{str(uuid.uuid4())}_{batch_num}.mp4"
    command = f"./ffmpeg -y -r 1 -pattern_type glob -i 'tmp_images/{row}_*.jpg' -c:v libx264 -preset superfast -b:v 300k " + title
    subprocess.run(command, shell=True, stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    if my_hash != scan_hash:
        return
    delete_images(row)
    if my_hash != scan_hash:
        return
    end_time = time.time()  # Stop timing the transcoding process

    images_encoded += UPLOAD_BATCH_SIZE
    percent_images_encoded = str(int(100*(images_encoded / SCAN_SIZE))) + "%"
    avg_encoding_duration = ((end_time - start_time) / UPLOAD_BATCH_SIZE) * 1000
    global encoding_speed_history
    global encoding_speed
    encoding_speed_history.append(avg_encoding_duration)
    encoding_speed = round(sum(encoding_speed_history) / len(encoding_speed_history), 1)
    update_client_speed()

    return os.path.abspath(title)

def delete_images(row):
    for filename in Path(".").glob(f"tmp_images/{row}_*.jpg"):
        os.remove(filename)

def clear_files():
    for filename in Path(".").glob(f"tmp_images/*.jpg"):
        os.remove(filename)
    
    for filename in Path(".").glob(f"videos/*.mp4"):
        os.remove(filename)

def copy_images(batch_num, row, my_hash):
    with capture_lock:
        start_time = time.time()  # Start timing the video creation process

        # Create the "tmp_images" folder if it doesn't exist
        folder_path = "tmp_images"
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        # Calculate the total number of images to capture
        global images_captured
        global percent_images_captured
        # global captured_images_to_upload
        # captured_images_to_upload = {"images": []}
        # captured_images_to_upload["row"] = 0
        # captured_images_to_upload["status"] = "add"
        global live_scan_table
        if my_hash != scan_hash:
            return
        live_scan_table[row]["hash"] = uuid.uuid4()
        live_scan_table[row]["status"] = "collecting"
        live_scan_table[row]["images"] = []

        global results_table
        if my_hash != scan_hash:
            return
        results_table.append({
            "batch": "Batch #" + str(batch_num + 1),
            "batch_size": UPLOAD_BATCH_SIZE,
            "status": "Collecting",
        })

        for i in range(UPLOAD_BATCH_SIZE):
            time.sleep(DEMO_COLLECTION_DELAY / 1000)
            if my_hash != scan_hash:
                return
            file_name = f"sample_{str(random.randint(1, 35)).zfill(4)}.jpeg"
            source_path = os.path.join("sample_video", file_name)
            destination_path = os.path.join(folder_path, f"{row}_{i + 1}.jpg")
            if my_hash != scan_hash:
                return
            shutil.copyfile(source_path, destination_path)
            images_captured += 1
            percent_images_captured = str(int(100*(images_captured / SCAN_SIZE))) + "%"
            if my_hash != scan_hash:
                return
            with Image.open(source_path) as image_file:
                image_file.thumbnail((108, 81))  # this keeps the aspect ratio intact
                buf = io.BytesIO()
                image_file.save(buf, format='JPEG')
                byte_im = buf.getvalue()
                encoded_string = base64.b64encode(byte_im)
                if my_hash != scan_hash:
                    return
                live_scan_table[row]["images"].append(encoded_string.decode('utf-8'))
                # captured_images_to_upload["images"].append(encoded_string.decode('utf-8'))

        # Release the VideoCapture object
        end_time = time.time()  # Stop timing the video creation process
        avg_capture_duration = ((end_time - start_time) / UPLOAD_BATCH_SIZE) * 1000
        global capture_speed_history
        global capture_speed
        if my_hash != scan_hash:
            return
        capture_speed_history.append(avg_capture_duration)
        capture_speed = round(sum(capture_speed_history) / len(capture_speed_history), 1)
        update_client_speed()


app = Flask(__name__)

@app.route('/')
@app.route('/<path:path>', methods=['GET'])
def index(path='index.html'):
    fp = os.path.join('/Users/tanabs/Desktop/python_medical_demo/dashboard/dist/', path)  # Replace 'path/to/static/files' with the actual path to your static files
    file_extension = os.path.splitext(fp)[1]
    if file_extension == '.mp4' and os.path.isfile(fp):
        return send_file(fp)

    with open(fp, 'rb') as file:
        content = file.read()

    return Response(content, mimetype='text/html')


def run_result_collector(my_hash):

    global inference_speed_history, inference_speed, pipeline_speed
    while my_hash == scan_hash:
        time.sleep(1)
        for pending_result in pending_results_tracker:
            # print("Checking up on results for batch " + str(pending_result["batch"]))
            pending_result["attempts"] += 1
            # if pending_result["attempts"] > 2:
            #     results_table[pending_result["batch"]]["status"] = "Error"
            #     results_table[pending_result["batch"]]["rbc_count"] = "Error"
            #     results_table[pending_result["batch"]]["inference_location"] = "Error"
            #     pending_results_tracker.remove(pending_result)
            
            result = download_result(pending_result["id"])
            if result["status"] != "success":
                # print(str(pending_result["batch"]) + " errored out")
                results_table[pending_result["batch"]]["status"] = "Error"
                results_table[pending_result["batch"]]["rbc_count"] = "Error"
                results_table[pending_result["batch"]]["inference_location"] = "Error"
                pending_results_tracker.remove(pending_result)
                if inference_speed == "Waiting":
                    inference_speed = "Down"
                    pipeline_speed = "Down"

            else:
                print("Got results for " + str(pending_result["batch"]))
                global images_processed, percent_images_processed
                end_time = time.time()

                output_file = "image.jpg"
                image_data = base64.b64decode(result["data"]["image"])
                image = Image.open(io.BytesIO(image_data))
                path = f"inference/{pending_result['batch']}.jpg"
                image.save(path, 'JPEG')
                results_table[pending_result["batch"]]["inference_location"] = f"inference/{pending_result['batch']}.jpg"

                # Remove old results (aligned with videos)
                inference_paths.append((pending_result['batch'], path))
                if len(inference_paths) > FILE_COLLECTION_HISTORY:
                    oldest_batch_num, oldest_path = inference_paths.pop(0)
                    if oldest_batch_num > FIRST_FILES_TO_KEEP:
                        try:
                            print("Deleting results for " + str(pending_result["batch"]))
                            os.remove(oldest_path)
                            del results_table[oldest_batch_num]["inference_location"]
                        except Exception as e:
                            print(f"Error while deleting the file: {e}")

                results_table[pending_result["batch"]]["status"] = "Success"
                numbers = list(map(float, result["data"]["RBCs per frame"][1:-1].split(',')))
                results_table[pending_result["batch"]]["rbc_count"] = round(sum(numbers) / len(numbers), 1)
                pending_results_tracker.remove(pending_result)
                images_processed += UPLOAD_BATCH_SIZE
                percent_images_processed = f"{int(100 * (images_processed / SCAN_SIZE))}%"
                avg_inference_duration = ((end_time - pending_result["start_time"]) / UPLOAD_BATCH_SIZE) * 1000
                inference_speed_history.append(avg_inference_duration)
                inference_speed = round(sum(inference_speed_history) / len(inference_speed_history), 1)
                update_pipeline_speed()

def run_scan_thread(row, my_hash):
    if my_hash != scan_hash:
        return
    global batch_counter, paused
    batch_num = -1
    while my_hash == scan_hash:
        with batch_num_lock:
            batch_num = batch_counter
            batch_counter += 1
        if my_hash != scan_hash:
            return
        copy_images(batch_num, row, my_hash)
        if my_hash != scan_hash:
            return
        path = create_video(batch_num, row, my_hash)
        if my_hash != scan_hash:
            return
        upload_video(batch_num, row, path, my_hash)
        if my_hash != scan_hash:
            return
        while paused:
            time.sleep(1)
            if my_hash != scan_hash:
                return


@app.route('/api/pauseToggle')
def pauseToggle():
    global paused
    paused = not paused
    return {"paused": paused}

@app.route('/api/start')
def start():
    global capture_speed, capture_speed_history, encoding_speed, encoding_speed_history
    global upload_speed, upload_speed_history, client_speed, inference_speed, inference_speed_history
    global pipeline_speed, images_captured, images_encoded, images_uploaded, images_processed
    global percent_images_captured, percent_images_encoded, percent_images_uploaded, percent_images_processed
    global captured_images_to_upload, live_scan_table, batch_counter, results_table, paused, scan_hash, running, pending_result

    running = True
    paused = False
    
    # global 
    scan_hash = str(uuid.uuid4())

    capture_speed = "Waiting"
    capture_speed_history = deque(maxlen=CAPTURE_HISTORY_LENGTH)
    encoding_speed = "Waiting"
    encoding_speed_history = deque(maxlen=CAPTURE_HISTORY_LENGTH)
    upload_speed = "Waiting"
    upload_speed_history = deque(maxlen=CAPTURE_HISTORY_LENGTH)
    client_speed = "Waiting"
    inference_speed = "Waiting"
    inference_speed_history = deque(maxlen=CAPTURE_HISTORY_LENGTH)
    pipeline_speed = "Waiting"
    images_captured = 0
    images_encoded = 0
    images_uploaded = 0
    images_processed = 0
    percent_images_captured = "0%"
    percent_images_encoded = "0%"
    percent_images_uploaded = "0%"
    percent_images_processed = "0%"

    captured_images_to_upload = {}

    live_scan_table = []

    for i in range(THREAD_COUNT):
        live_scan_table.append({
            "images": [],
            "status": "Waiting"
        })
    
    batch_counter = 0
    results_table = []

    clear_files()
    # threads = []
    thread = threading.Thread(target=run_result_collector, args=([scan_hash]))
    # threads.append(thread)
    thread.start()
    for i in range(THREAD_COUNT):
        thread = threading.Thread(target=run_scan_thread, args=(i,scan_hash))
        # threads.append(thread)
        thread.start()

    return {}


@app.route('/api/heartbeat')
def heartbeat():
    if paused:
        return {"paused": True, "running": running, "threads": THREAD_COUNT,}
    returnObj = {
        "paused": paused,
        "running": running,
        "threads": THREAD_COUNT,
        "capture_speed": {"value": f"{capture_speed} ms" if capture_speed != "Waiting" else "Waiting", "styling": "per_image_stats"},
        "encoding_speed": {"value": f"{encoding_speed} ms" if encoding_speed != "Waiting" else "Waiting", "styling": "per_image_stats"},
        "upload_speed": {"value": f"{upload_speed} ms" if upload_speed != "Waiting" else "Waiting", "styling": "per_image_stats"},
        "client_speed": {"value": f"{client_speed} ms" if client_speed != "Waiting" else "Waiting", "styling": "per_image_stats"},
        "inference_speed": {"value": f"{inference_speed} ms" if inference_speed != "Waiting" and inference_speed != "Down" else "Waiting" if inference_speed == "Waiting" else "Down", "styling": "per_image_stats"},
        "pipeline_speed": {"value": f"{pipeline_speed} ms" if pipeline_speed != "Waiting" and pipeline_speed != "Down" else "Waiting" if pipeline_speed == "Waiting" else "Down", "styling": "per_image_stats"},
        "images_captured": {"value": images_captured, "styling": "none"},
        "images_encoded": {"value": images_encoded, "styling": "none"},
        "images_uploaded": {"value": images_uploaded, "styling": "none"},
        "images_processed": {"value": images_processed, "styling": "none"},
        "percent_images_captured": {"value": percent_images_captured, "styling": "percentage_bar"},
        "percent_images_encoded": {"value": percent_images_encoded, "styling": "percentage_bar"},
        "percent_images_uploaded": {"value": percent_images_uploaded, "styling": "percentage_bar"},
        "percent_images_processed": {"value": percent_images_processed, "styling": "percentage_bar"},
        "live_scan_table": live_scan_table,
        "results_table": results_table,
    }
    return returnObj


def download_result(key):
    download_endpoint = "https://ag1fqnj778.execute-api.us-east-1.amazonaws.com/Demo/get-result"
    headers = {"inferenceId": key}
    try:
        response = requests.get(download_endpoint, headers=headers, timeout=DOWNLOAD_TIMEOUT)
        result = response.json()
        
        if result == "results not found":
            return {
                "status": "error"
            }
        else:
            return {
                "status": "success",
                "data": result
            }
    
    except Exception as e:
        print("EXCEPTION")
        print(e)
        return {
            "status": "problem"
        }

    


def upload_video(batch_num, row, path, my_hash):
    global images_uploaded, percent_images_uploaded, results_table, live_scan_table, video_paths
    if my_hash != scan_hash:
        return
    # add new path to the video_paths list, along with batch_num
    video_paths.append((batch_num, path))

    # if video_paths exceeds FILE_COLLECTION_HISTORY, delete oldest file and update results_table
    if len(video_paths) > FILE_COLLECTION_HISTORY:
        oldest_batch_num, oldest_path = video_paths.pop(0)
        if oldest_batch_num > FIRST_FILES_TO_KEEP:
            try:
                os.remove(oldest_path)
                del results_table[oldest_batch_num]["video_location"]
            except Exception as e:
                print(f"Error while deleting the file: {e}")
    if my_hash != scan_hash:
        return
    results_table[batch_num]["status"] = "Uploading"
    results_table[batch_num]["file_size"] = f"{round(os.path.getsize(path) / (1024 * 1024), 2)} MB"
    results_table[batch_num]["video_location"] = path

    live_scan_table[row]["status"] = "uploading"

    upload_endpoint = "https://l10ah500d2.execute-api.us-east-1.amazonaws.com/Demo/infer"
    start_time = time.time()

    with open(path, 'rb') as video_file:
        headers = {"filename": path.split('/')[-1]}
        try:
            response = requests.post(upload_endpoint, data=video_file, headers=headers, timeout=100)

            if response.status_code == 200:
                if my_hash != scan_hash:
                    return
                end_time = time.time()
                pending_results_tracker.append({
                    "batch": batch_num,
                    "start_time": end_time,
                    "id": response.json()["output_location"],
                    "attempts": 0,
                    "status": "ready"
                })
                results_table[batch_num]["status"] = "Running Inference"
                images_uploaded += UPLOAD_BATCH_SIZE
                percent_images_uploaded = f"{int(100 * (images_uploaded / SCAN_SIZE))}%"
                avg_capture_duration = ((end_time - start_time) / UPLOAD_BATCH_SIZE) * 1000
                global upload_speed_history, upload_speed
                upload_speed_history.append(avg_capture_duration)
                upload_speed = round(sum(upload_speed_history) / len(upload_speed_history), 1)
                update_client_speed()
                live_scan_table[row]["status"] = "done"
                return
            else:
                print(response.json())
        except Exception as e:
            print(e)
    
    pending_results_tracker.append({
        "batch": batch_num,
        "status": "error"
    })
    live_scan_table[row]["status"] = "done"
    results_table[batch_num]["status"] = "Error"

def update_client_speed():
    global client_speed
    if upload_speed != "Waiting" and encoding_speed != "Waiting" and capture_speed != "Waiting":
        client_speed = round(upload_speed + encoding_speed + capture_speed, 1)

def update_pipeline_speed():
    global pipeline_speed
    if pipeline_speed != "Waiting" and inference_speed != "Waiting":
        pipeline_speed = round(pipeline_speed + inference_speed, 1)

if __name__ == '__main__':

    video_folder_path = "videos"
    if not os.path.exists(video_folder_path):
        os.makedirs(video_folder_path)

    inference_folder_path = "inference"
    if not os.path.exists(inference_folder_path):
        os.makedirs(inference_folder_path)

    url = "http://127.0.0.1:5000"
    print("\n######################\n######################\n\n")
    print("Please visit " + url + " – it has been copied to your clipboard")
    print("\n\n\n######################\n######################")
    pyperclip.copy(url)

    # original_stdout = sys.stdout
    # Redirect the output to os.devnull
    sys.stdout = open(os.devnull, 'w')
    app.run(use_reloader=False, use_debugger=False)
