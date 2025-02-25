import os
import numpy as np
from datetime import datetime
from moviepy.editor import (
    ColorClip, ImageClip, TextClip, CompositeVideoClip, AudioFileClip
)
from PIL import Image
import matplotlib.font_manager as fm
import re

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
        
        # Set position for the combined clip (centered horizontally, fixed vertically)
        positioned_clip = text_on_rect.set_position(("center", "center"))
        
        # Calculate timing for this highlight
        word_start_time = start_time + (i * time_per_word)
        word_duration = time_per_word
        
        # Set timing for the highlighted text with background
        word_highlight = positioned_clip.set_start(word_start_time).set_duration(word_duration)
        
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
        ]).set_position(("center", "center"))
        
        final_duration = duration - (len(words) * time_per_word)
        if final_duration > 0:  # Only add if there's time remaining
            final_highlight = final_composite.set_start(
                start_time + len(words) * time_per_word
            ).set_duration(final_duration)
            
            highlight_clips.append(final_highlight)
    
    return highlight_clips

def create_video_file(state):
    print("Creating final video using MoviePy with word-by-word highlighting...")
    print(f"State: {state}")
    
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
    
    # Process each image overlay with extended duration - using local paths now
    for img_entry in state["images_manifest"]:
        if not img_entry.get("url") or not img_entry.get("start") or not img_entry.get("duration"):
            raise ValueError(f"Invalid image manifest entry: {img_entry}")
        start_time = timestamp_to_seconds(img_entry["start"])
        original_duration = timestamp_to_seconds(img_entry["duration"])
        
        # Extend duration by the factor but ensure it doesn't exceed video length
        extended_duration = min(original_duration * extend_factor, video_duration - start_time)
        
        # Use the local file path directly instead of downloading
        image_path = img_entry["url"]
        
        # Check if the image file exists
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file not found at path: {image_path}")
        
        # Open the image from the local path
        pil_img = Image.open(image_path).convert("RGB")
        # Resize image to fill the frame
        pil_img = pil_img.resize((width, height))
        np_img = np.array(pil_img)
        
        # Create image clip with no fade in/out and extended duration
        image_clip = ImageClip(np_img).set_start(start_time).set_duration(extended_duration)
        overlays.append(image_clip)

    # Process text overlays with word-by-word highlighting
    font_path = get_system_font(bold=True)
    fontsize = 60  # Larger font size for better readability
    
    for seg in state["script"]["videoScript"]:
        if not seg.get("text") or not seg.get("start") or not seg.get("duration"):
            raise ValueError(f"Invalid script segment: {seg}")
        
        start_time = timestamp_to_seconds(seg["start"])
        duration = timestamp_to_seconds(seg["duration"])
        text = seg["text"]
        
        # Create word-by-word highlight clips
        word_clips = create_word_highlight_clips(
            text=text,
            width=width,
            duration=duration,
            start_time=start_time,
            fontsize=fontsize,
            font_path=font_path
        )
        
        # Position each clip at the bottom of the screen
        bottom_margin = 100  # Margin from the bottom in pixels
        
        # Add all word highlight clips to overlays
        for clip in word_clips:
            # Check if it's already a CompositeVideoClip (which our new function creates)
            if isinstance(clip, CompositeVideoClip):
                clip_height = clip.h
                positioned_clip = clip.set_position(("center", height - clip_height - bottom_margin))
                overlays.append(positioned_clip)
            else:
                # For compatibility with any existing clips that might not have backgrounds
                clip_height = clip.h
                positioned_clip = clip.set_position(("center", height - clip_height - bottom_margin))
                overlays.append(positioned_clip)

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
    state = {'topic': 'Short moral of a story', 'script': {'videoScript': [{'start': '00:00', 'duration': '00:05', 'text': 'Hey! Ever heard a story that just sticks with you? Well get this...'}, {'start': '00:05', 'duration': '00:05', 'text': 'Truth and wisdom? ... Found where you LEAST expect it! Wow!'}, {'start': '00:10', 'duration': '00:06', 'text': 'Moral of the story? ... Look everywhere... even the uncomfortable places!'}, {'start': '00:16', 'duration': '00:06', 'text': "I'm so excited! What's a story that changed YOUR perspective?"}], 'totalDuration': '00:22'}, 'title': 'Uncover Truth! Unexpected Wisdom🤯 #shorts #wisdom #truth', 'description': "🤯Truth in unexpected places! You won't believe it! What story changed YOU? Share below! 👇 #storytime #mindblown #perspective", 'thumbnail_url': 'https://v3.fal.media/files/monkey/-Cw463xzRZ8rZkPml0fPJ.jpeg', 'audio_path': 'output/audio_1740506364.321846.mp3', 'images_manifest': [{'start': '00:00', 'duration': '00:05', 'text': 'Hey! Ever heard a story that just sticks with you? Well get this...', 'url': 'output/images/segment_1.jpg'}, {'start': '00:05', 'duration': '00:05', 'text': 'Truth and wisdom? ... Found where you LEAST expect it! Wow!', 'url': 'output/images/segment_2.jpg'}, {'start': '00:10', 'duration': '00:06', 'text': 'Moral of the story? ... Look everywhere... even the uncomfortable places!', 'url': 'output/images/segment_3.jpg'}, {'start': '00:16', 'duration': '00:06', 'text': "I'm so excited! What's a story that changed YOUR perspective?", 'url': 'output/images/segment_4.jpg'}]}
    
    try:
        result = create_video_file(state)
        print(f"Video created successfully: {result}")
    except Exception as err:
        print(f"Failed to create video: {err}")