import os
import numpy as np
from datetime import datetime
from moviepy.editor import (
    AudioFileClip, TextClip, CompositeVideoClip, ColorClip, ImageClip,
    concatenate_audioclips, CompositeAudioClip
)
import matplotlib.font_manager as fm
import re

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
    """Split text into words while preserving punctuation and filtering out single-letter words."""
    # This pattern keeps punctuation attached to words
    words = re.findall(r'\b[\w\']+\b|[.,!?;:…]', text)
    
    # Filter out empty strings and single-letter words (except 'I' and 'a')
    return [word for word in words if word.strip() and (len(word) > 1 or word.lower() in ['i', 'a'])]

def create_word_by_word_clips(text, start_time, duration, fontsize, font_path, shorts_width):
    """Create a sequence of clips with groups of words appearing and disappearing in sync with audio."""
    words = split_text_into_words(text)
    
    # Handle empty text case
    if len(words) == 0:
        return []
    
    # Group words into groups of 4 (or fewer for the last group if needed)
    word_groups = []
    i = 0
    current_group = []
    
    while i < len(words):
        # Check if current word is punctuation
        if words[i] in '.,!?;:…':
            # If we have words in the current group, add the punctuation to the last word
            if current_group:
                current_group[-1] += words[i]
            i += 1
            continue
        
        # Add the current word to the group
        current_group.append(words[i])
        i += 1
        
        # If we have 4 words or we've reached the end of the text, finalize the group
        if len(current_group) == 4 or i >= len(words):
            # Check if the next word is punctuation and add it to the last word in the group
            if i < len(words) and words[i] in '.,!?;:…':
                current_group[-1] += words[i]
                i += 1
            
            # Join the words with spaces and add to word_groups
            word_groups.append(" ".join(current_group))
            current_group = []
    
    # Calculate timing for each word group
    # We'll use less of the total duration to create gaps between captions
    # This ensures captions don't overlap and provides better sync with audio
    usable_duration = duration * 0.85  # Use only 85% of the total duration for captions
    
    # If we have no word groups (rare edge case), return empty list
    if not word_groups:
        return []
        
    time_per_group = usable_duration / len(word_groups)
    
    # Add an initial delay to sync better with audio
    # This helps ensure the caption appears slightly after the audio starts
    initial_delay = 0.4  # Increased from 0.2 to 0.4 seconds
    
    # Add a gap between captions to prevent overlap
    gap_between_captions = 0.2  # Increased from 0.1 to 0.2 seconds
    
    word_clips = []
    
    for i, word_group in enumerate(word_groups):
        # Calculate timing for this word group with initial delay and gaps
        # Each subsequent caption starts after the previous one ends plus a gap
        word_start_time = start_time + initial_delay + (i * (time_per_group + gap_between_captions))
        
        # Each word group appears for less than its allocated time to ensure no overlap
        word_duration = time_per_group * 0.9  # 90% of the allocated time
        
        # Create text clip for the word group
        text_clip = TextClip(
            word_group, 
            fontsize=fontsize, 
            color='white', 
            font=font_path,
            stroke_width=2,  # Add stroke for better visibility
            stroke_color='black',  # Black outline for better contrast
            method='label'
        )
        
        # Set timing and position
        text_clip = (text_clip
                    .set_start(word_start_time)
                    .set_duration(word_duration)
                    .set_position(("center", "center")))
        
        word_clips.append(text_clip)
    
    return word_clips

def create_image_overlays(images_manifest, video_duration, shorts_width, shorts_height):
    """Create fullscreen image overlays that appear throughout the video,
    ensuring text overlay areas remain visible."""
    image_clips = []
    
    # Use all segments
    all_segments = images_manifest
    
    if not all_segments:
        return image_clips  # Return empty list if no segments
    
    # Use ALL segments instead of just 90%
    selected_indices = list(range(len(all_segments)))
    
    # Track the end time of the previous image to ensure no gaps
    previous_end_time = 0
    
    for i, idx in enumerate(selected_indices):
        segment = all_segments[idx]
        
        # Skip if URL (file path) is missing or file doesn't exist
        if not segment.get("url") or not os.path.exists(segment["url"]):
            print(f"Warning: Image file not found: {segment.get('url')}")
            continue
        
        # Load the image
        try:
            img_clip = ImageClip(segment["url"])
            
            # Calculate start time and duration
            start_time = timestamp_to_seconds(segment["start"])
            duration = timestamp_to_seconds(segment["duration"])
            
            # Show image for 100% of the segment duration
            img_duration = duration
            
            # Start right at the beginning of the segment
            img_start = start_time
            
            # If there's a gap between this image and the previous one, adjust start time
            if i > 0 and img_start > previous_end_time:
                # There's a gap, so start this image right after the previous one
                img_start = previous_end_time
                # Extend duration to cover the gap
                img_duration += (start_time - previous_end_time)
            
            # Update the end time for the next iteration
            previous_end_time = img_start + img_duration
            
            # Calculate the height to reserve at the bottom for text overlay
            text_height_reserve = 220  # Height to reserve for text at bottom
            
            # Calculate the available height for the image
            available_height = shorts_height - text_height_reserve
            
            # Resize to fit within the available screen area while showing the entire image
            width_scale = shorts_width / img_clip.w
            height_scale = available_height / img_clip.h
            
            # Use the smaller scaling factor to ensure the entire image fits
            scale_factor = min(width_scale, height_scale)
            
            # Resize the image
            img_clip = img_clip.resize(scale_factor)
            
            # Center the image horizontally AND vertically
            x_center = (shorts_width - img_clip.w) / 2
            # Calculate vertical position to center in the available space
            y_center = (available_height - img_clip.h) / 2
            
            # Create a partial background for the image area if needed
            if img_clip.w < shorts_width or img_clip.h < available_height:
                # Create background only for the image area
                img_bg = ColorClip(size=(shorts_width, available_height), color=(0, 0, 0))
                img_bg = img_bg.set_duration(img_duration)
                img_bg = img_bg.set_position((0, 0))  # Position at the top
                
                # Add image on top of the background
                positioned_img = CompositeVideoClip([
                    img_bg,
                    img_clip.set_position((x_center, y_center))  # Position in center
                ])
            else:
                # Image fills the width, no need for additional background
                positioned_img = img_clip.set_position((x_center, y_center))  # Position in center
            
            # Set timing
            positioned_img = (positioned_img
                             .set_start(img_start)
                             .set_duration(img_duration))
            
            image_clips.append(positioned_img)
            
        except Exception as e:
            print(f"Error creating image overlay for {segment['url']}: {e}")
    
    # Check if there's still time left after the last image
    if previous_end_time < video_duration:
        # If the last image doesn't extend to the end of the video,
        # extend its duration or repeat the last image
        if image_clips:
            last_clip = image_clips[-1]
            extended_duration = last_clip.duration + (video_duration - previous_end_time)
            image_clips[-1] = last_clip.set_duration(extended_duration)
    
    return image_clips

def create_video_with_overlays(state):
    print("Creating final video with word-by-word highlighting...")
    print("\n\nState from create_video node: ", state)
    state["bg_music_path"] = "assets/bg_music.mp3"
    
    # Validate required keys in state
    if not state.get("audio_path"):
        raise ValueError("audio_path is required in state")
    if not state.get("images_manifest"):
        raise ValueError("images_manifest is required in state")
    if not state.get("script", {}).get("videoScript"):
        raise ValueError("script.videoScript is required in state")
    
    # Define YouTube Shorts dimensions
    shorts_width, shorts_height = 1080, 1920
    
    try:
        # Load audio
        audio = AudioFileClip(state["audio_path"])
        video_duration = audio.duration
        
        # Create a black background for the Shorts format
        background = ColorClip(size=(shorts_width, shorts_height), color=(0, 0, 0))
        background = background.set_duration(video_duration)
        
        # Get fonts
        font_path = get_system_font(bold=True)
        fontsize = 70  # Increased font size for better visibility
        
        # Create text overlays with word-by-word highlighting
        text_overlays = []
        for seg in state["script"]["videoScript"]:
            if not seg.get("text") or not seg.get("start") or not seg.get("duration"):
                raise ValueError(f"Invalid script segment: {seg}")
            
            start_time = timestamp_to_seconds(seg["start"])
            duration = timestamp_to_seconds(seg["duration"])
            text = seg["text"]
            
            # Create word-by-word clips
            word_clips = create_word_by_word_clips(
                text=text,
                start_time=start_time,
                duration=duration,
                fontsize=fontsize,
                font_path=font_path,
                shorts_width=shorts_width
            )
            
            # Position each clip at the bottom of the screen
            bottom_margin = 150  # Margin from the bottom in pixels
            
            # Add all word clips to overlays
            for clip in word_clips:
                # Position at the bottom of the screen
                positioned_clip = clip.set_position(("center", shorts_height - bottom_margin))
                text_overlays.append(positioned_clip)
        
        # Create image overlays using the local image paths from images_manifest
        image_overlays = create_image_overlays(
            state["images_manifest"], 
            video_duration,
            shorts_width,
            shorts_height
        )
        
        # Add background music if provided
        final_audio = audio
        if "bg_music_path" in state and state["bg_music_path"] and os.path.exists(state["bg_music_path"]):
            try:
                # Load background music
                bg_music = AudioFileClip(state["bg_music_path"])
                
                # Set the volume to be low (10% of original)
                bg_music = bg_music.volumex(0.1)
                
                # Loop the music if it's shorter than the video
                if bg_music.duration < video_duration:
                    # Calculate how many times we need to loop
                    loop_count = int(np.ceil(video_duration / bg_music.duration))
                    # Create a list of music clips
                    music_clips = [bg_music] * loop_count
                    # Concatenate the clips
                    bg_music = concatenate_audioclips(music_clips)
                
                # Trim to match video duration
                bg_music = bg_music.subclip(0, video_duration)
                
                # Mix background music with original audio
                final_audio = CompositeAudioClip([audio, bg_music])
                
                print(f"Background music added from {state['bg_music_path']}")
            except Exception as e:
                print(f"Warning: Could not add background music: {e}")
        else:
            print("No background music path provided or file not found, continuing without background music")
        
        # Combine all clips - ORDER MATTERS: background first, then images, then text on top
        all_clips = [background] + image_overlays + text_overlays
        
        # Create composite video
        composite = CompositeVideoClip(all_clips, size=(shorts_width, shorts_height))
        
        # Set the duration to match the audio
        composite = composite.set_duration(video_duration)
        
        # Set the final audio
        composite = composite.set_audio(final_audio)
        
        # Create output directory if it doesn't exist
        output_dir = "output/final_videos"
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate output path with timestamp
        output_path = f"{output_dir}/video_output_{datetime.now().timestamp()}.mp4"
        
        # Write the final video
        composite.write_videofile(
            output_path,
            fps=24,
            codec="libx264",
            audio_codec="aac",
            audio=True,
            threads=4,
            preset='medium'
        )
        
        # Return the path to the final video
        return {"final_video_path": output_path}
        
    except Exception as e:
        raise ValueError(f"Failed to create video: {str(e)}")
        
    finally:
        # Clean up MoviePy clips
        try:
            if 'composite' in locals():
                composite.close()
            if 'audio' in locals():
                audio.close()
            if 'bg_music' in locals():
                bg_music.close()
            
            # Close all image clips
            if 'image_overlays' in locals():
                for clip in image_overlays:
                    clip.close()
            
            # Close all text clips
            if 'text_overlays' in locals():
                for clip in text_overlays:
                    clip.close()
                    
        except Exception as e:
            print(f"Warning: Failed to clean up some MoviePy clips: {e}")

if __name__ == "__main__":
    state = {'topic': 'Tell me a motivational real story', 'script': {'videoScript': [{'start': '00:00', 'duration': '00:05', 'text': 'Ever feel like giving up? I get it. But listen to this.'}, {'start': '00:05', 'duration': '00:06', 'text': "I'm so excited to share this with you. Have you heard of Colonel Sanders? Yeah, the KFC guy."}, {'start': '00:11', 'duration': '00:07', 'text': 'Get this. He was 65, 65 years old and basically broke'}, {'start': '00:18', 'duration': '00:06', 'text': 'when he decided to turn his chicken recipe into Kentucky Fried Chicken. Can you believe it?'}, {'start': '00:24', 'duration': '00:05', 'text': '65. Most people are thinking about retirement.'}, {'start': '00:29', 'duration': '00:06', 'text': 'He was thinking about fried chicken domination. Talk about never giving up on your dream, right?'}, {'start': '00:35', 'duration': '00:07', 'text': "This is incredible. So, what's your asterisk KFC? What dream are asterisk you going to chase"}, {'start': '00:42', 'duration': '00:06', 'text': "no matter your age? Let me know in the comments. Let's inspire each other."}], 'totalDuration': '00:48'}, 'title': '65 & Broke?! 🤯 Never Give Up! #Motivation #Inspiration', 'description': "Feeling defeated? Colonel Sanders wasn't! 🍗 He started KFC at 65! What's YOUR dream? 👇 Comment below! #NeverGiveUp #KFC #Shorts #Success", 'thumbnail_url': 'https://avatars.githubusercontent.com/u/91617309?v=4', 'audio_path': 'output/audios/audio_1743319871.140448.mp3', 'images_manifest': [{'start': '00:00', 'duration': '00:05', 'text': 'Ever feel like giving up? I get it. But listen to this.', 'url': 'output/images/segment_1.png', 'source': 'Gemini', 'prompt': "Vertical portrait orientation, 1080x1620. A lone figure, a young woman with determined eyes, stands silhouetted against a breathtaking sunrise over a vast mountain range. She's dressed in modern athletic wear, suggesting resilience and perseverance. The sky explodes with vibrant hues of orange, pink, and gold, contrasting sharply with the deep blue shadows clinging to the mountain peaks. Use dramatic backlighting to emphasize her silhouette and create a sense of scale and isolation. The composition should be slightly off-center, drawing the viewer's eye towards her. The mood is hopeful and inspiring, conveying a feeling of overcoming adversity. Render in a photorealistic style with sharp focus and exceptional detail, giving a sense of awe and wonder. The overall aesthetic is clean, modern, and professional, suitable for a tech-savvy audience. No text or logos."}, {'start': '00:05', 'duration': '00:06', 'text': "I'm so excited to share this with you. Have you heard of Colonel Sanders? Yeah, the KFC guy.", 'url': 'output/images/segment_2.png', 'source': 'Gemini', 'prompt': "Vertical portrait of a young, enthusiastic entrepreneur in a brightly lit, modern office space. The entrepreneur is mid-gesture, eyes wide with excitement, subtly pointing towards a vintage framed portrait of a younger Colonel Sanders (Harland Sanders) hanging on the wall behind them. The portrait is slightly out of focus, suggesting it's a point of inspiration rather than the main subject. The office features sleek, minimalist furniture and a large window overlooking a vibrant cityscape bathed in warm, golden hour sunlight. Employ a shallow depth of field to keep the entrepreneur sharp and the background soft. The overall mood is optimistic and energetic, with a color palette of warm yellows, oranges, and teals. Use a realistic, slightly stylized digital painting style, aiming for high resolution and detail to create a visually compelling image for a YouTube Short. Dimensions: 1080x1620. No text."}, {'start': '00:11', 'duration': '00:07', 'text': 'Get this. He was 65, 65 years old and basically broke', 'url': 'output/images/segment_3.png', 'source': 'Gemini', 'prompt': "A vertical portrait image (1080x1620) depicting a weathered but determined 65-year-old man. He is sitting alone on a park bench under the shade of a large, leafy tree, looking thoughtfully into the distance. His clothing is simple and slightly worn, but clean and respectable. The bench is slightly aged but well-maintained. Sunlight filters through the leaves, creating dappled lighting on his face and the surrounding area, highlighting wrinkles around his eyes that tell a story of experience. The background is slightly blurred, focusing attention on the man. The overall mood is somber yet hopeful. The style is realistic with a touch of painterly flair, vibrant colors, and high detail. The lighting should be soft and warm, emphasizing the man's resilience. The composition should be balanced and visually appealing, avoiding any text or words. The aesthetic is modern and professional, suitable for tech-related content, conveying a sense of quiet strength and the potential for change."}, {'start': '00:18', 'duration': '00:06', 'text': 'when he decided to turn his chicken recipe into Kentucky Fried Chicken. Can you believe it?', 'url': 'output/images/segment_4.png', 'source': 'Gemini', 'prompt': "Vertical portrait orientation, 1080x1620. A determined, slightly weathered, but kind-looking Colonel Sanders (stylized, not photorealistic) in his late 40s, standing in a 1930s era, clean but modest kitchen. He's wearing a crisp white chef's apron, a partially unbuttoned white shirt, and a loosened black tie. His sleeves are rolled up, revealing strong forearms. He's gazing confidently towards the viewer, a subtle smile playing on his lips. In the background, a large cast iron skillet sizzles with golden-brown fried chicken pieces. Ingredients like flour, spices, and milk are neatly arranged on a wooden countertop. Warm, inviting lighting emanates from a window, casting soft shadows and highlighting the textures of the food and kitchenware. The overall mood is hopeful, industrious, and hinting at future success. A slight depth of field blurs the very back of the kitchen, focusing attention on Colonel Sanders and the chicken. A modern, professional aesthetic with vibrant colors and sharp details. High-quality resolution. No text or words visible."}, {'start': '00:24', 'duration': '00:05', 'text': '65. Most people are thinking about retirement.', 'url': 'output/images/segment_5.png', 'source': 'Gemini', 'prompt': 'Vertical portrait, 1080x1620. Create an image depicting a diverse group of people, aged 30s-50s, subtly blurred in the background, gazing wistfully at a distant, idealized beach scene through a large, modern office window. Focus sharply on a single, determined individual in the foreground, mid-stride, wearing smart casual attire, looking directly at the viewer with a confident, almost challenging expression. The office space is bright, clean, and minimalist, with soft, natural light streaming in from the window, creating long shadows. The beach scene visible through the window should be vibrant and inviting, contrasting with the focused, professional atmosphere of the office. The overall mood should be aspirational but grounded in reality. Style: Clean, modern, slightly desaturated color palette except for the vibrant beach scene. High quality, sharp focus on the foreground individual, bokeh effect on the background.'}, {'start': '00:29', 'duration': '00:06', 'text': 'He was thinking about fried chicken domination. Talk about never giving up on your dream, right?', 'url': 'output/images/segment_6.png', 'source': 'Gemini', 'prompt': "A vertical (1080x1620) image depicting a determined young African-American man in his late 20s, wearing a crisp, slightly grease-stained white chef's apron over a casual t-shirt. He's standing in a bustling, modern, stainless-steel commercial kitchen. The background is slightly blurred, showing hints of activity: other chefs, gleaming equipment, and steam rising from cooking stations. His gaze is intense and focused, directed slightly upwards and to the right, as if visualizing a grand ambition. In his mind's eye, subtly overlaid and semi-transparent in front of him, is a vibrant, almost ethereal image of a cascading mountain of perfectly golden-brown fried chicken. The lighting is bright and warm, highlighting the crispness of the imagined chicken and the determination in his face. The overall mood is aspirational and energetic. The style should be photorealistic but with a slight stylized, almost hyperreal quality, emphasizing the textures and colors. Composition should be tight on the man's face and upper body, drawing the viewer's eye to his expression and the projected image of the fried chicken. High quality, vibrant colors, and clear subject matter are crucial."}, {'start': '00:35', 'duration': '00:07', 'text': "This is incredible. So, what's your asterisk KFC? What dream are asterisk you going to chase", 'url': 'output/images/placeholder.jpg'}, {'start': '00:42', 'duration': '00:06', 'text': "no matter your age? Let me know in the comments. Let's inspire each other.", 'url': 'output/images/segment_8.png', 'source': 'Gemini', 'prompt': 'Vertical portrait orientation, 1080x1620. A vibrant and hopeful scene depicting a diverse group of people silhouetted against a breathtaking sunrise over a futuristic cityscape. The silhouettes should represent different ages, from children to elderly figures, all gazing towards the radiant sun. The cityscape should incorporate elements of sustainable technology, such as wind turbines and solar panels, subtly integrated into the architecture. The lighting should be dramatic, with warm orange and pink hues emanating from the sunrise, casting long, soft shadows. A sense of aspiration and unity should permeate the image. Style: Modern, clean, and optimistic, with a touch of science fiction. Composition: A wide shot, emphasizing the scale of the cityscape and the collective hope of the silhouetted figures. High quality, sharp focus, and vibrant colors.'}]}
    result = create_video_with_overlays(state)
    print(result)