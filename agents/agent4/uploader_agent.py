import httplib2
import os
import random
import time
import argparse

from apiclient.discovery import build
from apiclient.errors import HttpError
from apiclient.http import MediaFileUpload
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import run_flow

# Define Constants
httplib2.RETRIES = 1
MAX_RETRIES = 10
RETRIABLE_EXCEPTIONS = (httplib2.HttpLib2Error, IOError)
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]

CLIENT_SECRETS_FILE = "secrets/yt-uploader.json"
YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

VALID_PRIVACY_STATUSES = ("public", "private", "unlisted")

def get_authenticated_service():
    # Create an argparse object for compatibility with oauth2client
    parser = argparse.ArgumentParser(description='YouTube Uploader')
    parser.add_argument('--auth_host_name', default='localhost', help='Authorization server host name')
    parser.add_argument('--auth_host_port', default=[8080, 8090], type=int, nargs='*', help='Authorization server host port')
    parser.add_argument('--logging_level', default='ERROR', help='Logging level')
    args, _ = parser.parse_known_args()
    
    flow = flow_from_clientsecrets(CLIENT_SECRETS_FILE, scope=YOUTUBE_UPLOAD_SCOPE)
    storage = Storage("secrets/yt-uploader-oauth2.json")
    credentials = storage.get()

    if credentials is None or credentials.invalid:
        credentials = run_flow(flow, storage, args)

    return build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, http=credentials.authorize(httplib2.Http()))

def initialize_upload(youtube, options):
    tags = None
    if options.get('keywords'):
        tags = options['keywords'].split(",")

    body = dict(
        snippet=dict(
            title=options['title'],
            description=options['description'],
            tags=tags,
            categoryId=options.get('category', '22')  # Default to 'People & Blogs' category
        ),
        status=dict(
            privacyStatus=options.get('privacyStatus', 'unlisted')
        )
    )

    insert_request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=MediaFileUpload(options['file'], chunksize=-1, resumable=True)
    )

    return resumable_upload(insert_request)

def resumable_upload(insert_request):
    response = None
    retry = 0
    video_id = None

    while response is None:
        try:
            print("Uploading file...")
            status, response = insert_request.next_chunk()

            if response is not None and 'id' in response:
                video_id = response['id']
                print(f"Video id '{video_id}' was successfully uploaded.")
                return video_id
        except HttpError as e:
            if e.resp.status in RETRIABLE_STATUS_CODES:
                error = f"A retriable HTTP error {e.resp.status} occurred: {e.content}"
                print(error)
            else:
                raise
        except RETRIABLE_EXCEPTIONS as e:
            error = f"A retriable error occurred: {e}"
            print(error)

        if retry > MAX_RETRIES:
            print("No longer attempting to retry.")
            return None

        retry += 1
        max_sleep = 2 ** retry
        sleep_seconds = random.random() * max_sleep
        print(f"Sleeping {sleep_seconds} seconds and then retrying...")
        time.sleep(sleep_seconds)

def upload_to_youtube(state):
    """
    Uploads the final video to YouTube and returns the video ID.
    """
    print("Starting YouTube upload process...")
    
    # Check if the video file exists
    if not os.path.exists(state['final_video_path']):
        print(f"Error: Video file not found at {state['final_video_path']}")
        return {"video_id": None}
    
    try:
        # Set up the YouTube upload options
        options = {
            'file': state['final_video_path'],
            'title': state['title'],
            'description': state['description'],
            'category': '24',  # Entertainment
            # 'keywords': '',
            'privacyStatus': 'unlisted'  # Default to unlisted for safety
        }
        
        # Get authenticated service
        youtube = get_authenticated_service()
        
        # Initialize and perform the upload
        video_id = initialize_upload(youtube, options)
        
        if video_id:
            print(f"Video successfully uploaded with ID: {video_id}")
            return {"video_id": video_id}
        else:
            print("Failed to upload video")
            return {"video_id": None}
            
    except Exception as e:
        print(f"Error uploading video to YouTube: {str(e)}")
        return {"video_id": None}