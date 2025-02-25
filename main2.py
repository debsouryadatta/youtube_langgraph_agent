# youtube_ai.py
import os
import json
import requests
from datetime import datetime
from typing import TypedDict, List, Annotated
from dotenv import load_dotenv
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langgraph.graph import END, StateGraph
from google.cloud import texttospeech
from elevenlabs.client import ElevenLabs
from elevenlabs import play, VoiceSettings
import fal_client as fal
from moviepy.editor import *
import base64
from PIL import ImageFont
import matplotlib.font_manager as fm
from bs4 import BeautifulSoup
import re
import requests

from lib.audio_stt import process_transcription
from lib.test_video import create_video_file

load_dotenv()

# 1. Define State Schema
class AgentState(TypedDict):
    topic: str
    script: dict
    title: str
    description: str
    thumbnail_url: str
    audio_path: str
    images_manifest: List[dict]
    final_video_path: str

# 2. Initialize Tools and Models
tavily = TavilySearchResults(max_results=3)
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    api_key=os.getenv("GEMINI_API_KEY"),
)
# llm = ChatGroq(
#     model="deepseek-r1-distill-qwen-32b",
#     api_key=os.getenv("GROQ_API_KEY"),
# )
parser = JsonOutputParser()

# 3. Define Agents
def research_and_generate_transcript(state: AgentState):
    print("Researching and generating transcript...")
    topic = state["topic"]
    
    # Web research
    tavily_results = tavily.invoke({"query": topic})
    
    # Generate script
    script_prompt = ChatPromptTemplate.from_template(
        """Create a compelling 30-second YouTube Shorts script about {topic} using this research:
        {research}
        
        Follow these guidelines strictly:
        1. Hook (0-5s): Start with an attention-grabbing opening line
        2. Core Content (5-25s): Present key information in short, impactful sentences
        3. Call-to-Action (25-30s): End with an engaging prompt
        
        Each segment MUST:
        - Be written in a conversational, natural speaking style
        - Use interjections like "Hey!", "Wow!", "You won't believe this!"
        - Include emotional emphasis ("This is incredible!", "I'm so excited to share...")
        - Add natural pauses with "..." for dramatic effect
        - Use rhetorical questions to engage viewers
        - Avoid any formatting symbols or special characters
        - Sound authentic and human-like
        - The text key in the json response should only contain the text 

        Format JSON exactly(The output response should be exactly like this):
        {{
            "videoScript": [
                {{
                    "start": "00:00",
                    "duration": "00:02",
                    "text": "Hey guys! You won't believe what I discovered..."
                }},
                ...
            ],
            "totalDuration": "00:30"
        }}"""
    )
    chain = script_prompt | llm | parser
    script = chain.invoke({
        "topic": topic,
        "research": f"Research: {tavily_results}"
    })
    print("Script generated:", script)
    return {"script": script}

def generate_title_description(state: AgentState):
    print("Generating title and description...")
    prompt = ChatPromptTemplate.from_template(
        """Generate compelling YouTube Shorts metadata for this script:
        {script}
        
        Follow these guidelines:
        1. Title must:
           - Start with a powerful action word or number
           - Include trending keywords
           - Create curiosity or urgency
           - Be optimized for YouTube search
           - Stay under 60 characters
        
        2. Description must:
           - Start with a hook
           - Include relevant hashtags
           - Use strategic emojis
           - Add a clear call-to-action
           - Stay under 200 characters
        
        Return JSON with(The output response should be exactly like this):
        {{
            "title": "Catchy title under 60 chars",
            "description": "Engaging description with emojis (200 chars)"
        }}"""
    )
    chain = prompt | llm | parser
    metadata = chain.invoke({"script": state["script"]})
    print("Metadata generated:", metadata)
    return {"title": metadata["title"], "description": metadata["description"]}

def generate_thumbnail(state: AgentState):
    print("Generating thumbnail...")
    prompt_text = f"""Create a visually striking YouTube Shorts thumbnail for '{state["title"]}'.
    {state["description"]}
    
    Style requirements:
    - Vertical format optimized for mobile
    - High contrast and vibrant colors
    - Cinematic lighting with dramatic shadows
    - Modern, trending aesthetic
    - Clean composition with clear focal point
    - Professional quality finish"""
    
    result = fal.run(
        "fal-ai/fast-sdxl",
        arguments={
            "prompt": prompt_text,
            "negative_prompt": "text, watermark, blurry, low quality, distorted, amateur, poorly lit",
            "image_size": {"width": 1080, "height": 1920}
        }
    )
    return {"thumbnail_url": result["images"][0]["url"]}

def format_transcript(response):
    def format_time(seconds):
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"
    
    video_script = []
    current_text = ""
    segment_start = 0
    chars = response["normalized_alignment"]["characters"]
    start_times = response["normalized_alignment"]["character_start_times_seconds"]
    end_times = response["normalized_alignment"]["character_end_times_seconds"]
    
    for i in range(len(chars)):
        current_text += chars[i]
        if i + 1 < len(chars) and start_times[i + 1] - start_times[i] > 0.5:
            duration = end_times[i] - segment_start
            video_script.append({
                "start": format_time(segment_start),
                "duration": format_time(duration),
                "text": current_text.strip()
            })
            segment_start = start_times[i + 1]
            current_text = ""
    
    # Add the last segment
    if current_text:
        duration = end_times[-1] - segment_start
        video_script.append({
            "start": format_time(segment_start),
            "duration": format_time(duration),
            "text": current_text.strip()
        })
    
    total_duration = end_times[-1]
    return {"videoScript": video_script, "totalDuration": format_time(total_duration)}

def generate_audio(state: AgentState):
    print("Generating audio...")
    
    # Set the path to your service account key file
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "gcp_key.json"
    
    # Initialize the client
    client = texttospeech.TextToSpeechClient()
    
    # Combine all text segments
    full_text = " ".join([seg["text"] for seg in state["script"]["videoScript"]])
    
    # Set the text input
    synthesis_input = texttospeech.SynthesisInput(text=full_text)
    
    # Configure voice parameters
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
        name="en-US-Chirp-HD-F"
    )
    
    # Set audio configuration
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )
    
    # Generate speech
    response = client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config
    )
    
    audio_path = f"output/audio_{datetime.now().timestamp()}.mp3"
    
    # Save the audio file
    with open(audio_path, "wb") as out:
        out.write(response.audio_content)
        print(f"Audio content written to file: {audio_path}")
    
    # Get audio duration
    with AudioFileClip(audio_path) as audio:
        duration = audio.duration
    
    # formatted_transcript = {
    #     "videoScript": [
    #         {
    #             "start": "00:00",
    #             "duration": f"{int(duration // 60):02d}:{int(duration % 60):02d}",
    #             "text": full_text
    #         }
    #     ],
    #     "totalDuration": f"{int(duration // 60):02d}:{int(duration % 60):02d}"
    # }
    formatted_transcript = process_transcription(audio_path=audio_path)
    
    return {"audio_path": audio_path, "script": formatted_transcript}

def generate_images(state: AgentState):
    print("Generating images...")
    
    # Process script segments programmatically instead of using LLM
    original_segments = state["script"]["videoScript"]
    total_duration_str = state["script"]["totalDuration"]
    
    # Convert the total duration to seconds
    total_duration_seconds = timestamp_to_seconds(total_duration_str)
    
    # Combine all text from original segments
    all_text = " ".join([segment["text"] for segment in original_segments])
    
    # Calculate how many 4-second segments we need
    segment_duration = 4  # seconds
    num_segments = max(1, int(total_duration_seconds / segment_duration))
    
    # Calculate characters per segment based on total text length divided by number of segments
    chars_per_segment = max(1, len(all_text) // num_segments)
    
    # Create new segments
    new_segments = []
    start_time = 0
    
    for i in range(num_segments):
        # For the last segment, use all remaining text
        if i == num_segments - 1:
            segment_text = all_text[i * chars_per_segment:]
            segment_duration = total_duration_seconds - start_time
        else:
            segment_text = all_text[i * chars_per_segment:(i + 1) * chars_per_segment]
            segment_duration = 4  # fixed 4 seconds per segment
        
        # Format times as MM:SS
        start_str = f"{int(start_time // 60):02d}:{int(start_time % 60):02d}"
        duration_str = f"{int(segment_duration // 60):02d}:{int(segment_duration % 60):02d}"
        
        new_segments.append({
            "start": start_str,
            "duration": duration_str,
            "text": segment_text.strip()
        })
        
        start_time += segment_duration
    
    # Create result with the same structure as expected from the LLM
    result = {
        "videoScript": new_segments,
        "totalDuration": total_duration_str
    }
    
        # Create Google image search function
    def fetch_image_urls(query, num_images=1):
        # Prepare keywords for URL encoding
        query_for_url = query.replace(" ", "+")
        url = f"https://www.google.com/search?q={query_for_url}&tbm=isch"
        
        # Use a common User-Agent header to mimic a real browser
        headers = {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/103.0.5060.114 Safari/537.36")
        }
        
        # Fetch the search result page
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Request failed with status code {response.status_code}")
            return []
        
        # Parse the page using BeautifulSoup
        soup = BeautifulSoup(response.text, "html.parser")
        image_urls = []
        
        # First approach: look for <img> tags with src containing http
        for img in soup.find_all("img"):
            src = img.get("src")
            if src and src.startswith("http"):
                image_urls.append(src)
            if len(image_urls) >= num_images:
                break

        # Fallback: use regex to extract jpg URLs from the raw HTML if not enough URLs found
        if len(image_urls) < num_images:
            regex_urls = re.findall(r'["\'](https?://[^"\']+?\.jpg)["\']', response.text)
            for url in regex_urls:
                if url not in image_urls:
                    image_urls.append(url)
                if len(image_urls) >= num_images:
                    break
        return image_urls[:num_images]
    
    
    # Ensure output directory exists
    os.makedirs("output/images", exist_ok=True)
    
    # Rest of the function remains the same as before
    search_prompt = ChatPromptTemplate.from_template(
        """Create a short and focused image search query based on this video segment text and the topic of the video.
        The query should directly relate to the core topic being discussed.
        
        Video segment text: {segment_text}
        Video topic: {topic}
        
        Create a search query that:
        1. Uses 3-5 key words
        2. Focuses on the main subject
        3. Describes a clear, relevant visual
        
        Return only the search query text with no additional formatting."""
    )
    
    # Create chain for search term generation
    search_chain = search_prompt | llm | StrOutputParser()
    
    images_manifest = []
    for i, segment in enumerate(state["script"]["videoScript"]):
        # Generate search term for this segment
        search_term = search_chain.invoke({"segment_text": segment['text'], "topic": state["topic"]})
        search_term = search_term.strip() + " vertical high quality"
        print(f"Generated search term: {search_term}")
        
        # Fetch image URLs
        image_urls = fetch_image_urls(search_term)
        
        if not image_urls:
            print(f"No images found for segment {i+1}, trying alternative search...")
            # Try a more generic search if specific one fails
            fallback_search = search_chain.invoke({"segment_text": "professional high quality " + segment['text'][:30]})
            image_urls = fetch_image_urls(fallback_search + " vertical")
        
        if image_urls:
            # Download the image
            image_path = f"output/images/segment_{i+1}.jpg"
            try:
                response = requests.get(image_urls[0], timeout=10)
                response.raise_for_status()
                
                with open(image_path, "wb") as f:
                    f.write(response.content)
                print(f"Downloaded image for segment {i+1} to {image_path}")
                
                images_manifest.append({
                    "start": segment["start"],
                    "duration": segment["duration"],
                    "text": segment["text"],
                    "url": image_path  # Store local path instead of URL
                })
            except Exception as e:
                print(f"Failed to download image for segment {i+1}: {str(e)}")
                # Use a placeholder or fallback image
                images_manifest.append({
                    "start": segment["start"],
                    "duration": segment["duration"],
                    "text": segment["text"],
                    "url": "output/images/placeholder.jpg"  # Default placeholder
                })
        else:
            print(f"No images found for segment {i+1}, using placeholder")
            # Use placeholder
            images_manifest.append({
                "start": segment["start"],
                "duration": segment["duration"],
                "text": segment["text"],
                "url": "output/images/placeholder.jpg"
            })
    
    print("Images manifest:", images_manifest)
    return {"images_manifest": images_manifest}
def timestamp_to_seconds(timestamp: str) -> float:
    """Convert a timestamp string (HH:MM:SS or MM:SS) to seconds."""
    parts = timestamp.split(":")
    if len(parts) == 2:  # MM:SS format
        minutes, seconds = parts
        return float(minutes) * 60 + float(seconds)
    elif len(parts) == 3:  # HH:MM:SS format
        hours, minutes, seconds = parts
        return float(hours) * 3600 + float(minutes) * 60 + float(seconds)
    else:
        try:
            return float(timestamp)  # Try direct conversion if it's already a number
        except ValueError:
            raise ValueError(f"Invalid timestamp format: {timestamp}")

def get_system_font():
    """Get a suitable system font path."""
    # Try common system fonts in order of preference
    font_candidates = [
        'Arial.ttf',
        'Helvetica.ttf',
        '/System/Library/Fonts/Helvetica.ttc',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/System/Library/Fonts/SF-Pro-Text-Regular.otf'
    ]
    
    # Get all system fonts
    system_fonts = fm.findSystemFonts()
    
    # First try the candidates
    for font in font_candidates:
        if os.path.exists(font):
            return font
    
    # If none of the candidates work, use the first available system font
    if system_fonts:
        return system_fonts[0]
    
    raise ValueError("No suitable font found on the system")

def create_video(state: AgentState):
    try:
        result = create_video_file(state)
        print(f"Video created successfully: {result}")
        return {"final_video_path": result["final_video_path"]}
    except Exception as err:
        print(f"Failed to create video: {err}")

# 4. Build Workflow
workflow = StateGraph(AgentState)

workflow.add_node("research_transcript", research_and_generate_transcript)
workflow.add_node("title_description", generate_title_description)
workflow.add_node("generate_audio", generate_audio)
workflow.add_node("generate_images", generate_images)
workflow.add_node("create_video", create_video)

workflow.set_entry_point("research_transcript")
workflow.add_edge("research_transcript", "title_description")
workflow.add_edge("title_description", "generate_audio")
workflow.add_edge("generate_audio", "generate_images")
workflow.add_edge("generate_images", "create_video")
workflow.add_edge("create_video", END)

app = workflow.compile()

# 5. Execution
if __name__ == "__main__":
    result = app.invoke({
        # "topic": "Top 3 AI Tools for Content Creation"
        "topic": "new claude 3.7 sonnet release by anthropic"
    })
    # print(f"Final video created at: {result['final_video_path']}")



# Using: 1. audio with google text to speech, 2. images from google search