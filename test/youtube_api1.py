# Fetch the top viewed youtube videos on search query

from googleapiclient.discovery import build
import os
from dotenv import load_dotenv

load_dotenv()

def youtube_authenticate(api_key):
    return build('youtube', 'v3', developerKey=api_key)

def get_most_viewed_videos(youtube, search_term, max_results=10):
    # Search for videos using the provided search term
    search_request = youtube.search().list(
        part="snippet",
        q=search_term,  # Use your search term here
        type="video",
        order="viewCount",  # Orders by view count
        maxResults=max_results
    )

    search_response = search_request.execute()

    videos = []
    for item in search_response['items']:
        video_id = item['id']['videoId']
        
        # Get detailed video statistics
        video_response = youtube.videos().list(
            part="snippet,statistics",
            id=video_id
        ).execute()
        
        # Select the first (and usually only) result from the list
        video_info = video_response['items'][0]
        print(f"Whole video info: {video_info} \n \n \n")
        videos.append({
            'title': video_info['snippet']['title'],
            'views': video_info['statistics']['viewCount'],
            'url': f"https://youtube.com/watch?v={video_id}"
        })

    return videos

api_key = os.getenv('YOUTUBE_API_KEY')
youtube = youtube_authenticate(api_key)

search_term = "Cursor tutorial"
most_viewed = get_most_viewed_videos(youtube, search_term)

for video in most_viewed:
    print(f"Title: {video['title']}")
    print(f"Views: {video['views']}")
    print(f"URL: {video['url']}\n")
