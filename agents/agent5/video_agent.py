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

def split_text_into_words(text):
    """Split text into words while preserving punctuation and filtering out single-letter words."""
    # This pattern keeps punctuation attached to words
    words = re.findall(r'\b[\w\']+\b|[.,!?;:…]', text)
    
    # Filter out empty strings and single-letter words (except 'I' and 'a')
    return [word for word in words if word.strip() and (len(word) > 1 or word.lower() in ['i', 'a'])]

def create_word_by_word_clips_from_detailed_transcript(detailed_transcript, fontsize, font_path, shorts_width):
    """Create a sequence of clips with groups of 3 words appearing and disappearing based on detailed transcript timing."""
    word_clips = []
    
    # Handle empty transcript case
    if not detailed_transcript or len(detailed_transcript) == 0:
        return []
    
    # Group words into chunks of 3 words
    word_groups = []
    current_group = []
    
    for i, word_data in enumerate(detailed_transcript):
        # Add word to current group
        current_group.append(word_data)
        
        # When we have 3 words or reach the end of the transcript, finalize the group
        if len(current_group) >= 3 or i == len(detailed_transcript) - 1:
            if current_group:  # Make sure the group isn't empty
                word_groups.append(current_group)
                current_group = []
    
    # Create clips for each word group
    for group in word_groups:
        if not group:  # Skip empty groups
            continue
        
        # Get the start time from the first word and end time from the last word
        start_time = group[0].get("start", 0)
        end_time = group[-1].get("end", 0)
        
        # Skip if timing is invalid
        if end_time <= start_time:
            continue
        
        # Calculate duration
        duration = end_time - start_time
        
        # Combine the words in the group
        words_text = " ".join([word.get("word", "") for word in group])
        
        # Create text clip for the word group with increased boldness and better visibility
        text_clip = TextClip(
            words_text, 
            fontsize=fontsize, 
            color='white', 
            font=font_path,
            stroke_width=4,  # Increased stroke width for more boldness
            stroke_color='black',  # Black outline for better contrast
            method='label'
        )
        
        # Set timing and position
        text_clip = (text_clip
                    .set_start(start_time)
                    .set_duration(duration)
                    .set_position(("center", "center")))  # Position in the center of the screen
        
        word_clips.append(text_clip)
    
    return word_clips

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
        
        # Create text clip for the word group with increased boldness and better visibility
        text_clip = TextClip(
            word_group, 
            fontsize=fontsize, 
            color='white', 
            font=font_path,
            stroke_width=4,  # Increased stroke width for more boldness
            stroke_color='black',  # Black outline for better contrast
            method='label'
        )
        
        # Set timing and position
        text_clip = (text_clip
                    .set_start(word_start_time)
                    .set_duration(word_duration)
                    .set_position(("center", "center")))  # Position in the center of the screen
        
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
            
            # Calculate the height to reserve at the center for text overlay
            # Reserve more space in the middle for text
            text_height_reserve = 300  # Increased height to reserve for text in the middle
            
            # Calculate the available height for the image
            available_height = shorts_height - text_height_reserve
            
            # Resize to fit within the available screen area while showing the entire image
            width_scale = shorts_width / img_clip.w
            height_scale = shorts_height / img_clip.h  # Use full screen height for scaling
            
            # Use the smaller scaling factor to ensure the entire image fits
            scale_factor = min(width_scale, height_scale)
            
            # Resize the image
            img_clip = img_clip.resize(scale_factor)
            
            # Center the image horizontally and vertically
            x_center = (shorts_width - img_clip.w) / 2
            y_center = (shorts_height - img_clip.h) / 2
            
            # Create a full screen background
            img_bg = ColorClip(size=(shorts_width, shorts_height), color=(0, 0, 0))
            img_bg = img_bg.set_duration(img_duration)
            
            # Add zoom-out effect to the image
            # Start with a larger size and zoom out to normal size
            def zoom_effect(t):
                # Calculate zoom factor: start at 2.5x zoom and end at 1.0x
                # Use the first 0.3 seconds for the zoom effect (extremely fast zoom)
                zoom_duration = min(0.3, img_duration * 0.15)  # Use at most 15% of duration for zoom
                
                if t < zoom_duration:
                    # Aggressive non-linear interpolation for much faster initial zoom
                    progress = t / zoom_duration
                    # Use a cubic function for very rapid initial movement
                    zoom_factor = 2.5 - (1.5 * (progress * progress * progress))
                    return zoom_factor
                else:
                    # After zoom duration, maintain normal size
                    return 1.0
            
            # Add vibration effect to the image
            def vibration_effect(t):
                # Further reduced amplitude vibration
                base_amplitude = 2.5  # Reduced from 4 to 2.5
                
                # Create subtle, non-uniform vibrations
                # Use different frequencies and random factors
                t_mod = t * 6  # Slower time scale (reduced from 8)
                
                # Create gentle abrupt changes
                abrupt_factor = 0.8 + 0.1 * np.sin(t_mod * 5.0)  # Reduced variation
                
                # Random spikes in movement (less frequent and smaller)
                if (t_mod % 1.0) < 0.1:  # Create sudden movements only 10% of the time
                    x_spike = base_amplitude * 1.0  # Reduced spike multiplier
                    y_spike = base_amplitude * 0.8  # Reduced spike multiplier
                else:
                    x_spike = 0
                    y_spike = 0
                
                # Combine smooth and abrupt movements
                x_offset = np.sin(t_mod * 4.0 + 0.5) * base_amplitude * abrupt_factor + x_spike
                y_offset = np.cos(t_mod * 5.0 + 1.5) * base_amplitude * abrupt_factor + y_spike
                
                return (x_offset, y_offset)
            
            # Apply the zoom effect to the image clip
            zoomed_img = img_clip.resize(lambda t: zoom_effect(t))
            
            # Recalculate position for the zoomed image to keep it centered and add vibration
            def position_function(t):
                zoom = zoom_effect(t)
                vib_x, vib_y = vibration_effect(t)
                
                # Calculate new dimensions based on zoom factor
                new_width = img_clip.w * zoom
                new_height = img_clip.h * zoom
                
                # Use the pre-calculated center positions and adjust for zoom
                # This ensures the image stays centered during zoom and vibration
                new_x = x_center - ((new_width - img_clip.w) / 2) + vib_x
                new_y = y_center - ((new_height - img_clip.h) / 2) + vib_y
                
                return (new_x, new_y)
            
            # Create the final positioned image with background
            positioned_img = CompositeVideoClip([
                img_bg,
                zoomed_img.set_position(position_function)
            ])
            
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
    
    # Validate required keys in state
    if not state.get("audio_path"):
        raise ValueError("audio_path is required in state")
    if not state.get("images_manifest"):
        raise ValueError("images_manifest is required in state")
    if not state.get("detailed_transcript"):
        raise ValueError("detailed_transcript is required in state")
        
    
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
        font_path = "assets/fonts/LilitaOne-Regular.ttf"
        fontsize = 80  # Increased font size for better visibility and boldness
        
        # Create image overlays using the local image paths from images_manifest
        # Create these first so they appear behind the text
        image_overlays = create_image_overlays(
            state["images_manifest"], 
            video_duration,
            shorts_width,
            shorts_height
        )
        
        # Create text overlays with word-by-word highlighting using detailed transcript
        text_overlays = create_word_by_word_clips_from_detailed_transcript(
            state["detailed_transcript"],
            fontsize,
            font_path,
            shorts_width
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
    state = {'topic': 'Recent launch of Gemini 2.5 pro', 'script': '\n    Wow! Google just dropped Gemini 2.5 Pro! Can you believe it? This AI model is absolutely breaking barriers with some incredible features! What are they? First, a million token context window - that\'s huge! Second, advanced reasoning capabilities that blow previous models away. And third, dramatically improved multimodal understanding! \n    \n    What does this mean for users? It can analyze entire codebases, books, or even hours of video in one go! Isn\'t that amazing? But wait - the most impressive feature? It\'s definitely the "function calling" capability that lets developers create complex AI applications faster than ever before! How cool is that?\n    \n    Want to try it yourself? Gemini 2.5 Pro is available right now through Google AI Studio and Vertex AI! Don\'t miss out on experiencing this revolutionary technology!\n    ', 'audio_path': 'output/audios/audio.mp3', 'detailed_transcript': [{'word': 'wow', 'start': 0.161, 'end': 0.641, 'confidence': 0.986, 'punctuated_word': 'Wow,'}, {'word': 'google', 'start': 0.971, 'end': 1.291, 'confidence': 0.998, 'punctuated_word': 'Google'}, {'word': 'just', 'start': 1.351, 'end': 1.621, 'confidence': 1.0, 'punctuated_word': 'just'}, {'word': 'dropped', 'start': 1.621, 'end': 1.881, 'confidence': 1.0, 'punctuated_word': 'dropped'}, {'word': 'gemini', 'start': 1.881, 'end': 2.331, 'confidence': 0.725, 'punctuated_word': 'Gemini'}, {'word': '2.5', 'start': 2.331, 'end': 2.711, 'confidence': 0.997, 'punctuated_word': '2.5'}, {'word': 'pro', 'start': 2.711, 'end': 2.971, 'confidence': 0.995, 'punctuated_word': 'Pro.'}, {'word': 'can', 'start': 3.211, 'end': 3.381, 'confidence': 1.0, 'punctuated_word': 'Can'}, {'word': 'you', 'start': 3.381, 'end': 3.511, 'confidence': 1.0, 'punctuated_word': 'you'}, {'word': 'believe', 'start': 3.511, 'end': 3.801, 'confidence': 1.0, 'punctuated_word': 'believe'}, {'word': 'it', 'start': 3.801, 'end': 3.991, 'confidence': 1.0, 'punctuated_word': 'it?'}, {'word': 'this', 'start': 4.231, 'end': 4.461, 'confidence': 1.0, 'punctuated_word': 'This'}, {'word': 'ai', 'start': 4.541, 'end': 4.731, 'confidence': 0.998, 'punctuated_word': 'AI'}, {'word': 'model', 'start': 4.731, 'end': 5.011, 'confidence': 1.0, 'punctuated_word': 'model'}, {'word': 'is', 'start': 5.011, 'end': 5.311, 'confidence': 1.0, 'punctuated_word': 'is'}, {'word': 'absolutely', 'start': 5.311, 'end': 5.781, 'confidence': 1.0, 'punctuated_word': 'absolutely'}, {'word': 'breaking', 'start': 5.781, 'end': 6.151, 'confidence': 1.0, 'punctuated_word': 'breaking'}, {'word': 'barriers', 'start': 6.151, 'end': 6.551, 'confidence': 1.0, 'punctuated_word': 'barriers'}, {'word': 'with', 'start': 6.551, 'end': 6.721, 'confidence': 1.0, 'punctuated_word': 'with'}, {'word': 'some', 'start': 6.721, 'end': 6.901, 'confidence': 1.0, 'punctuated_word': 'some'}, {'word': 'incredible', 'start': 6.901, 'end': 7.381, 'confidence': 1.0, 'punctuated_word': 'incredible'}, {'word': 'features', 'start': 7.381, 'end': 7.801, 'confidence': 1.0, 'punctuated_word': 'features.'}, {'word': 'what', 'start': 8.111, 'end': 8.311, 'confidence': 1.0, 'punctuated_word': 'What'}, {'word': 'are', 'start': 8.311, 'end': 8.411, 'confidence': 1.0, 'punctuated_word': 'are'}, {'word': 'they', 'start': 8.411, 'end': 8.641, 'confidence': 1.0, 'punctuated_word': 'they?'}, {'word': 'first', 'start': 8.891, 'end': 9.171, 'confidence': 1.0, 'punctuated_word': 'First,'}, {'word': 'a', 'start': 9.221, 'end': 9.281, 'confidence': 1.0, 'punctuated_word': 'a'}, {'word': 'million', 'start': 9.281, 'end': 9.591, 'confidence': 1.0, 'punctuated_word': 'million'}, {'word': 'token', 'start': 9.591, 'end': 9.861, 'confidence': 1.0, 'punctuated_word': 'token'}, {'word': 'context', 'start': 9.861, 'end': 10.241, 'confidence': 1.0, 'punctuated_word': 'context'}, {'word': 'window', 'start': 10.241, 'end': 10.531, 'confidence': 1.0, 'punctuated_word': 'window.'}, {'word': "that's", 'start': 10.621, 'end': 10.821, 'confidence': 1.0, 'punctuated_word': "That's"}, {'word': 'huge', 'start': 10.821, 'end': 11.111, 'confidence': 1.0, 'punctuated_word': 'huge.'}, {'word': 'second', 'start': 11.421, 'end': 11.791, 'confidence': 1.0, 'punctuated_word': 'Second,'}, {'word': 'advanced', 'start': 11.881, 'end': 12.321, 'confidence': 1.0, 'punctuated_word': 'advanced'}, {'word': 'reasoning', 'start': 12.321, 'end': 12.731, 'confidence': 1.0, 'punctuated_word': 'reasoning'}, {'word': 'capabilities', 'start': 12.731, 'end': 13.341, 'confidence': 1.0, 'punctuated_word': 'capabilities'}, {'word': 'that', 'start': 13.341, 'end': 13.471, 'confidence': 1.0, 'punctuated_word': 'that'}, {'word': 'blow', 'start': 13.471, 'end': 13.701, 'confidence': 1.0, 'punctuated_word': 'blow'}, {'word': 'previous', 'start': 13.701, 'end': 14.031, 'confidence': 1.0, 'punctuated_word': 'previous'}, {'word': 'models', 'start': 14.031, 'end': 14.331, 'confidence': 1.0, 'punctuated_word': 'models'}, {'word': 'away', 'start': 14.331, 'end': 14.591, 'confidence': 1.0, 'punctuated_word': 'away.'}, {'word': 'and', 'start': 14.831, 'end': 15.0, 'confidence': 1.0, 'punctuated_word': 'And'}, {'word': 'third', 'start': 15.0, 'end': 15.711, 'confidence': 1.0, 'punctuated_word': 'third,'}, {'word': 'dramatically', 'start': 15.711, 'end': 16.341, 'confidence': 1.0, 'punctuated_word': 'dramatically'}, {'word': 'improved', 'start': 16.341, 'end': 16.781, 'confidence': 1.0, 'punctuated_word': 'improved'}, {'word': 'multimodal', 'start': 16.781, 'end': 17.441, 'confidence': 1.0, 'punctuated_word': 'multimodal'}, {'word': 'understanding', 'start': 17.441, 'end': 18.091, 'confidence': 1.0, 'punctuated_word': 'understanding.'}, {'word': 'what', 'start': 18.381, 'end': 18.591, 'confidence': 1.0, 'punctuated_word': 'What'}, {'word': 'does', 'start': 18.591, 'end': 18.741, 'confidence': 1.0, 'punctuated_word': 'does'}, {'word': 'this', 'start': 18.741, 'end': 18.921, 'confidence': 1.0, 'punctuated_word': 'this'}, {'word': 'mean', 'start': 18.921, 'end': 19.121, 'confidence': 1.0, 'punctuated_word': 'mean'}, {'word': 'for', 'start': 19.121, 'end': 19.261, 'confidence': 1.0, 'punctuated_word': 'for'}, {'word': 'users', 'start': 19.261, 'end': 19.691, 'confidence': 1.0, 'punctuated_word': 'users?'}, {'word': 'it', 'start': 19.841, 'end': 19.951, 'confidence': 1.0, 'punctuated_word': 'It'}, {'word': 'can', 'start': 19.951, 'end': 20.151, 'confidence': 1.0, 'punctuated_word': 'can'}, {'word': 'analyze', 'start': 20.151, 'end': 20.611, 'confidence': 1.0, 'punctuated_word': 'analyze'}, {'word': 'entire', 'start': 20.611, 'end': 20.971, 'confidence': 1.0, 'punctuated_word': 'entire'}, {'word': 'code', 'start': 21.011, 'end': 21.261, 'confidence': 1.0, 'punctuated_word': 'code'}, {'word': 'bases', 'start': 21.261, 'end': 21.691, 'confidence': 1.0, 'punctuated_word': 'bases,'}, {'word': 'books', 'start': 21.821, 'end': 22.461, 'confidence': 1.0, 'punctuated_word': 'books,'}, {'word': 'or', 'start': 22.581, 'end': 22.681, 'confidence': 1.0, 'punctuated_word': 'or'}, {'word': 'even', 'start': 22.681, 'end': 22.941, 'confidence': 1.0, 'punctuated_word': 'even'}, {'word': 'hours', 'start': 22.941, 'end': 23.231, 'confidence': 1.0, 'punctuated_word': 'hours'}, {'word': 'of', 'start': 23.231, 'end': 23.311, 'confidence': 1.0, 'punctuated_word': 'of'}, {'word': 'video', 'start': 23.311, 'end': 23.641, 'confidence': 1.0, 'punctuated_word': 'video'}, {'word': 'in', 'start': 23.641, 'end': 23.761, 'confidence': 1.0, 'punctuated_word': 'in'}, {'word': 'one', 'start': 23.761, 'end': 23.941, 'confidence': 1.0, 'punctuated_word': 'one'}, {'word': 'go', 'start': 23.941, 'end': 24.191, 'confidence': 1.0, 'punctuated_word': 'go.'}, {'word': "isn't", 'start': 24.521, 'end': 24.781, 'confidence': 1.0, 'punctuated_word': "Isn't"}, {'word': 'that', 'start': 24.781, 'end': 24.961, 'confidence': 1.0, 'punctuated_word': 'that'}, {'word': 'amazing', 'start': 24.961, 'end': 25.401, 'confidence': 1.0, 'punctuated_word': 'amazing?'}, {'word': 'but', 'start': 25.641, 'end': 25.851, 'confidence': 1.0, 'punctuated_word': 'But'}, {'word': 'wait', 'start': 25.851, 'end': 26.161, 'confidence': 1.0, 'punctuated_word': 'wait.'}, {'word': 'the', 'start': 26.341, 'end': 26.441, 'confidence': 1.0, 'punctuated_word': 'The'}, {'word': 'most', 'start': 26.441, 'end': 26.711, 'confidence': 1.0, 'punctuated_word': 'most'}, {'word': 'impressive', 'start': 26.711, 'end': 27.221, 'confidence': 1.0, 'punctuated_word': 'impressive'}, {'word': 'feature', 'start': 27.221, 'end': 27.561, 'confidence': 1.0, 'punctuated_word': 'feature?'}, {'word': "it's", 'start': 27.841, 'end': 28.051, 'confidence': 1.0, 'punctuated_word': "It's"}, {'word': 'definitely', 'start': 28.051, 'end': 28.491, 'confidence': 1.0, 'punctuated_word': 'definitely'}, {'word': 'the', 'start': 28.491, 'end': 28.611, 'confidence': 1.0, 'punctuated_word': 'the'}, {'word': 'function', 'start': 28.611, 'end': 29.061, 'confidence': 1.0, 'punctuated_word': 'function'}, {'word': 'calling', 'start': 29.061, 'end': 29.411, 'confidence': 1.0, 'punctuated_word': 'calling'}, {'word': 'capability', 'start': 29.411, 'end': 30.381, 'confidence': 1.0, 'punctuated_word': 'capability'}, {'word': 'that', 'start': 30.381, 'end': 30.531, 'confidence': 1.0, 'punctuated_word': 'that'}, {'word': 'lets', 'start': 30.531, 'end': 30.731, 'confidence': 1.0, 'punctuated_word': 'lets'}, {'word': 'developers', 'start': 30.731, 'end': 31.161, 'confidence': 1.0, 'punctuated_word': 'developers'}, {'word': 'create', 'start': 31.161, 'end': 31.511, 'confidence': 1.0, 'punctuated_word': 'create'}, {'word': 'complex', 'start': 31.511, 'end': 31.981, 'confidence': 1.0, 'punctuated_word': 'complex'}, {'word': 'ai', 'start': 32.051, 'end': 32.251, 'confidence': 1.0, 'punctuated_word': 'AI'}, {'word': 'applications', 'start': 32.251, 'end': 33.1, 'confidence': 1.0, 'punctuated_word': 'applications'}, {'word': 'faster', 'start': 33.1, 'end': 33.411, 'confidence': 1.0, 'punctuated_word': 'faster'}, {'word': 'than', 'start': 33.411, 'end': 33.621, 'confidence': 1.0, 'punctuated_word': 'than'}, {'word': 'ever', 'start': 33.621, 'end': 33.861, 'confidence': 1.0, 'punctuated_word': 'ever'}, {'word': 'before', 'start': 33.861, 'end': 34.241, 'confidence': 1.0, 'punctuated_word': 'before.'}, {'word': 'how', 'start': 34.611, 'end': 34.811, 'confidence': 1.0, 'punctuated_word': 'How'}, {'word': 'cool', 'start': 34.811, 'end': 35.071, 'confidence': 1.0, 'punctuated_word': 'cool'}, {'word': 'is', 'start': 35.071, 'end': 35.171, 'confidence': 1.0, 'punctuated_word': 'is'}, {'word': 'that', 'start': 35.171, 'end': 35.421, 'confidence': 1.0, 'punctuated_word': 'that?'}, {'word': 'want', 'start': 35.551, 'end': 35.751, 'confidence': 1.0, 'punctuated_word': 'Want'}, {'word': 'to', 'start': 35.751, 'end': 35.831, 'confidence': 1.0, 'punctuated_word': 'to'}, {'word': 'try', 'start': 35.831, 'end': 36.041, 'confidence': 1.0, 'punctuated_word': 'try'}, {'word': 'it', 'start': 36.041, 'end': 36.121, 'confidence': 1.0, 'punctuated_word': 'it'}, {'word': 'yourself', 'start': 36.121, 'end': 36.561, 'confidence': 1.0, 'punctuated_word': 'yourself?'}, {'word': 'gemini', 'start': 36.741, 'end': 37.131, 'confidence': 0.85, 'punctuated_word': 'Gemini'}, {'word': '2.5', 'start': 37.181, 'end': 37.531, 'confidence': 0.995, 'punctuated_word': '2.5'}, {'word': 'pro', 'start': 37.531, 'end': 37.751, 'confidence': 1.0, 'punctuated_word': 'Pro'}, {'word': 'is', 'start': 37.751, 'end': 37.861, 'confidence': 1.0, 'punctuated_word': 'is'}, {'word': 'available', 'start': 37.861, 'end': 38.331, 'confidence': 1.0, 'punctuated_word': 'available'}, {'word': 'right', 'start': 38.331, 'end': 38.581, 'confidence': 1.0, 'punctuated_word': 'right'}, {'word': 'now', 'start': 38.581, 'end': 38.831, 'confidence': 1.0, 'punctuated_word': 'now'}, {'word': 'through', 'start': 38.831, 'end': 39.051, 'confidence': 1.0, 'punctuated_word': 'through'}, {'word': 'google', 'start': 39.051, 'end': 39.321, 'confidence': 1.0, 'punctuated_word': 'Google'}, {'word': 'ai', 'start': 39.321, 'end': 39.531, 'confidence': 1.0, 'punctuated_word': 'AI'}, {'word': 'studio', 'start': 39.531, 'end': 40.271, 'confidence': 1.0, 'punctuated_word': 'Studio'}, {'word': 'and', 'start': 40.271, 'end': 40.451, 'confidence': 1.0, 'punctuated_word': 'and'}, {'word': 'vertex', 'start': 40.451, 'end': 40.831, 'confidence': 1.0, 'punctuated_word': 'Vertex'}, {'word': 'ai', 'start': 40.831, 'end': 41.131, 'confidence': 1.0, 'punctuated_word': 'AI.'}, {'word': "don't", 'start': 41.491, 'end': 41.781, 'confidence': 1.0, 'punctuated_word': "Don't"}, {'word': 'miss', 'start': 41.781, 'end': 41.991, 'confidence': 1.0, 'punctuated_word': 'miss'}, {'word': 'out', 'start': 41.991, 'end': 42.221, 'confidence': 1.0, 'punctuated_word': 'out'}, {'word': 'on', 'start': 42.221, 'end': 42.341, 'confidence': 1.0, 'punctuated_word': 'on'}, {'word': 'experiencing', 'start': 42.341, 'end': 42.881, 'confidence': 1.0, 'punctuated_word': 'experiencing'}, {'word': 'this', 'start': 42.881, 'end': 43.071, 'confidence': 1.0, 'punctuated_word': 'this'}, {'word': 'revolutionary', 'start': 43.071, 'end': 43.711, 'confidence': 1.0, 'punctuated_word': 'revolutionary'}, {'word': 'technology', 'start': 43.711, 'end': 44.261, 'confidence': 1.0, 'punctuated_word': 'technology.'}], 'images_manifest': [{'start': '00:00', 'duration': '00:06', 'text': 'Wow, Google just dropped Gemini 1.5 Pro. Can you believe it? This AI model is absolutely breaking barriers', 'url': 'output/images/1.jpg', 'source_url': 'https://i.ytimg.com/vi/wa0MT8OwHuk/maxresdefault.jpg', 'search_term': 'Gemini 1.5 Pro launch image vertical high quality'}, {'start': '00:06', 'duration': '00:05', 'text': "with some incredible features. What are they? First, a million token context window, that's huge.", 'url': 'output/images/2.jpg', 'source_url': 'https://storage.googleapis.com/gweb-uniblog-publish-prod/images/final_2.5_blog_1.original.jpg', 'search_term': 'Gemini 2.5 Pro context window vertical high quality'}, {'start': '00:11', 'duration': '00:04', 'text': 'Second, advanced reasoning capabilities that blow previous models away. And third,', 'url': 'output/images/3.jpg', 'source_url': 'https://storage.googleapis.com/gweb-uniblog-publish-prod/images/final_2.5_blog_1.original.jpg', 'search_term': 'Gemini 2.5 Pro reasoning capabilities vertical high quality'}, {'start': '00:15', 'duration': '00:04', 'text': 'dramatically improved multimodal understanding. What does this mean for users?', 'url': 'output/images/4.jpg', 'source_url': 'https://storage.googleapis.com/gweb-uniblog-publish-prod/images/final_2.5_blog_1.original.jpg', 'search_term': 'Gemini 2.5 Pro multimodal examples vertical high quality'}, {'start': '00:19', 'duration': '00:05', 'text': 'It can analyze entire code bases, books, or even hours of video in one go.', 'url': 'output/images/5.jpg', 'source_url': 'https://storage.googleapis.com/gweb-uniblog-publish-prod/images/final_2.5_blog_1.original.jpg', 'search_term': 'Gemini 2.5 Pro analysis capabilities vertical high quality'}, {'start': '00:24', 'duration': '00:05', 'text': "Isn't that amazing? But wait, the most impressive feature? It's definitely the function calling capability", 'url': 'output/images/6.jpg', 'source_url': 'https://storage.googleapis.com/gweb-uniblog-publish-prod/images/final_2.5_blog_1.original.jpg', 'search_term': 'Gemini 2.5 Pro function calling vertical high quality'}, {'start': '00:29', 'duration': '00:05', 'text': 'that lets developers create complex AI applications faster than ever before.', 'url': 'output/images/7.jpg', 'source_url': 'https://res.infoq.com/news/2025/03/gemini-2-5-pro/en/headerimage/generatedHeaderImage-1743189035105.jpg', 'search_term': 'Gemini 2.5 Pro applications development vertical high quality'}, {'start': '00:34', 'duration': '00:05', 'text': 'How cool is that? Want to try it yourself? Gemini 1.5 Pro is available right now through Google AI Studio', 'url': 'output/images/8.jpg', 'source_url': 'https://i.ytimg.com/vi/wa0MT8OwHuk/maxresdefault.jpg', 'search_term': 'Gemini 1.5 Pro Google AI Studio vertical high quality'}, {'start': '00:39', 'duration': '00:05', 'text': "and Vertex AI. Don't miss out on experiencing this revolutionary technology.", 'url': 'output/images/9.jpg', 'source_url': 'https://res.infoq.com/news/2025/03/gemini-2-5-pro/en/headerimage/generatedHeaderImage-1743189035105.jpg', 'search_term': 'Gemini 2.5 Pro interface vertical high quality'}], 'bg_music_path': 'assets/bg_music.mp3'}
    result = create_video_with_overlays(state)
    print(result)