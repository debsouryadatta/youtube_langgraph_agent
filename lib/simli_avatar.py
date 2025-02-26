import requests
import base64
import os
from dotenv import load_dotenv
import time

load_dotenv()

def generate_avatar_video(api_key, face_id, audio_file_path, output_file_path):
    # Read the audio file and encode it to Base64
    try:
        with open(audio_file_path, "rb") as audio_file:
            audio_base64 = base64.b64encode(audio_file.read()).decode("utf-8")
    except Exception as e:
        print(f"Error reading audio file: {e}")
        return

    # API endpoint URL
    url = "https://api.simli.ai/audioToVideoStream"

    # Request payload
    payload = {
        "simliAPIKey": api_key,
        "faceId": face_id,
        "audioBase64": audio_base64,
        "audioFormat": "mp3",  # Adjust if your file is in another format like 'wav' or 'mp3'
        "audioSampleRate": 16000,
        "audioChannelCount": 1,
        "videoStartingFrame": 0
    }

    # Make the POST request
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()  # Raise an error for HTTP codes 4xx/5xx
    except requests.exceptions.RequestException as e:
        print(f"Error making API request: {e}")
        return

    # Parse the response
    response_data = response.json()
    mp4_url = response_data.get("mp4_url")
    print("Response data:", response_data, "\n", "MP4 URL:", mp4_url)

    if not mp4_url:
        print("Error: 'mp4_url' not found in the API response.")
        return

    # Download the MP4 video from the URL with a browser-like header
    try:
        # Adding a User-Agent header helps emulate a browser request
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        video_response = requests.get(mp4_url, stream=True, headers=headers)

        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
        with open(output_file_path, "wb") as video_file:
            for chunk in video_response.iter_content(chunk_size=8192):
                video_file.write(chunk)

        print(f"Avatar video saved successfully to: {output_file_path}")
    except Exception as e:
        print(f"Error downloading or saving the video: {e}")

if __name__ == "__main__":
    # Replace these values with your actual credentials and file paths
    SIMLI_API_KEY = os.getenv("SIMLI_API_KEY")
    FACE_ID = "ec6f0534-7b63-4a53-9939-c4bff7fd3c3b"
    AUDIO_FILE_PATH = "output/audio_1740510098.255412.mp3"  # Path to your input audio file
    OUTPUT_FILE_PATH = "output/output_avatar_video.mp4"     # Path to save the output MP4 file

    generate_avatar_video(SIMLI_API_KEY, FACE_ID, AUDIO_FILE_PATH, OUTPUT_FILE_PATH)
