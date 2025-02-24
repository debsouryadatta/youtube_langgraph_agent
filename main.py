# youtube_ai.py
import os
import json
import requests
from datetime import datetime
from typing import TypedDict, List, Annotated
from dotenv import load_dotenv
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph
from elevenlabs.client import ElevenLabs
from elevenlabs import play, VoiceSettings
import fal_client as fal
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.VideoClip import ImageClip, TextClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy import vfx
import base64
from PIL import ImageFont
import matplotlib.font_manager as fm

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
    client = ElevenLabs(
        api_key=os.getenv("ELEVENLABS_API_KEY"),
    )
    
    full_text = " ".join([seg["text"] for seg in state["script"]["videoScript"]])
    response = client.text_to_speech.convert_with_timestamps(
        text=full_text,
        voice_id="cgSgspJ2msm6clMCkdW9",  # Adam voice
        model_id="eleven_turbo_v2_5",  # Turbo model for low latency
        output_format="mp3_44100_128",
        voice_settings=VoiceSettings(
            stability=0.0,
            similarity_boost=1.0,
            style=0.0,
            use_speaker_boost=True,
        ),
    )
    # print("Audio generated:", response)
    
    formatted_transcript = format_transcript(response)
    print("Formatted transcript:", formatted_transcript)
    
    audio_path = f"output/audio_{datetime.now().timestamp()}.mp3"
    
    # Save audio from base64
    audio_base64 = response["audio_base64"]
    if audio_base64:
        audio_bytes = base64.b64decode(audio_base64)
        with open(audio_path, "wb") as f:
            f.write(audio_bytes)
    else:
        print("No audio_base64 found in response.")
        # Write the streaming response to file
        with open(audio_path, "wb") as f:
            for chunk in response:
                if chunk:
                    f.write(chunk)
    
    print(f"{audio_path}: Audio file saved successfully!")
    return {"audio_path": audio_path, "script": formatted_transcript}

def generate_images(state: AgentState):
    print("Generating images...")
    
    # Create prompt template for combining segments
    combine_prompt = ChatPromptTemplate.from_template(
        """Given the following video script segments, combine them into fewer segments suitable for generating a single image for each segment. 
Keep all the original text but group them logically while preserving proper timing.
Each output segment’s duration must be at least 5 seconds and no more than 6 seconds.
If there are many short, similar segments, group them together; if there are longer segments, split them into parts so that each segment fits within the 5-6 second range.
Original segments: {segments}

Format the response exactly as:
{{
    "videoScript": [
        {{
            "start": "MM:SS",
            "duration": "MM:SS",
            "text": "Combined text for this segment"
        }},
        ...
    ],
    "totalDuration": "MM:SS"
}}
"""
    )
    
    # Create chain for combining segments
    combine_chain = combine_prompt | llm | parser
    
    # Get optimized script with combined segments
    result = combine_chain.invoke({"segments": state["script"]["videoScript"]})
    
    images_manifest = []
    for segment in result["videoScript"]:
        image_result = fal.run(
            "fal-ai/fast-sdxl",
            arguments={
                "prompt": f"""Video scene for YouTube Shorts: {segment['text']}
                Style requirements:
                - Vertical cinematic composition
                - Professional lighting with dramatic contrast
                - Vibrant, eye-catching colors
                - Clean, uncluttered background
                - Modern and trendy aesthetic
                - Emotionally engaging visuals""",
                "negative_prompt": "text, watermark, blurry, low quality, distorted, amateur, poorly lit, busy background",
                "image_size": {"width": 1080, "height": 1920}
            }
        )
        
        images_manifest.append({
            "start": segment["start"],
            "duration": segment["duration"],
            "text": segment["text"],
            "url": image_result["images"][0]["url"]
        })
        print(f"Generated image for combined segment starting at {segment['start']}")
    
    print("Images manifest:", images_manifest, "Modified Script:", result)
    return {"images_manifest": images_manifest, "script": result}

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
    print("Creating final video...")
    clips = []
    temp_image_files = []
    
    # Get system font path
    try:
        font_path = get_system_font()
        print(f"Using font: {font_path}")
    except Exception as e:
        print(f"Warning: Font selection failed: {e}")
        raise ValueError("Could not find a suitable system font")
    
    if not state.get("audio_path"):
        raise ValueError("audio_path is required in state")
    if not state.get("images_manifest"):
        raise ValueError("images_manifest is required in state")
    if not state.get("script", {}).get("videoScript"):
        raise ValueError("script.videoScript is required in state")
    
    try:
        # Download assets
        audio = AudioFileClip(state["audio_path"])
        
        # Download and save images temporarily
        for img in state["images_manifest"]:
            if not img.get("url") or not img.get("start") or not img.get("duration"):
                raise ValueError(f"Invalid image manifest entry: {img}")
                
            response = requests.get(img["url"], stream=True, timeout=10)
            response.raise_for_status()
            
            # Create a temporary file with .jpg extension
            temp_file = f"output/temp_img_{len(temp_image_files)}.jpg"
            temp_image_files.append(temp_file)
            
            # Save the image data
            with open(temp_file, "wb") as f:
                f.write(response.content)
            
            try:
                # Convert timestamp strings to seconds
                start_time = timestamp_to_seconds(img["start"])
                duration = timestamp_to_seconds(img["duration"])
                
                # Create clip from saved image
                clip = (ImageClip(temp_file)
                       .resized((1080, 1920))
                       .with_start(start_time)
                       .with_duration(duration))
                clips.append(clip)
            except Exception as e:
                raise ValueError(f"Failed to create clip from image {img['url']}: {str(e)}")
        
        if not clips:
            raise ValueError("No valid clips were created from the images")
            
        # Fix crossfading between image clips
        if len(clips) > 1:
            final_clips = []
            for i in range(len(clips)):
                current_clip = clips[i]
                effects = []
                if i > 0:  # Add fade in for all clips except first
                    effects.append(vfx.FadeIn(0.5))
                if i < len(clips) - 1:  # Add fade out for all clips except last
                    effects.append(vfx.FadeOut(0.5))
                if effects:
                    current_clip = current_clip.with_effects(effects)
                final_clips.append(current_clip)
            clips = final_clips
        
        # Create text overlays
        text_clips = []
        for seg in state["script"]["videoScript"]:
            if not seg.get("text") or not seg.get("start") or not seg.get("duration"):
                raise ValueError(f"Invalid script segment: {seg}")
                
            try:
                start_time = timestamp_to_seconds(seg["start"])
                duration = timestamp_to_seconds(seg["duration"])
                
                # Create text clip with position included in initialization
                text_clip = TextClip(
                    text=seg["text"],
                    font=font_path,
                    font_size=40,
                    color='white',
                    size=(1080, 1920),
                    method='caption',
                ).with_position(('bottom')).with_duration(duration)

                # text_clip = text_clip.with_position(('center', 'bottom'))
                
                # Only apply timing
                text_clip = text_clip.with_start(start_time).with_duration(duration)
                
                text_clips.append(text_clip)
            except Exception as e:
                raise ValueError(f"Failed to create text clip for segment: {seg['text']}: {str(e)}")
        
        if not text_clips:
            raise ValueError("No valid text clips were created")
            
        # Fix video composition with audio
        try:
            all_clips = clips + text_clips
            
            # Create composite and properly set audio
            video = CompositeVideoClip(all_clips, size=(1080, 1920))
            
            # Ensure video duration matches audio
            video = video.with_duration(audio.duration)
            
            # Create final video with audio
            final_video = video.with_audio(audio)
            
            output_path = f"output/video_output_{datetime.now().timestamp()}.mp4"
            
            # Write with explicit audio parameters
            final_video.write_videofile(
                output_path,
                fps=24,
                codec="libx264",
                audio_codec="aac",
                audio=True,  # Ensure audio is included
                threads=4,
                preset='medium'
            )
            
            return {"final_video_path": output_path}
            
        except Exception as e:
            raise ValueError(f"Failed to compose final video: {str(e)}")
            
    finally:
        # Clean up temporary files
        for temp_file in temp_image_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                print(f"Warning: Failed to remove temporary file {temp_file}: {e}")
                
        # Clean up MoviePy clips
        try:
            if 'final_video' in locals():
                final_video.close()
            if 'video' in locals():
                video.close()
            audio.close()
            for clip in clips:
                clip.close()
            for clip in text_clips:
                clip.close()
        except Exception as e:
            print(f"Warning: Failed to clean up some MoviePy clips: {e}")

# 4. Build Workflow
workflow = StateGraph(AgentState)

workflow.add_node("research_transcript", research_and_generate_transcript)
workflow.add_node("title_description", generate_title_description)
workflow.add_node("generate_thumbnail", generate_thumbnail)
workflow.add_node("generate_audio", generate_audio)
workflow.add_node("generate_images", generate_images)
workflow.add_node("create_video", create_video)

workflow.set_entry_point("research_transcript")
workflow.add_edge("research_transcript", "title_description")
workflow.add_edge("title_description", "generate_thumbnail")
workflow.add_edge("generate_thumbnail", "generate_audio")
workflow.add_edge("generate_audio", "generate_images")
workflow.add_edge("generate_images", "create_video")
workflow.add_edge("create_video", END)

app = workflow.compile()

# 5. Execution
if __name__ == "__main__":
    result = app.invoke({
        # "topic": "Top 3 AI Tools for Content Creation"
        "topic": "Short moral of a story"
    })
    print(f"Final video created at: {result['final_video_path']}")
