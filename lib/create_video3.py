import os
import numpy as np
from datetime import datetime
from moviepy.editor import (
    VideoFileClip, TextClip, CompositeVideoClip, ColorClip, ImageClip
)
import matplotlib.font_manager as fm
import re
import random

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

def split_text_into_words(text):
    """Split text into words while preserving punctuation."""
    # This pattern keeps punctuation attached to words
    words = re.findall(r'\b[\w\']+\b|[.,!?;:…]', text)
    # Filter out empty strings
    return [word for word in words if word.strip()]

def create_word_highlight_clips(text, width, duration, start_time, fontsize, font_path):
    """Create a sequence of clips with word-by-word highlighting with rectangular background."""
    words = split_text_into_words(text)
    
    # Handle empty text case
    if len(words) == 0:
        return []
    
    speed_factor = 1.1  # Lower value means faster highlighting
    time_per_word = (duration * speed_factor) / len(words)
    
    # Calculate dimensions for our text
    dummy_text_clip = TextClip(
        text, 
        fontsize=fontsize, 
        color='white', 
        font=font_path, 
        method='caption',
        align='center',
        size=(width - 80, None)
    )
    
    # Create a background with padding
    padding_v = 40  # Vertical padding
    padding_h = 40  # Horizontal padding
    bg_width = dummy_text_clip.w + padding_h * 2
    bg_height = dummy_text_clip.h + padding_v * 2
    
    highlight_clips = []
    current_words = []
    
    # Create a series of clips with progressively highlighted words
    for i, word in enumerate(words):
        current_words.append(word)
        
        # Join words with appropriate spacing
        highlighted_text = ""
        original_index = 0
        
        for j, highlighted_word in enumerate(current_words):
            # Find the actual position of this word in the original text
            if j == 0:
                highlighted_index = text.find(highlighted_word, original_index)
                original_index = highlighted_index
            else:
                # For subsequent words, start search from after previous word
                highlighted_index = text.find(highlighted_word, original_index)
                original_index = highlighted_index
            
            # If not the first word and there's space before it in the original text
            if j > 0 and highlighted_index > 0 and text[highlighted_index-1].isspace():
                highlighted_text += " "
            
            highlighted_text += highlighted_word
            original_index += len(highlighted_word)
        
        # First, create a text clip to get its dimensions
        text_clip = TextClip(
            highlighted_text, 
            fontsize=fontsize, 
            color='white', 
            font=font_path, 
            method='caption',
            align='center',
            size=(width - 80, None)
        )
        
        # Create a background rectangle clip with a bit of padding
        rect_padding = 10  # Padding around text
        rect_width = text_clip.w + (rect_padding * 2)
        rect_height = text_clip.h + (rect_padding * 2)
        
        # Create colored rectangle background (semi-transparent blue)
        rect_clip = ColorClip(
            size=(rect_width, rect_height),
            color=(0, 102, 204)  # RGB blue color
        ).set_opacity(0.7)  # Make it semi-transparent
        
        # Position the text over the rectangle
        text_on_rect = CompositeVideoClip([
            rect_clip,
            text_clip.set_position(("center", "center"))
        ])
        
        # Calculate timing for this highlight
        word_start_time = start_time + (i * time_per_word)
        word_duration = time_per_word
        
        # Set timing for the highlighted text with background
        word_highlight = text_on_rect.set_start(word_start_time).set_duration(word_duration)
        
        highlight_clips.append(word_highlight)
    
    # Add a final clip that keeps the last highlighted state until the end of the segment
    if current_words:
        # For the final state, we need to recreate the composite clip
        final_text_clip = TextClip(
            highlighted_text, 
            fontsize=fontsize, 
            color='white', 
            font=font_path, 
            method='caption',
            align='center',
            size=(width - 80, None)
        )
        
        rect_width = final_text_clip.w + (rect_padding * 2)
        rect_height = final_text_clip.h + (rect_padding * 2)
        
        final_rect_clip = ColorClip(
            size=(rect_width, rect_height),
            color=(0, 102, 204)
        ).set_opacity(0.7)
        
        final_composite = CompositeVideoClip([
            final_rect_clip,
            final_text_clip.set_position(("center", "center"))
        ])
        
        final_duration = duration - (len(words) * time_per_word)
        if final_duration > 0:  # Only add if there's time remaining
            final_highlight = final_composite.set_start(
                start_time + len(words) * time_per_word
            ).set_duration(final_duration)
            
            highlight_clips.append(final_highlight)
    
    return highlight_clips

def create_image_overlays(images_manifest, video_duration, shorts_width, shorts_height):
    """Create fullscreen image overlays that appear frequently throughout the video,
    ensuring text overlay areas remain visible."""
    image_clips = []
    
    # Use all segments (including first and last for more coverage)
    all_segments = images_manifest
    
    if not all_segments:
        return image_clips  # Return empty list if no segments
    
    # Select most segments to show images for (increased frequency)
    segment_count = len(all_segments)
    
    # Select approximately 90% of the segments (increased from 75%)
    num_to_select = max(2, int(segment_count * 0.9))
    selected_indices = sorted(random.sample(range(segment_count), min(num_to_select, segment_count)))
    
    for idx in selected_indices:
        segment = all_segments[idx]
        
        # Skip if URL is missing
        if not os.path.exists(segment["url"]):
            print(f"Warning: Image file not found: {segment['url']}")
            continue
        
        # Load the image
        try:
            img_clip = ImageClip(segment["url"])
            
            # Calculate start time with a slight offset into the segment
            start_time = timestamp_to_seconds(segment["start"])
            duration = timestamp_to_seconds(segment["duration"])
            
            # Show image for approximately 90% of the segment duration (increased)
            img_duration = duration * 1.0
            
            # Start right at the beginning of the segment
            img_start = start_time
            
            # Calculate the height to reserve at the bottom for text overlay
            text_height_reserve = 220  # Height to reserve for text at bottom
            
            # Calculate the available height for the image (subtract text area)
            available_height = shorts_height - text_height_reserve
            
            # Resize to fit within the available screen area while showing the entire image
            width_scale = shorts_width / img_clip.w
            height_scale = available_height / img_clip.h
            
            # Use the smaller scaling factor to ensure the entire image fits
            scale_factor = min(width_scale, height_scale)
            
            # Resize the image
            img_clip = img_clip.resize(scale_factor)
            
            # Center the image horizontally, but position at the top
            x_center = (shorts_width - img_clip.w) / 2
            
            # Create a partial background just for the image area if needed
            # (only if image doesn't fill the available width)
            if img_clip.w < shorts_width:
                # Create background only for the image area, not the text area
                img_bg = ColorClip(size=(shorts_width, available_height), color=(0, 0, 0))
                img_bg = img_bg.set_duration(img_duration)
                img_bg = img_bg.set_position((0, 0))  # Position at the top
                
                # Add image on top of the background
                positioned_img = CompositeVideoClip([
                    img_bg,
                    img_clip.set_position((x_center, 0))  # Position at the top
                ])
            else:
                # Image fills the width, no need for additional background
                positioned_img = img_clip.set_position((x_center, 0))  # Position at the top
            
            # Set timing without any fade effects
            positioned_img = (positioned_img
                             .set_start(img_start)
                             .set_duration(img_duration))
            
            image_clips.append(positioned_img)
            
        except Exception as e:
            print(f"Error creating image overlay for {segment['url']}: {e}")
    
    return image_clips

def create_video_with_overlays(state):
    print("Adding text and image overlays to existing video...")
    print(f"State: {state}")
    
    # Validate required keys in state
    if not state.get("video_path"):
        raise ValueError("video_path is required in state")
    if "videoScript" not in state.get("script", {}):
        raise ValueError("script.videoScript is required in state")
    if "images_manifest" not in state:
        raise ValueError("images_manifest is required in state")
    
    # Load the existing video (which already has audio)
    try:
        original_video = VideoFileClip(state["video_path"])
        video_duration = original_video.duration
        original_width, original_height = original_video.size
    except Exception as e:
        raise ValueError(f"Error loading video from {state['video_path']}: {str(e)}")
    
    # Define YouTube Shorts dimensions
    shorts_width, shorts_height = 1080, 1920
    
    # Create a black background for the Shorts format
    background = ColorClip(size=(shorts_width, shorts_height), color=(0, 0, 0))
    background = background.set_duration(video_duration)
    
    # Calculate the scaling factor to maximize the video size while maintaining aspect ratio
    scale_factor = shorts_width / original_width
    
    # Resize the video while maintaining aspect ratio
    resized_video = original_video.resize(scale_factor)
    
    # Get the new dimensions after resizing
    new_width, new_height = resized_video.size
    
    # Calculate position to center the resized video
    x_center = (shorts_width - new_width) // 2
    y_center = (shorts_height - new_height) // 2
    
    # Position the resized video in the center of the frame
    positioned_resized_video = resized_video.set_position((x_center, y_center))
    
    font_path = get_system_font(bold=True)
    fontsize = 60
    
    text_overlays = []
    
    # Create text overlays with word-by-word highlighting
    for seg in state["script"]["videoScript"]:
        if not seg.get("text") or not seg.get("start") or not seg.get("duration"):
            raise ValueError(f"Invalid script segment: {seg}")
        
        start_time = timestamp_to_seconds(seg["start"])
        duration = timestamp_to_seconds(seg["duration"])
        text = seg["text"]
        
        # Create word-by-word highlight clips
        word_clips = create_word_highlight_clips(
            text=text,
            width=shorts_width,
            duration=duration,
            start_time=start_time,
            fontsize=fontsize,
            font_path=font_path
        )
        
        # Position each clip at the bottom of the screen
        bottom_margin = 150  # Margin from the bottom in pixels
        
        # Add all word highlight clips to overlays
        for clip in word_clips:
            # Position at the bottom of the screen
            clip_height = clip.h
            positioned_clip = clip.set_position(("center", shorts_height - clip_height - bottom_margin))
            text_overlays.append(positioned_clip)
    
    # Create image overlays using the images_manifest
    image_overlays = create_image_overlays(
        state["images_manifest"], 
        video_duration,
        shorts_width,
        shorts_height
    )
    
    # ORDER OF CLIPS MATTERS: We put the text_overlays at the end to ensure they're on top
    all_clips = [background, positioned_resized_video] + image_overlays + text_overlays
    composite = CompositeVideoClip(all_clips, size=(shorts_width, shorts_height))
    
    # Set the duration to match the original video
    composite = composite.set_duration(video_duration)
    
    # Copy the audio from the original video
    composite = composite.set_audio(original_video.audio)
    
    # Write the final video (MoviePy will call ffmpeg internally)
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"shorts_with_overlays_{datetime.now().timestamp()}.mp4")
    
    # Write the final video
    composite.write_videofile(
        output_path, 
        fps=24, 
        codec='libx264', 
        audio_codec='aac'
    )
    
    # Close the video files to release resources
    original_video.close()
    
    return {"final_video_path": output_path}

if __name__ == "__main__":
    # Example state dictionary
    state = {'topic': 'new claude 3.7 sonnet release by anthropic', 'script': {'videoScript': [{'start': '00:00', 'duration': '00:06', 'text': 'Hey tech lovers! Big news dropped! Anthropic just released Claude 3.7 Sonnet.'}, {'start': '00:06', 'duration': '00:01', 'text': 'Wow, this is incredible!'}, {'start': '00:08', 'duration': '00:05', 'text': "It's their most advanced AI yet, offering near-instant responses and extended thinking."}, {'start': '00:14', 'duration': '00:02', 'text': 'Think faster, smarter AI.'}, {'start': '00:16', 'duration': '00:05', 'text': 'And get this, they also launched Claude Code, a game-changer for developers.'}, {'start': '00:22', 'duration': '00:04', 'text': "Coding tasks just got a whole lot easier. I'm so excited to share this."}, {'start': '00:26', 'duration': '00:05', 'text': 'It can even write, test and commit code to GitHub Are you ready to level up your coding game?'}, {'start': '00:32', 'duration': '00:05', 'text': 'So, what will you build with Cloud 3.7? Let me know in the comments!'}], 'totalDuration': '00:37'}, 'title': '🤯 Claude 3.7 DROPPED! Faster AI is HERE!', 'description': '🤯 HUGE AI NEWS! Anthropic just launched Claude 3.7 Sonnet & Code! Near-instant AI! What will you build? 👇 #Claude3 #AI #ArtificialIntelligence #Coding #Tech 🚀', 'audio_path': 'output/audio_1740593054.885661.mp3', 'images_manifest': [{'start': '00:00', 'duration': '00:06', 'text': 'Hey tech lovers! Big news dropped! Anthropic just released Claude 3.7 Sonnet.', 'url': 'output/images/segment_1.jpg'}, {'start': '00:06', 'duration': '00:01', 'text': 'Wow, this is incredible!', 'url': 'output/images/segment_2.jpg'}, {'start': '00:08', 'duration': '00:05', 'text': "It's their most advanced AI yet, offering near-instant responses and extended thinking.", 'url': 'output/images/segment_3.jpg'}, {'start': '00:14', 'duration': '00:02', 'text': 'Think faster, smarter AI.', 'url': 'output/images/segment_4.jpg'}, {'start': '00:16', 'duration': '00:05', 'text': 'And get this, they also launched Claude Code, a game-changer for developers.', 'url': 'output/images/placeholder.jpg'}, {'start': '00:22', 'duration': '00:04', 'text': "Coding tasks just got a whole lot easier. I'm so excited to share this.", 'url': 'output/images/placeholder.jpg'}, {'start': '00:26', 'duration': '00:05', 'text': 'It can even write, test and commit code to GitHub Are you ready to level up your coding game?', 'url': 'output/images/placeholder.jpg'}, {'start': '00:32', 'duration': '00:05', 'text': 'So, what will you build with Cloud 3.7? Let me know in the comments!', 'url': 'output/images/segment_8.jpg'}], 'video_path': 'output/output_avatar_video.mp4'}
    
    try:
        result = create_video_with_overlays(state)
        print(f"YouTube Shorts video with overlays created successfully: {result}")
    except Exception as err:
        print(f"Failed to create YouTube Shorts video with overlays: {err}")