import os
import numpy as np
from datetime import datetime
from moviepy.editor import (
    AudioFileClip, TextClip, CompositeVideoClip, ColorClip, ImageClip,
    concatenate_audioclips, CompositeAudioClip, VideoFileClip
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
        
        # Set timing and position - Position below center instead of at center
        # Use lambda function to calculate position dynamically based on clip size
        text_clip = (text_clip
                    .set_start(start_time)
                    .set_duration(duration)
                    .set_position(lambda t: ('center', 1920//2 + 350)))  # Position 150px below the center
        
        word_clips.append(text_clip)
    
    return word_clips

def create_image_overlays(images_manifest, video_duration, shorts_width, shorts_height):
    """Create fullscreen image overlays that appear throughout the video,
    ensuring text overlay areas remain visible."""
    image_clips = []
    transition_clips = []
    
    # Use all segments
    all_segments = images_manifest
    
    if not all_segments:
        return image_clips  # Return empty list if no segments
    
    # Use ALL segments instead of just 90%
    selected_indices = list(range(len(all_segments)))
    
    # Track the end time of the previous image to ensure no gaps
    previous_end_time = 0
    
    # Load the shutter effect transition video
    shutter_effect_path = "assets/audios/shutter-effect.mp4"
    if os.path.exists(shutter_effect_path):
        shutter_effect = VideoFileClip(shutter_effect_path, audio=True)  # Explicitly load audio
        # Set the transition duration (in seconds)
        transition_duration = min(0.5, shutter_effect.duration)  # Use at most 0.5 seconds or the full duration if shorter
    else:
        print(f"Warning: Shutter effect video not found at {shutter_effect_path}")
        shutter_effect = None
        transition_duration = 0
    
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
            
            # Create a full screen background using the image layout
            img_bg = ImageClip("assets/images/placeholder.jpg").set_duration(img_duration)
            
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
            
            # Define position function for vibration only (no zoom)
            def position_function(t):
                vib_x, vib_y = vibration_effect(t)
                
                # Use the pre-calculated center positions and add vibration
                new_x = x_center + vib_x
                new_y = y_center + vib_y
                
                return (new_x, new_y)
            
            # Create the final positioned image with background
            positioned_img = CompositeVideoClip([
                img_bg,
                img_clip.set_position(position_function)
            ])
            
            # Set timing
            positioned_img = (positioned_img
                            .set_start(img_start)
                            .set_duration(img_duration))
            
            image_clips.append(positioned_img)
            
            # Add transition effect at the end of this image (except for the last image)
            if shutter_effect is not None and i < len(selected_indices) - 1:
                # Calculate when to start the transition (at the end of the current image minus transition duration)
                transition_start = img_start + img_duration - transition_duration
                
                # Create a copy of the shutter effect for this transition
                transition_clip = shutter_effect.copy()
                
                # Resize the transition to fill the screen
                transition_clip = transition_clip.resize(height=shorts_height)
                
                # Set the timing for the transition
                transition_clip = (transition_clip
                                .set_start(transition_start)
                                .set_duration(transition_duration))
                
                # Add the transition clip to our list
                transition_clips.append(transition_clip)
            
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
    
    # Combine image clips and transition clips
    return image_clips + transition_clips

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
        
        # Create a background using the image layout for the Shorts format
        background = ImageClip("assets/images/placeholder.jpg")
        background = background.set_duration(video_duration)
        
        # Get fonts
        font_path = "assets/fonts/LilitaOne-Regular.ttf"
        fontsize = 80  # Increased font size for better visibility and boldness
        
        # Create image overlays using the local image paths from images_manifest
        # Create these first so they appear behind the text
        image_and_transition_clips = create_image_overlays(
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
        transition_audio_clips = []
        
        # Extract audio from transition clips if they have audio
        for clip in image_and_transition_clips:
            if hasattr(clip, 'audio') and clip.audio is not None:
                # Create an audio clip with the same timing as the video clip
                transition_audio = clip.audio.set_start(clip.start).set_duration(clip.duration)
                transition_audio_clips.append(transition_audio)
        
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
                if transition_audio_clips:
                    # Include transition audio clips in the final audio
                    final_audio = CompositeAudioClip([audio, bg_music] + transition_audio_clips)
                else:
                    final_audio = CompositeAudioClip([audio, bg_music])
                
                print(f"Background music added from {state['bg_music_path']}")
            except Exception as e:
                print(f"Warning: Could not add background music: {e}")
        else:
            print("No background music path provided or file not found, continuing without background music")
            # Still include transition audio if available
            if transition_audio_clips:
                final_audio = CompositeAudioClip([audio] + transition_audio_clips)
        
        # Combine all clips - ORDER MATTERS: background first, then images, then text on top
        all_clips = [background] + image_and_transition_clips + text_overlays
        
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
            if 'image_and_transition_clips' in locals():
                for clip in image_and_transition_clips:
                    clip.close()
            
            # Close all text clips
            if 'text_overlays' in locals():
                for clip in text_overlays:
                    clip.close()
                    
            # Close shutter effect clip if it exists
            if 'shutter_effect' in locals() and shutter_effect is not None:
                shutter_effect.close()
                    
        except Exception as e:
            print(f"Warning: Failed to clean up some MoviePy clips: {e}")

if __name__ == "__main__":
    state = {'topic': 'Recent launch of Gemini 2.5 pro', 'script': "\n    Hey tech enthusiasts! Guess what? Meta just dropped Llama 4... and wow, it's a game-changer! They've released two initial models: Scout and Maverick.\n\n    Scout runs on a single H100 GPU but packs a punch with 17 billion active parameters and—get this—a context window of 10 MILLION tokens! That's insane for document processing.\n\n    Maverick is the multilingual beast with 400 billion total parameters supporting 12 languages and amazing multimodal abilities.\n\n    But here's the juicy part... they're still training the most powerful version called 'Behemoth' with a mind-blowing 2 TRILLION parameters! Can you imagine what that will do?\n\n    What makes Llama 4 special? It uses a Mixture of Experts architecture and early fusion for handling text, images, and video seamlessly.\n\n    The best part? It's open-source! You can download it now from llama.com or try it on Meta's platforms.\n\n    Ready to build something amazing with Llama 4? Let me know in the comments!\n    ", 'audio_path': 'assets/audios/audio.mp3', 'detailed_transcript': [{'word': 'Hey', 'start': 0.066, 'end': 0.286, 'confidence': 0.98, 'punctuated_word': 'Hey'}, {'word': 'tech', 'start': 0.286, 'end': 0.516, 'confidence': 0.99, 'punctuated_word': 'tech'}, {'word': 'enthusiasts,', 'start': 0.516, 'end': 1.166, 'confidence': 0.99, 'punctuated_word': 'enthusiasts,'}, {'word': 'guess', 'start': 1.306, 'end': 1.616, 'confidence': 0.99, 'punctuated_word': 'guess'}, {'word': 'what?', 'start': 1.616, 'end': 1.886, 'confidence': 0.99, 'punctuated_word': 'what?'}, {'word': 'Meta', 'start': 1.976, 'end': 2.256, 'confidence': 0.99, 'punctuated_word': 'Meta'}, {'word': 'just', 'start': 2.256, 'end': 2.496, 'confidence': 0.99, 'punctuated_word': 'just'}, {'word': 'dropped', 'start': 2.496, 'end': 2.806, 'confidence': 0.99, 'punctuated_word': 'dropped'}, {'word': 'Llama', 'start': 2.956, 'end': 3.246, 'confidence': 0.98, 'punctuated_word': 'Llama'}, {'word': '4,', 'start': 3.246, 'end': 3.456, 'confidence': 0.98, 'punctuated_word': '4,'}, {'word': 'and', 'start': 3.706, 'end': 3.866, 'confidence': 0.99, 'punctuated_word': 'and'}, {'word': 'wow,', 'start': 4.096, 'end': 4.356, 'confidence': 0.99, 'punctuated_word': 'wow,'}, {'word': "it's", 'start': 4.356, 'end': 4.526, 'confidence': 0.99, 'punctuated_word': "it's"}, {'word': 'a', 'start': 4.526, 'end': 4.576, 'confidence': 0.99, 'punctuated_word': 'a'}, {'word': 'game', 'start': 4.636, 'end': 4.896, 'confidence': 0.99, 'punctuated_word': 'game'}, {'word': 'changer.', 'start': 4.896, 'end': 5.316, 'confidence': 0.99, 'punctuated_word': 'changer.'}, {'word': "They've", 'start': 5.426, 'end': 5.686, 'confidence': 0.99, 'punctuated_word': "They've"}, {'word': 'released', 'start': 5.686, 'end': 6.086, 'confidence': 0.99, 'punctuated_word': 'released'}, {'word': 'two', 'start': 6.086, 'end': 6.266, 'confidence': 0.99, 'punctuated_word': 'two'}, {'word': 'initial', 'start': 6.266, 'end': 6.656, 'confidence': 0.99, 'punctuated_word': 'initial'}, {'word': 'models,', 'start': 6.656, 'end': 7.046, 'confidence': 0.99, 'punctuated_word': 'models,'}, {'word': 'Scout', 'start': 7.136, 'end': 7.486, 'confidence': 0.99, 'punctuated_word': 'Scout'}, {'word': 'and', 'start': 7.486, 'end': 7.626, 'confidence': 0.99, 'punctuated_word': 'and'}, {'word': 'Maverick.', 'start': 7.626, 'end': 8.096, 'confidence': 0.99, 'punctuated_word': 'Maverick.'}, {'word': 'Scout', 'start': 8.216, 'end': 8.566, 'confidence': 0.99, 'punctuated_word': 'Scout'}, {'word': 'runs', 'start': 8.566, 'end': 8.816, 'confidence': 0.99, 'punctuated_word': 'runs'}, {'word': 'on', 'start': 8.816, 'end': 8.916, 'confidence': 0.99, 'punctuated_word': 'on'}, {'word': 'a', 'start': 8.916, 'end': 8.966, 'confidence': 0.99, 'punctuated_word': 'a'}, {'word': 'single', 'start': 9.066, 'end': 9.396, 'confidence': 0.99, 'punctuated_word': 'single'}, {'word': 'H100', 'start': 9.516, 'end': 9.846, 'confidence': 0.95, 'punctuated_word': 'H100'}, {'word': 'GPU', 'start': 9.846, 'end': 10.236, 'confidence': 0.99, 'punctuated_word': 'GPU'}, {'word': 'but', 'start': 10.466, 'end': 10.666, 'confidence': 0.99, 'punctuated_word': 'but'}, {'word': 'packs', 'start': 10.716, 'end': 11.016, 'confidence': 0.99, 'punctuated_word': 'packs'}, {'word': 'a', 'start': 11.016, 'end': 11.046, 'confidence': 0.99, 'punctuated_word': 'a'}, {'word': 'punch', 'start': 11.126, 'end': 11.416, 'confidence': 0.99, 'punctuated_word': 'punch'}, {'word': 'with', 'start': 11.416, 'end': 11.606, 'confidence': 0.99, 'punctuated_word': 'with'}, {'word': '17', 'start': 11.766, 'end': 12.146, 'confidence': 0.96, 'punctuated_word': '17'}, {'word': 'billion', 'start': 12.216, 'end': 12.566, 'confidence': 0.99, 'punctuated_word': 'billion'}, {'word': 'active', 'start': 12.566, 'end': 12.916, 'confidence': 0.99, 'punctuated_word': 'active'}, {'word': 'parameters', 'start': 12.916, 'end': 13.446, 'confidence': 0.99, 'punctuated_word': 'parameters'}, {'word': 'and', 'start': 13.446, 'end': 13.616, 'confidence': 0.99, 'punctuated_word': 'and'}, {'word': 'get', 'start': 13.616, 'end': 13.826, 'confidence': 0.99, 'punctuated_word': 'get'}, {'word': 'this,', 'start': 13.826, 'end': 14.066, 'confidence': 0.99, 'punctuated_word': 'this,'}, {'word': 'a', 'start': 14.246, 'end': 14.346, 'confidence': 0.99, 'punctuated_word': 'a'}, {'word': 'context', 'start': 14.466, 'end': 14.866, 'confidence': 0.99, 'punctuated_word': 'context'}, {'word': 'window', 'start': 14.866, 'end': 15.186, 'confidence': 0.99, 'punctuated_word': 'window'}, {'word': 'of', 'start': 15.186, 'end': 15.316, 'confidence': 0.99, 'punctuated_word': 'of'}, {'word': '10', 'start': 15.386, 'end': 15.666, 'confidence': 0.99, 'punctuated_word': '10'}, {'word': 'million', 'start': 15.666, 'end': 16.006, 'confidence': 0.99, 'punctuated_word': 'million'}, {'word': 'tokens.', 'start': 16.006, 'end': 16.486, 'confidence': 0.99, 'punctuated_word': 'tokens.'}, {'word': "That's", 'start': 16.746, 'end': 16.996, 'confidence': 0.99, 'punctuated_word': "That's"}, {'word': 'insane', 'start': 17.076, 'end': 17.426, 'confidence': 0.99, 'punctuated_word': 'insane'}, {'word': 'for', 'start': 17.426, 'end': 17.576, 'confidence': 0.99, 'punctuated_word': 'for'}, {'word': 'document', 'start': 17.636, 'end': 18.016, 'confidence': 0.99, 'punctuated_word': 'document'}, {'word': 'processing.', 'start': 18.016, 'end': 18.486, 'confidence': 0.99, 'punctuated_word': 'processing.'}, {'word': 'Maverick', 'start': 18.686, 'end': 19.076, 'confidence': 0.99, 'punctuated_word': 'Maverick'}, {'word': 'is', 'start': 19.076, 'end': 19.206, 'confidence': 0.99, 'punctuated_word': 'is'}, {'word': 'the', 'start': 19.206, 'end': 19.326, 'confidence': 0.99, 'punctuated_word': 'the'}, {'word': 'multilingual', 'start': 19.396, 'end': 20.006, 'confidence': 0.99, 'punctuated_word': 'multilingual'}, {'word': 'beast', 'start': 20.076, 'end': 20.396, 'confidence': 0.99, 'punctuated_word': 'beast'}, {'word': 'with', 'start': 20.396, 'end': 20.586, 'confidence': 0.99, 'punctuated_word': 'with'}, {'word': '400', 'start': 20.776, 'end': 21.216, 'confidence': 0.98, 'punctuated_word': '400'}, {'word': 'billion', 'start': 21.216, 'end': 21.536, 'confidence': 0.99, 'punctuated_word': 'billion'}, {'word': 'total', 'start': 21.536, 'end': 21.876, 'confidence': 0.99, 'punctuated_word': 'total'}, {'word': 'parameters,', 'start': 21.876, 'end': 22.446, 'confidence': 0.99, 'punctuated_word': 'parameters,'}, {'word': 'supporting', 'start': 22.556, 'end': 22.956, 'confidence': 0.99, 'punctuated_word': 'supporting'}, {'word': '12', 'start': 23.066, 'end': 23.356, 'confidence': 0.98, 'punctuated_word': '12'}, {'word': 'languages', 'start': 23.356, 'end': 23.896, 'confidence': 0.99, 'punctuated_word': 'languages'}, {'word': 'and', 'start': 24.056, 'end': 24.226, 'confidence': 0.99, 'punctuated_word': 'and'}, {'word': 'amazing', 'start': 24.356, 'end': 24.766, 'confidence': 0.99, 'punctuated_word': 'amazing'}, {'word': 'multimodal', 'start': 24.836, 'end': 25.296, 'confidence': 0.99, 'punctuated_word': 'multimodal'}, {'word': 'abilities.', 'start': 25.296, 'end': 25.806, 'confidence': 0.99, 'punctuated_word': 'abilities.'}, {'word': 'But', 'start': 26.196, 'end': 26.386, 'confidence': 0.99, 'punctuated_word': 'But'}, {'word': "here's", 'start': 26.386, 'end': 26.646, 'confidence': 0.99, 'punctuated_word': "here's"}, {'word': 'the', 'start': 26.646, 'end': 26.746, 'confidence': 0.99, 'punctuated_word': 'the'}, {'word': 'juicy', 'start': 26.746, 'end': 27.006, 'confidence': 0.99, 'punctuated_word': 'juicy'}, {'word': 'part.', 'start': 27.006, 'end': 27.296, 'confidence': 0.99, 'punctuated_word': 'part.'}, {'word': "They're", 'start': 27.546, 'end': 27.726, 'confidence': 0.99, 'punctuated_word': "They're"}, {'word': 'still', 'start': 27.726, 'end': 27.996, 'confidence': 0.99, 'punctuated_word': 'still'}, {'word': 'training', 'start': 27.996, 'end': 28.346, 'confidence': 0.99, 'punctuated_word': 'training'}, {'word': 'the', 'start': 28.346, 'end': 28.456, 'confidence': 0.99, 'punctuated_word': 'the'}, {'word': 'most', 'start': 28.516, 'end': 28.796, 'confidence': 0.99, 'punctuated_word': 'most'}, {'word': 'powerful', 'start': 28.866, 'end': 29.266, 'confidence': 0.99, 'punctuated_word': 'powerful'}, {'word': 'version', 'start': 29.266, 'end': 29.596, 'confidence': 0.99, 'punctuated_word': 'version'}, {'word': 'called', 'start': 29.596, 'end': 29.866, 'confidence': 0.99, 'punctuated_word': 'called'}, {'word': 'Behemoth', 'start': 29.926, 'end': 30.436, 'confidence': 0.98, 'punctuated_word': 'Behemoth'}, {'word': 'with', 'start': 30.646, 'end': 30.816, 'confidence': 0.99, 'punctuated_word': 'with'}, {'word': 'a', 'start': 30.816, 'end': 30.846, 'confidence': 0.99, 'punctuated_word': 'a'}, {'word': 'mind-blowing', 'start': 30.936, 'end': 31.566, 'confidence': 0.99, 'punctuated_word': 'mind-blowing'}, {'word': '2', 'start': 31.626, 'end': 31.816, 'confidence': 0.98, 'punctuated_word': '2'}, {'word': 'trillion', 'start': 31.816, 'end': 32.176, 'confidence': 0.99, 'punctuated_word': 'trillion'}, {'word': 'parameters.', 'start': 32.176, 'end': 32.756, 'confidence': 0.99, 'punctuated_word': 'parameters.'}, {'word': 'Can', 'start': 32.916, 'end': 33.076, 'confidence': 0.99, 'punctuated_word': 'Can'}, {'word': 'you', 'start': 33.076, 'end': 33.206, 'confidence': 0.99, 'punctuated_word': 'you'}, {'word': 'imagine', 'start': 33.206, 'end': 33.646, 'confidence': 0.99, 'punctuated_word': 'imagine'}, {'word': 'what', 'start': 33.646, 'end': 33.836, 'confidence': 0.99, 'punctuated_word': 'what'}, {'word': 'that', 'start': 33.836, 'end': 33.996, 'confidence': 0.99, 'punctuated_word': 'that'}, {'word': 'will', 'start': 33.996, 'end': 34.166, 'confidence': 0.99, 'punctuated_word': 'will'}, {'word': 'do?', 'start': 34.166, 'end': 34.376, 'confidence': 0.99, 'punctuated_word': 'do?'}, {'word': 'What', 'start': 34.486, 'end': 34.686, 'confidence': 0.99, 'punctuated_word': 'What'}, {'word': 'makes', 'start': 34.686, 'end': 34.966, 'confidence': 0.99, 'punctuated_word': 'makes'}, {'word': 'Llama', 'start': 34.966, 'end': 35.266, 'confidence': 0.97, 'punctuated_word': 'Llama'}, {'word': '4', 'start': 35.266, 'end': 35.406, 'confidence': 0.97, 'punctuated_word': '4'}, {'word': 'special?', 'start': 35.406, 'end': 35.846, 'confidence': 0.99, 'punctuated_word': 'special?'}, {'word': 'It', 'start': 36.186, 'end': 36.306, 'confidence': 0.99, 'punctuated_word': 'It'}, {'word': 'uses', 'start': 36.306, 'end': 36.616, 'confidence': 0.99, 'punctuated_word': 'uses'}, {'word': 'a', 'start': 36.616, 'end': 36.646, 'confidence': 0.99, 'punctuated_word': 'a'}, {'word': 'mixture', 'start': 36.746, 'end': 37.096, 'confidence': 0.99, 'punctuated_word': 'mixture'}, {'word': 'of', 'start': 37.096, 'end': 37.196, 'confidence': 0.99, 'punctuated_word': 'of'}, {'word': 'experts', 'start': 37.276, 'end': 37.766, 'confidence': 0.99, 'punctuated_word': 'experts'}, {'word': 'architecture', 'start': 37.766, 'end': 38.366, 'confidence': 0.99, 'punctuated_word': 'architecture'}, {'word': 'and', 'start': 38.366, 'end': 38.516, 'confidence': 0.99, 'punctuated_word': 'and'}, {'word': 'early', 'start': 38.516, 'end': 38.806, 'confidence': 0.99, 'punctuated_word': 'early'}, {'word': 'fusion', 'start': 38.806, 'end': 39.256, 'confidence': 0.99, 'punctuated_word': 'fusion'}, {'word': 'for', 'start': 39.386, 'end': 39.546, 'confidence': 0.99, 'punctuated_word': 'for'}, {'word': 'handling', 'start': 39.546, 'end': 39.936, 'confidence': 0.99, 'punctuated_word': 'handling'}, {'word': 'text,', 'start': 39.936, 'end': 40.266, 'confidence': 0.99, 'punctuated_word': 'text,'}, {'word': 'images,', 'start': 40.386, 'end': 40.766, 'confidence': 0.99, 'punctuated_word': 'images,'}, {'word': 'and', 'start': 40.766, 'end': 40.906, 'confidence': 0.99, 'punctuated_word': 'and'}, {'word': 'video', 'start': 40.906, 'end': 41.226, 'confidence': 0.99, 'punctuated_word': 'video'}, {'word': 'seamlessly.', 'start': 41.226, 'end': 41.756, 'confidence': 0.99, 'punctuated_word': 'seamlessly.'}, {'word': 'The', 'start': 41.966, 'end': 42.106, 'confidence': 0.99, 'punctuated_word': 'The'}, {'word': 'best', 'start': 42.106, 'end': 42.376, 'confidence': 0.99, 'punctuated_word': 'best'}, {'word': 'part?', 'start': 42.376, 'end': 42.706, 'confidence': 0.99, 'punctuated_word': 'part?'}, {'word': "It's", 'start': 42.926, 'end': 43.126, 'confidence': 0.99, 'punctuated_word': "It's"}, {'word': 'open', 'start': 43.226, 'end': 43.476, 'confidence': 0.99, 'punctuated_word': 'open'}, {'word': 'source.', 'start': 43.476, 'end': 43.876, 'confidence': 0.99, 'punctuated_word': 'source.'}, {'word': 'You', 'start': 44.086, 'end': 44.236, 'confidence': 0.99, 'punctuated_word': 'You'}, {'word': 'can', 'start': 44.236, 'end': 44.406, 'confidence': 0.99, 'punctuated_word': 'can'}, {'word': 'download', 'start': 44.406, 'end': 44.776, 'confidence': 0.99, 'punctuated_word': 'download'}, {'word': 'it', 'start': 44.776, 'end': 44.876, 'confidence': 0.99, 'punctuated_word': 'it'}, {'word': 'now', 'start': 44.876, 'end': 45.086, 'confidence': 0.99, 'punctuated_word': 'now'}, {'word': 'from', 'start': 45.086, 'end': 45.306, 'confidence': 0.99, 'punctuated_word': 'from'}, {'word': 'llama.com', 'start': 45.386, 'end': 46.016, 'confidence': 0.96, 'punctuated_word': 'llama.com'}, {'word': 'or', 'start': 46.186, 'end': 46.336, 'confidence': 0.99, 'punctuated_word': 'or'}, {'word': 'try', 'start': 46.336, 'end': 46.576, 'confidence': 0.99, 'punctuated_word': 'try'}, {'word': 'it', 'start': 46.576, 'end': 46.696, 'confidence': 0.99, 'punctuated_word': 'it'}, {'word': 'on', 'start': 46.696, 'end': 46.836, 'confidence': 0.99, 'punctuated_word': 'on'}, {'word': "Meta's", 'start': 46.916, 'end': 47.286, 'confidence': 0.99, 'punctuated_word': "Meta's"}, {'word': 'platforms.', 'start': 47.286, 'end': 47.826, 'confidence': 0.99, 'punctuated_word': 'platforms.'}, {'word': 'Ready', 'start': 48.066, 'end': 48.356, 'confidence': 0.99, 'punctuated_word': 'Ready'}, {'word': 'to', 'start': 48.356, 'end': 48.456, 'confidence': 0.99, 'punctuated_word': 'to'}, {'word': 'build', 'start': 48.456, 'end': 48.706, 'confidence': 0.99, 'punctuated_word': 'build'}, {'word': 'something', 'start': 48.706, 'end': 49.036, 'confidence': 0.99, 'punctuated_word': 'something'}, {'word': 'amazing', 'start': 49.086, 'end': 49.496, 'confidence': 0.99, 'punctuated_word': 'amazing'}, {'word': 'with', 'start': 49.496, 'end': 49.686, 'confidence': 0.99, 'punctuated_word': 'with'}, {'word': 'Llama', 'start': 49.686, 'end': 49.956, 'confidence': 0.97, 'punctuated_word': 'Llama'}, {'word': '4?', 'start': 49.956, 'end': 50.166, 'confidence': 0.97, 'punctuated_word': '4?'}, {'word': 'Let', 'start': 50.296, 'end': 50.476, 'confidence': 0.99, 'punctuated_word': 'Let'}, {'word': 'me', 'start': 50.476, 'end': 50.596, 'confidence': 0.99, 'punctuated_word': 'me'}, {'word': 'know', 'start': 50.596, 'end': 50.826, 'confidence': 0.99, 'punctuated_word': 'know'}, {'word': 'in', 'start': 50.826, 'end': 50.946, 'confidence': 0.99, 'punctuated_word': 'in'}, {'word': 'the', 'start': 50.946, 'end': 51.046, 'confidence': 0.99, 'punctuated_word': 'the'}, {'word': 'comments.', 'start': 51.046, 'end': 51.536, 'confidence': 0.99, 'punctuated_word': 'comments.'}], 'images_manifest': [{'start': '00:00', 'duration': '00:05', 'text': "Hey tech enthusiasts, guess what? Meta just dropped Llama 4, and wow, it's a game changer.", 'url': 'assets/images/1.jpg', 'source_url': 'https://storage.googleapis.com/gweb-uniblog-publish-prod/images/final_2.5_blog_1.original.jpg', 'search_term': 'Gemini 2.5 Pro performance comparison vertical high quality'}, {'start': '00:05', 'duration': '00:05', 'text': "They've released two initial models, Scout and Maverick. Scout runs on a single H100 GPU,", 'url': 'assets/images/2.jpg', 'source_url': 'https://hindiimages.etnownews.com/thumb/msid-151357040,width-1280,height-720,resizemode-75/151357040.jpg', 'search_term': 'Llama 4 models Scout Maverick vertical high quality'}, {'start': '00:10', 'duration': '00:06', 'text': 'but packs a punch with 17 billion active parameters and get this, a context window of 10 million tokens.', 'url': 'assets/images/3.jpg', 'source_url': 'https://storage.googleapis.com/gweb-uniblog-publish-prod/images/final_2.5_blog_1.original.jpg', 'search_term': 'Gemini 2.5 Pro architecture diagram vertical high quality'}, {'start': '00:16', 'duration': '00:07', 'text': "That's insane for document processing. Maverick is the multilingual beast with 400 billion total parameters, supporting 12 languages,", 'url': 'assets/images/4.jpg', 'source_url': 'https://www.solulab.com/wp-content/uploads/2024/09/Large-Language-Models-1024x569.jpg', 'search_term': 'Multilingual language model comparison chart vertical high quality'}, {'start': '00:23', 'duration': '00:04', 'text': "and amazing multimodal abilities. But here's the juicy part.", 'url': 'assets/images/5.jpg', 'source_url': 'https://storage.googleapis.com/gweb-uniblog-publish-prod/images/final_2.5_blog_1.original.jpg', 'search_term': 'Gemini 2.5 Pro multimodal capabilities vertical high quality'}, {'start': '00:27', 'duration': '00:05', 'text': "They're still training the most powerful version called Behemoth, with a mind-blowing two trillion parameters.", 'url': 'assets/images/6.jpg', 'source_url': 'https://dev.ua/storage/images/82/46/01/64/derived/48bb05f2ea86adc73e3732723a34dd86.jpg', 'search_term': 'Llama 4 Behemoth architecture vertical high quality'}, {'start': '00:32', 'duration': '00:05', 'text': 'Can you imagine what that will do? What makes Llama 4 special? It uses a mixture of experts architecture', 'url': 'assets/images/7.jpg', 'source_url': 'https://storage.googleapis.com/gweb-research2023-media/original_images/ba5144968824a01adef53b4223fb6378-image2.jpg', 'search_term': 'Mixture of Experts architecture diagram vertical high quality'}, {'start': '00:37', 'duration': '00:04', 'text': 'and early fusion for handling text, images, and video seamlessly.', 'url': 'assets/images/8.jpg', 'source_url': 'https://www.researchgate.net/publication/337643039/figure/fig3/AS:855222037536770@1580912231658/a-Early-fusion-video-and-audio-features-are-concatenated-and-used-to-train-an-SVR-b.jpg', 'search_term': 'early fusion text image video vertical high quality'}, {'start': '00:41', 'duration': '00:04', 'text': "The best part? It's open source. You can download it now from llama.com", 'url': 'assets/images/9.jpg', 'source_url': 'https://cdn.arstechnica.net/wp-content/uploads/2024/07/lama405b_hero_3.jpg', 'search_term': 'Llama 4 open source download vertical high quality'}, {'start': '00:45', 'duration': '00:06', 'text': "or try it on Meta's platforms. Ready to build something amazing with Llama 4? Let me know in the comments.", 'url': 'assets/images/10.jpg', 'source_url': 'https://pbs.twimg.com/media/GnzCofAbcAAVkQm.jpg', 'search_term': 'Meta Llama 4 architecture diagram vertical high quality'}], 'bg_music_path': 'assets/audios/bg_music3.mp3'}
    result = create_video_with_overlays(state)
    print(result)