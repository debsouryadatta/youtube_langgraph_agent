import os
import requests
from datetime import datetime
from io import BytesIO
import numpy as np
from moviepy.editor import (
    ColorClip, ImageClip, TextClip, CompositeVideoClip, AudioFileClip
)
from PIL import Image
import matplotlib.font_manager as fm

def timestamp_to_seconds(timestamp: str) -> float:
    parts = timestamp.split(":")
    if len(parts) == 2:  # MM:SS format
        minutes, seconds = parts
        return float(minutes) * 60 + float(seconds)
    elif len(parts) == 3:  # HH:MM:SS format
        hours, minutes, seconds = parts
        return float(hours) * 3600 + float(minutes) * 60 + float(seconds)
    else:
        try:
            return float(timestamp)
        except ValueError:
            raise ValueError(f"Invalid timestamp format: {timestamp}")

def get_system_font(bold=False) -> str:
    """Return a suitable system font path for text overlays.
    
    Args:
        bold (bool): Whether to return a bold font variant if available
    """
    # First try to find bold fonts if requested
    if bold:
        bold_font_candidates = [
            'Arial-Bold.ttf',
            'Helvetica-Bold.ttf',
            '/System/Library/Fonts/Helvetica-Bold.ttc',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            '/System/Library/Fonts/SF-Pro-Text-Bold.otf'
        ]
        for font in bold_font_candidates:
            if os.path.exists(font):
                return font
    
    # Regular font alternatives
    font_candidates = [
        'Arial.ttf',
        'Helvetica.ttf',
        '/System/Library/Fonts/Helvetica.ttc',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/System/Library/Fonts/SF-Pro-Text-Regular.otf'
    ]
    
    # Try to find specifically bold fonts in system fonts
    system_fonts = fm.findSystemFonts()
    if bold:
        for font in system_fonts:
            font_lower = font.lower()
            if 'bold' in font_lower and ('arial' in font_lower or 'helvetica' in font_lower or 'sf-pro' in font_lower):
                return font
    
    # Check for exact matches in font candidates
    for font in font_candidates:
        if os.path.exists(font):
            return font
    
    # Fall back to any system font
    if system_fonts:
        return system_fonts[0]
    
    raise ValueError("No suitable font found on the system")

def create_text_background(text, width, fontsize, font_path):
    """Create a semi-transparent background for text with proper padding."""
    # Add line breaks to ensure better text wrapping
    # This is an alternative to using line_spacing parameter
    wrapped_text = text
    
    text_clip = TextClip(
        wrapped_text, 
        fontsize=fontsize, 
        color='white', 
        font=font_path, 
        method='caption',
        align='center',
        size=(width - 80, None)  # Add horizontal padding by reducing width
    )
    
    # Create a background with padding
    padding_v = 40  # Vertical padding (top and bottom)
    padding_h = 40  # Horizontal padding (left and right)
    bg_width = text_clip.w + padding_h * 2
    bg_height = text_clip.h + padding_v * 2
    
    # Create a black background with increased transparency (0.5 instead of 0.7)
    bg_clip = ColorClip(
        size=(bg_width, bg_height), 
        color=(0, 0, 0)
    ).set_opacity(0.5)  # Increased transparency from 0.7 to 0.5
    
    # Position text in the center of background
    text_centered = text_clip.set_position(("center", "center"))
    
    # Combine background and text
    return CompositeVideoClip([bg_clip, text_centered])

def create_video(state):
    print("Creating final video using MoviePy...")
    
    # Validate required keys in state
    if not state.get("audio_path"):
        raise ValueError("audio_path is required in state")
    if not state.get("images_manifest"):
        raise ValueError("images_manifest is required in state")
    if "videoScript" not in state.get("script", {}):
        raise ValueError("script.videoScript is required in state")
    if "totalDuration" not in state["script"]:
        raise ValueError("totalDuration not provided in script")
    
    video_duration = timestamp_to_seconds(state["script"]["totalDuration"])
    width, height = 1080, 1920  # Final video dimensions

    # Create a black background clip
    background = ColorClip(size=(width, height), color=(0, 0, 0), duration=video_duration)
    
    overlays = [background]

    # Calculate extension time for images (25% longer than specified in the manifest)
    extend_factor = 1.25
    
    # Process each image overlay with extended duration
    for img_entry in state["images_manifest"]:
        if not img_entry.get("url") or not img_entry.get("start") or not img_entry.get("duration"):
            raise ValueError(f"Invalid image manifest entry: {img_entry}")
        start_time = timestamp_to_seconds(img_entry["start"])
        original_duration = timestamp_to_seconds(img_entry["duration"])
        
        # Extend duration by the factor but ensure it doesn't exceed video length
        extended_duration = min(original_duration * extend_factor, video_duration - start_time)
        
        response = requests.get(img_entry["url"], stream=True, timeout=10)
        response.raise_for_status()
        image_bytes = response.content
        pil_img = Image.open(BytesIO(image_bytes)).convert("RGB")
        # Resize image to fill the frame
        pil_img = pil_img.resize((width, height))
        np_img = np.array(pil_img)
        
        # Create image clip with no fade in/out and extended duration
        image_clip = ImageClip(np_img).set_start(start_time).set_duration(extended_duration)
        overlays.append(image_clip)

    # Process text overlays
    for seg in state["script"]["videoScript"]:
        if not seg.get("text") or not seg.get("start") or not seg.get("duration"):
            raise ValueError(f"Invalid script segment: {seg}")
        start_time = timestamp_to_seconds(seg["start"])
        duration = timestamp_to_seconds(seg["duration"])
        text = seg["text"]
        
        # Get bold font for text
        font_path = get_system_font(bold=True)
        fontsize = 60  # Larger font size for better readability
        
        # Create text with more transparent background
        text_bg_clip = create_text_background(text, width, fontsize, font_path)
        
        # Position text at the bottom with proper margin
        bottom_margin = 100  # Margin from the bottom in pixels
        text_position = ("center", height - text_bg_clip.h - bottom_margin)
        
        # Add text clip to overlays with no fade in/out effects
        text_with_bg = text_bg_clip.set_position(text_position).set_start(start_time).set_duration(duration)
        overlays.append(text_with_bg)

    # Composite all clips together
    composite = CompositeVideoClip(overlays, size=(width, height))
    
    # Add the audio track
    audio = AudioFileClip(state["audio_path"]).set_duration(video_duration)
    composite = composite.set_audio(audio)
    
    # Write the final video (MoviePy will call ffmpeg internally)
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"shorts_video_{datetime.now().timestamp()}.mp4")
    
    # No fade in/out transitions when writing the video
    composite.write_videofile(
        output_path, 
        fps=24, 
        codec='libx264', 
        audio_codec='aac'
    )
    
    return {"final_video_path": output_path}

if __name__ == "__main__":
    # Example state dictionary similar to previous examples
    state = {
        'topic': 'Short moral of a story',
        'script': {
            'videoScript': [
                {'start': '00:00', 'duration': '00:06', 'text': "Hey! Ever wonder if you're missing something HUGE? I just learned... sometimes the truth... the REAL wisdom... is hiding where you least expect it!"},
                {'start': '00:09', 'duration': '00:05', 'text': 'Wow! Like... are you giving up too easily on something you really want?'},
                {'start': '00:15', 'duration': '00:05', 'text': "Maybe... just maybe... you're more capable than you think! This is incredible!"},
                {'start': '00:20', 'duration': '00:08', 'text': "Don't underestimate yourself! So... what's one thing you're going to try again? Tell me in the comments!"}
            ],
            'totalDuration': '00:28'
        },
        'title': 'Unlock Your Hidden Potential! #Motivation #Shorts',
        'description': "Feeling stuck? The REAL truth is closer than you think! Don't give up! What will YOU try again?",
        'thumbnail_url': 'https://v3.fal.media/files/panda/cLhuvDd5NgGNaZgXZj5n5.jpeg',
        'audio_path': 'output/audio_1740480945.814656.mp3',
        'images_manifest': [
            {
                'start': '00:00',
                'duration': '00:06',
                'text': "Hey! Ever wonder if you're missing something HUGE? I just learned... sometimes the truth... the REAL wisdom... is hiding where you least expect it!",
                'url': 'https://v3.fal.media/files/koala/oxucnLRjA4cGQnBfHuLqW.jpeg'
            },
            {
                'start': '00:09',
                'duration': '00:05',
                'text': 'Wow! Like... are you giving up too easily on something you really want?',
                'url': 'https://v3.fal.media/files/rabbit/EwladKSCZWhXjCyHHfAAW.jpeg'
            },
            {
                'start': '00:15',
                'duration': '00:05',
                'text': "Maybe... just maybe... you're more capable than you think! This is incredible!",
                'url': 'https://v3.fal.media/files/rabbit/l4QvhOX0U48rlObpTKa_t.jpeg'
            },
            {
                'start': '00:20',
                'duration': '00:08',
                'text': "Don't underestimate yourself! So... what's one thing you're going to try again? Tell me in the comments!",
                'url': 'https://v3.fal.media/files/tiger/CNiene9lrK7QXkNoAvJYs.jpeg'
            }
        ]
    }
    
    try:
        result = create_video(state)
        print(f"Video created successfully: {result}")
    except Exception as err:
        print(f"Failed to create video: {err}")