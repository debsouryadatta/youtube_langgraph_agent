# `uv add google-api-python-client oauth2client httplib2 uritemplate WebTest pyOpenSSL`


# 1. Import Libraries:

import httplib2
import os
import random
import sys
import time

from apiclient.discovery import build
from apiclient.errors import HttpError
from apiclient.http import MediaFileUpload
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import argparser, run_flow

# 2. Define Constants:

httplib2.RETRIES = 1
MAX_RETRIES = 10
RETRIABLE_EXCEPTIONS = (httplib2.HttpLib2Error, IOError)
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]

CLIENT_SECRETS_FILE = "secrets/yt-uploader.json"
YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

VALID_PRIVACY_STATUSES = ("public", "private", "unlisted")

# 3. Authentication Function:

def get_authenticated_service(args):
    flow = flow_from_clientsecrets(CLIENT_SECRETS_FILE, scope=YOUTUBE_UPLOAD_SCOPE)
    storage = Storage(f"secrets/yt-uploader-oauth2.json")
    credentials = storage.get()

    if credentials is None or credentials.invalid:
        credentials = run_flow(flow, storage, args)

    return build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, http=credentials.authorize(httplib2.Http()))

# 4. Video Upload Function:

def initialize_upload(youtube, options):
    tags = options.keywords.split(",") if options.keywords else None

    body = dict(
        snippet=dict(
            title=options.title,
            description=options.description,
            tags=tags,
            categoryId=options.category
        ),
        status=dict(
            privacyStatus=options.privacyStatus
        )
    )

    insert_request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=MediaFileUpload(options.file, chunksize=-1, resumable=True)
    )

    resumable_upload(insert_request)

# 5. Resumable Upload Logic:

def resumable_upload(insert_request):
    response = None
    retry = 0

    while response is None:
        try:
            print("Uploading file...")
            status, response = insert_request.next_chunk()

            if response is not None and 'id' in response:
                print(f"Video id '{response['id']}' was successfully uploaded.")
                return
        except HttpError as e:
            if e.resp.status in RETRIABLE_STATUS_CODES:
                error = f"A retriable HTTP error {e.resp.status} occurred: {e.content}"
            else:
                raise
        except RETRIABLE_EXCEPTIONS as e:
            error = f"A retriable error occurred: {e}"

        if retry > MAX_RETRIES:
            sys.exit("No longer attempting to retry.")

        retry += 1
        max_sleep = 2 ** retry
        sleep_seconds = random.random() * max_sleep
        print(f"Sleeping {sleep_seconds} seconds and then retrying...")
        time.sleep(sleep_seconds)

# 6. Main Script Execution:

if __name__ == "__main__":
    argparser.add_argument("--file", required=True, help="Video file to upload")
    argparser.add_argument("--title", help="Video title", default="Test Title")
    argparser.add_argument("--description", help="Video description", default="Test Description")
    argparser.add_argument("--category", default="22", help="Numeric video category")
    argparser.add_argument("--keywords", help="Video keywords, comma separated", default="")
    argparser.add_argument("--privacyStatus", choices=VALID_PRIVACY_STATUSES, default="public", help="Video privacy status.")

    args = argparser.parse_args()

    if not os.path.exists(args.file):
        sys.exit("Please specify a valid file using the --file= parameter.")

    youtube = get_authenticated_service(args)
    initialize_upload(youtube, args)


