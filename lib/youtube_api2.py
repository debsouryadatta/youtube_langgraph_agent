# Fetch the latest videos from youtube channels

from googleapiclient.discovery import build
import os
from dotenv import load_dotenv

load_dotenv()

def youtube_authenticate(api_key):
    return build('youtube', 'v3', developerKey=api_key)

def get_latest_videos_from_channel(youtube, channel_id, max_results=3):
    # Search for the latest videos from the given channel
    request = youtube.search().list(
        part="snippet",
        channelId=channel_id,
        order="date",   # Order results by upload date
        type="video",
        maxResults=max_results
    )
    response = request.execute()
    videos = []
    for item in response.get('items', []):
        video_id = item['id']['videoId']
        video_title = item['snippet']['title']
        videos.append({
            'title': video_title,
            'video_id': video_id,
            'url': f"https://www.youtube.com/watch?v={video_id}"
        })
    return videos

def get_latest_videos_from_channels(youtube, channel_ids, max_results_per_channel=3):
    channel_videos = {}
    for channel_id in channel_ids:
        # Retrieve and store the latest videos for each channel
        channel_videos[channel_id] = get_latest_videos_from_channel(youtube, channel_id, max_results_per_channel)
    return channel_videos

# Example usage
api_key = os.getenv('YOUTUBE_API_KEY')
youtube = youtube_authenticate(api_key)

# Array of famous YouTube channel IDs for testing:
channels = [
    "UCMwVTLZIRRUyyVrkjDpn4pA",  # Cole Medin
    "UC0BHO4AbCeBpghWNifMbH5Q",   # Leonardo Grigorio | The AI Forge
    "UCsBjURrPoezykLs9EqgamOA"    # Fireship
]

latest_videos = get_latest_videos_from_channels(youtube, channels, max_results_per_channel=3)

# Print the latest videos from each channel
for channel, videos in latest_videos.items():
    print(f"Channel ID: {channel}")
    for video in videos:
        print(f"Title: {video['title']}")
        print(f"URL: {video['url']}")
    print("=" * 40)
