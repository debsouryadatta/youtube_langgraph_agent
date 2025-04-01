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
    """Create a sequence of clips with groups of 3-4 words appearing and disappearing based on detailed transcript timing."""
    word_clips = []
    
    # Handle empty transcript case
    if not detailed_transcript or len(detailed_transcript) == 0:
        return []
    
    # Group words into chunks of 3-4 words
    word_groups = []
    current_group = []
    
    for i, word_data in enumerate(detailed_transcript):
        # Add word to current group
        current_group.append(word_data)
        
        # When we have 3-4 words or reach the end of the transcript, finalize the group
        if len(current_group) >= 4 or i == len(detailed_transcript) - 1:
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
    state["bg_music_path"] = "assets/bg_music2.mp3"
    
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
                
                # Set the volume to be low (40% of original)
                bg_music = bg_music.volumex(0.4)
                
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
    state = {'topic': "The story of Shikhandi and Bhishma's downfall", 'script': "Dosto, kabhi socha hai ki aapki sabse badi taakat hi aapki kamzori kaise ban sakti hai? Mahabharat yaad hai? Pitamah Bhishma... Iccha Mrityu ka vardaan tha unhe! Koi unhe hara nahi sakta tha. Lekin unki ek pratigya thi - woh kisi stri ya napunsak par shastra nahi uthayenge. Aur phir Kurukshetra ke maidan mein aaye Shikhandi. Pehchante the Bhishma... yeh Amba hai, pichle janam ki woh atma jiska apmaan hua tha, ab ek naye roop mein. Shikhandi ko saamne dekh, Bhishma ne apna dhanush neeche rakh diya. Apni pratigya nibhaai, apna dharm nibhaya. Aur usi pal, Arjun ne unhe baan-shayya par lita diya. Socho zara! Itna bada yoddha, apne hi vachan se bandh gaya. Zindagi mein hum bhi toh kabhi kabhi apne hi banaye usoolon mein, apni hi zidd mein, aise hi phas jaate hain na? Kya koi aisi 'pratigya' hai jo aapko aage badhne se rok rahi hai? Apne dil se poochho. Aur comment mein zaroor batana!", 'title': "🤯Bhishma's Deadly Vow! Mahabharat Secrets #shorts #motivation", 'description': "Could your strength be your weakness? 🤔 Mahabharat's Bhishma! Find YOUR 'vow' holding you back! 👇 Comment now! #mahabharat #hinduism #storytime #inspiration", 'thumbnail_url': 'https://avatars.githubusercontent.com/u/91617309?v=4', 'audio_path': 'output/audios/audio_1743504573.050883.mp3', 'detailed_transcript': [{'word': 'dosto', 'start': 0.704, 'end': 1.024, 'confidence': 0.97, 'punctuated_word': 'दोस्तों,'}, {'word': 'kabhi', 'start': 1.214, 'end': 1.414, 'confidence': 0.99, 'punctuated_word': 'कभी'}, {'word': 'socha', 'start': 1.414, 'end': 1.664, 'confidence': 0.99, 'punctuated_word': 'सोचा'}, {'word': 'hai', 'start': 1.664, 'end': 1.774, 'confidence': 0.97, 'punctuated_word': 'है'}, {'word': 'ki', 'start': 1.834, 'end': 1.944, 'confidence': 0.9, 'punctuated_word': 'कि'}, {'word': 'aapki', 'start': 2.044, 'end': 2.304, 'confidence': 0.98, 'punctuated_word': 'आपकी'}, {'word': 'sabse', 'start': 2.304, 'end': 2.554, 'confidence': 0.99, 'punctuated_word': 'सबसे'}, {'word': 'badi', 'start': 2.554, 'end': 2.794, 'confidence': 0.99, 'punctuated_word': 'बड़ी'}, {'word': 'taakat', 'start': 2.794, 'end': 3.074, 'confidence': 0.99, 'punctuated_word': 'ताकत'}, {'word': 'hi', 'start': 3.074, 'end': 3.194, 'confidence': 0.99, 'punctuated_word': 'ही'}, {'word': 'aapki', 'start': 3.294, 'end': 3.554, 'confidence': 0.99, 'punctuated_word': 'आपकी'}, {'word': 'kamzori', 'start': 3.584, 'end': 4.024, 'confidence': 0.98, 'punctuated_word': 'कमजोरी'}, {'word': 'kaise', 'start': 4.024, 'end': 4.274, 'confidence': 0.99, 'punctuated_word': 'कैसे'}, {'word': 'ban', 'start': 4.274, 'end': 4.434, 'confidence': 0.99, 'punctuated_word': 'बन'}, {'word': 'sakti', 'start': 4.434, 'end': 4.714, 'confidence': 0.99, 'punctuated_word': 'सकती'}, {'word': 'hai', 'start': 4.714, 'end': 4.874, 'confidence': 0.99, 'punctuated_word': 'है?'}, {'word': 'Mahabharat', 'start': 5.204, 'end': 5.694, 'confidence': 0.99, 'punctuated_word': 'महाभारत'}, {'word': 'yaad', 'start': 5.784, 'end': 6.024, 'confidence': 0.99, 'punctuated_word': 'याद'}, {'word': 'hai', 'start': 6.024, 'end': 6.184, 'confidence': 0.99, 'punctuated_word': 'है?'}, {'word': 'pitamah', 'start': 6.334, 'end': 6.784, 'confidence': 0.99, 'punctuated_word': 'पितामह'}, {'word': 'Bhishma', 'start': 6.784, 'end': 7.244, 'confidence': 0.97, 'punctuated_word': 'भीष्मा,'}, {'word': 'ichchha', 'start': 7.454, 'end': 7.804, 'confidence': 0.93, 'punctuated_word': 'इच्छा'}, {'word': 'mrityu', 'start': 7.804, 'end': 8.104, 'confidence': 0.99, 'punctuated_word': 'मृत्यु'}, {'word': 'ka', 'start': 8.104, 'end': 8.244, 'confidence': 0.99, 'punctuated_word': 'का'}, {'word': 'vardaan', 'start': 8.294, 'end': 8.664, 'confidence': 0.99, 'punctuated_word': 'वरदान'}, {'word': 'tha', 'start': 8.664, 'end': 8.814, 'confidence': 0.99, 'punctuated_word': 'था'}, {'word': 'unhein', 'start': 8.814, 'end': 9.174, 'confidence': 0.98, 'punctuated_word': 'उन्हें।'}, {'word': 'koi', 'start': 9.434, 'end': 9.664, 'confidence': 0.99, 'punctuated_word': 'कोई'}, {'word': 'unhein', 'start': 9.664, 'end': 9.894, 'confidence': 0.99, 'punctuated_word': 'उन्हें'}, {'word': 'hara', 'start': 9.954, 'end': 10.244, 'confidence': 0.99, 'punctuated_word': 'हरा'}, {'word': 'nahin', 'start': 10.244, 'end': 10.474, 'confidence': 0.99, 'punctuated_word': 'नहीं'}, {'word': 'sakta', 'start': 10.474, 'end': 10.774, 'confidence': 0.99, 'punctuated_word': 'सकता'}, {'word': 'tha', 'start': 10.774, 'end': 11.004, 'confidence': 0.99, 'punctuated_word': 'था।'}, {'word': 'lekin', 'start': 11.424, 'end': 11.734, 'confidence': 0.99, 'punctuated_word': 'लेकिन'}, {'word': 'unki', 'start': 11.784, 'end': 11.994, 'confidence': 0.99, 'punctuated_word': 'उनकी'}, {'word': 'ek', 'start': 12.024, 'end': 12.164, 'confidence': 0.99, 'punctuated_word': 'एक'}, {'word': 'pratigya', 'start': 12.194, 'end': 12.654, 'confidence': 0.99, 'punctuated_word': 'प्रतिज्ञा'}, {'word': 'thi', 'start': 12.654, 'end': 12.904, 'confidence': 0.99, 'punctuated_word': 'थी,'}, {'word': 'wo', 'start': 13.074, 'end': 13.224, 'confidence': 0.99, 'punctuated_word': 'वो'}, {'word': 'kisi', 'start': 13.264, 'end': 13.504, 'confidence': 0.99, 'punctuated_word': 'किसी'}, {'word': 'stri', 'start': 13.534, 'end': 13.774, 'confidence': 0.99, 'punctuated_word': 'स्त्री'}, {'word': 'ya', 'start': 13.774, 'end': 13.894, 'confidence': 0.99, 'punctuated_word': 'या'}, {'word': 'napunsak', 'start': 13.924, 'end': 14.344, 'confidence': 0.98, 'punctuated_word': 'नपुंसक'}, {'word': 'par', 'start': 14.344, 'end': 14.514, 'confidence': 0.99, 'punctuated_word': 'पर'}, {'word': 'shastra', 'start': 14.514, 'end': 14.844, 'confidence': 0.99, 'punctuated_word': 'शास्त्र'}, {'word': 'nahin', 'start': 14.844, 'end': 15.064, 'confidence': 0.99, 'punctuated_word': 'नहीं'}, {'word': 'uthayenge', 'start': 15.064, 'end': 15.544, 'confidence': 0.99, 'punctuated_word': 'उठाएंगे।'}, {'word': 'aur', 'start': 15.824, 'end': 16.004, 'confidence': 0.99, 'punctuated_word': 'और'}, {'word': 'phir', 'start': 16.044, 'end': 16.304, 'confidence': 0.99, 'punctuated_word': 'फिर,'}, {'word': 'Kurukshetra', 'start': 16.504, 'end': 17.024, 'confidence': 0.99, 'punctuated_word': 'कुरुक्षेत्र'}, {'word': 'ke', 'start': 17.024, 'end': 17.154, 'confidence': 0.99, 'punctuated_word': 'के'}, {'word': 'maidan', 'start': 17.154, 'end': 17.504, 'confidence': 0.99, 'punctuated_word': 'मैदान'}, {'word': 'mein', 'start': 17.504, 'end': 17.654, 'confidence': 0.99, 'punctuated_word': 'में'}, {'word': 'aaye', 'start': 17.654, 'end': 17.844, 'confidence': 0.99, 'punctuated_word': 'आए'}, {'word': 'Shikhandi', 'start': 17.844, 'end': 18.474, 'confidence': 0.99, 'punctuated_word': 'शिखंडी।'}, {'word': 'pehchante', 'start': 18.994, 'end': 19.404, 'confidence': 0.99, 'punctuated_word': 'पहचानते'}, {'word': 'the', 'start': 19.404, 'end': 19.534, 'confidence': 0.99, 'punctuated_word': 'थे'}, {'word': 'Bhishma', 'start': 19.534, 'end': 20.034, 'confidence': 0.98, 'punctuated_word': 'भीष्मा,'}, {'word': 'yeh', 'start': 20.294, 'end': 20.514, 'confidence': 0.97, 'punctuated_word': 'यह'}, {'word': 'Amba', 'start': 20.514, 'end': 20.804, 'confidence': 0.96, 'punctuated_word': 'अंबा'}, {'word': 'hai', 'start': 20.804, 'end': 21.034, 'confidence': 0.98, 'punctuated_word': 'है,'}, {'word': 'pichhle', 'start': 21.264, 'end': 21.574, 'confidence': 0.99, 'punctuated_word': 'पिछले'}, {'word': 'janam', 'start': 21.574, 'end': 21.844, 'confidence': 0.99, 'punctuated_word': 'जन्म'}, {'word': 'ki', 'start': 21.844, 'end': 21.964, 'confidence': 0.99, 'punctuated_word': 'की'}, {'word': 'wo', 'start': 21.964, 'end': 22.114, 'confidence': 0.99, 'punctuated_word': 'वो'}, {'word': 'aatma', 'start': 22.114, 'end': 22.414, 'confidence': 0.99, 'punctuated_word': 'आत्मा'}, {'word': 'jiska', 'start': 22.414, 'end': 22.764, 'confidence': 0.99, 'punctuated_word': 'जिसका'}, {'word': 'apmaan', 'start': 22.764, 'end': 23.114, 'confidence': 0.99, 'punctuated_word': 'अपमान'}, {'word': 'hua', 'start': 23.114, 'end': 23.304, 'confidence': 0.99, 'punctuated_word': 'हुआ'}, {'word': 'tha', 'start': 23.304, 'end': 23.494, 'confidence': 0.99, 'punctuated_word': 'था,'}, {'word': 'ab', 'start': 23.674, 'end': 23.854, 'confidence': 0.99, 'punctuated_word': 'अब'}, {'word': 'ek', 'start': 23.854, 'end': 24.004, 'confidence': 0.99, 'punctuated_word': 'एक'}, {'word': 'naye', 'start': 24.004, 'end': 24.224, 'confidence': 0.99, 'punctuated_word': 'नए'}, {'word': 'roop', 'start': 24.224, 'end': 24.474, 'confidence': 0.99, 'punctuated_word': 'रूप'}, {'word': 'mein', 'start': 24.474, 'end': 24.714, 'confidence': 0.99, 'punctuated_word': 'में।'}, {'word': 'Shikhandi', 'start': 25.134, 'end': 25.544, 'confidence': 0.99, 'punctuated_word': 'शिखंडी'}, {'word': 'ko', 'start': 25.544, 'end': 25.684, 'confidence': 0.99, 'punctuated_word': 'को'}, {'word': 'samne', 'start': 25.684, 'end': 25.974, 'confidence': 0.99, 'punctuated_word': 'सामने'}, {'word': 'dekh', 'start': 25.974, 'end': 26.304, 'confidence': 0.99, 'punctuated_word': 'देख,'}, {'word': 'Bhishma', 'start': 26.374, 'end': 26.674, 'confidence': 0.97, 'punctuated_word': 'भीष्मा'}, {'word': 'ne', 'start': 26.674, 'end': 26.794, 'confidence': 0.99, 'punctuated_word': 'ने'}, {'word': 'apna', 'start': 26.794, 'end': 27.044, 'confidence': 0.99, 'punctuated_word': 'अपना'}, {'word': 'dhanush', 'start': 27.044, 'end': 27.414, 'confidence': 0.99, 'punctuated_word': 'धनुष'}, {'word': 'niche', 'start': 27.414, 'end': 27.704, 'confidence': 0.99, 'punctuated_word': 'नीचे'}, {'word': 'rakh', 'start': 27.704, 'end': 27.884, 'confidence': 0.99, 'punctuated_word': 'रख'}, {'word': 'diya', 'start': 27.884, 'end': 28.174, 'confidence': 0.99, 'punctuated_word': 'दिया।'}, {'word': 'apni', 'start': 28.554, 'end': 28.804, 'confidence': 0.99, 'punctuated_word': 'अपनी'}, {'word': 'pratigya', 'start': 28.834, 'end': 29.244, 'confidence': 0.99, 'punctuated_word': 'प्रतिज्ञा'}, {'word': 'nibhai', 'start': 29.244, 'end': 29.674, 'confidence': 0.99, 'punctuated_word': 'निभाई,'}, {'word': 'apna', 'start': 29.794, 'end': 30.064, 'confidence': 0.99, 'punctuated_word': 'अपना'}, {'word': 'dharm', 'start': 30.064, 'end': 30.604, 'confidence': 0.87, 'punctuated_word': 'धर्म'}, {'word': 'nibhaaya', 'start': 30.604, 'end': 30.894, 'confidence': 0.98, 'punctuated_word': 'निभाया।'}, {'word': 'aur', 'start': 31.154, 'end': 31.344, 'confidence': 0.99, 'punctuated_word': 'और'}, {'word': 'usi', 'start': 31.344, 'end': 31.554, 'confidence': 0.99, 'punctuated_word': 'उसी'}, {'word': 'pal', 'start': 31.554, 'end': 31.884, 'confidence': 0.98, 'punctuated_word': 'पाल,'}, {'word': 'Arjun', 'start': 31.994, 'end': 32.294, 'confidence': 0.98, 'punctuated_word': 'अर्जुन'}, {'word': 'ne', 'start': 32.294, 'end': 32.414, 'confidence': 0.99, 'punctuated_word': 'ने'}, {'word': 'unhein', 'start': 32.414, 'end': 32.664, 'confidence': 0.99, 'punctuated_word': 'उन्हें'}, {'word': 'baan', 'start': 32.704, 'end': 32.954, 'confidence': 0.99, 'punctuated_word': 'बाण'}, {'word': 'shaiyya', 'start': 32.954, 'end': 33.274, 'confidence': 0.99, 'punctuated_word': 'शैय्या'}, {'word': 'par', 'start': 33.274, 'end': 33.424, 'confidence': 0.99, 'punctuated_word': 'पर'}, {'word': 'lita', 'start': 33.424, 'end': 33.664, 'confidence': 0.99, 'punctuated_word': 'लिटा'}, {'word': 'diya', 'start': 33.664, 'end': 33.934, 'confidence': 0.99, 'punctuated_word': 'दिया।'}, {'word': 'socho', 'start': 34.394, 'end': 34.724, 'confidence': 0.99, 'punctuated_word': 'सोचो'}, {'word': 'zara', 'start': 34.724, 'end': 35.044, 'confidence': 0.99, 'punctuated_word': 'ज़रा।'}, {'word': 'itna', 'start': 35.444, 'end': 35.724, 'confidence': 0.99, 'punctuated_word': 'इतना'}, {'word': 'bada', 'start': 35.724, 'end': 35.974, 'confidence': 0.99, 'punctuated_word': 'बड़ा'}, {'word': 'yoddha', 'start': 35.974, 'end': 36.384, 'confidence': 0.98, 'punctuated_word': 'योद्धा,'}, {'word': 'apne', 'start': 36.524, 'end': 36.734, 'confidence': 0.99, 'punctuated_word': 'अपने'}, {'word': 'hi', 'start': 36.734, 'end': 36.844, 'confidence': 0.99, 'punctuated_word': 'ही'}, {'word': 'vachan', 'start': 36.844, 'end': 37.164, 'confidence': 0.99, 'punctuated_word': 'वचन'}, {'word': 'se', 'start': 37.164, 'end': 37.304, 'confidence': 0.99, 'punctuated_word': 'से'}, {'word': 'bandh', 'start': 37.304, 'end': 37.574, 'confidence': 0.99, 'punctuated_word': 'बंध'}, {'word': 'gaya', 'start': 37.574, 'end': 37.864, 'confidence': 0.99, 'punctuated_word': 'गया।'}, {'word': 'zindagi', 'start': 38.324, 'end': 38.704, 'confidence': 0.99, 'punctuated_word': 'ज़िंदगी'}, {'word': 'mein', 'start': 38.704, 'end': 38.854, 'confidence': 0.99, 'punctuated_word': 'में'}, {'word': 'hum', 'start': 38.854, 'end': 39.044, 'confidence': 0.99, 'punctuated_word': 'हम'}, {'word': 'bhi', 'start': 39.044, 'end': 39.194, 'confidence': 0.99, 'punctuated_word': 'भी'}, {'word': 'to', 'start': 39.194, 'end': 39.334, 'confidence': 0.98, 'punctuated_word': 'तो'}, {'word': 'kabhi', 'start': 39.334, 'end': 39.584, 'confidence': 0.99, 'punctuated_word': 'कभी'}, {'word': 'kabhi', 'start': 39.584, 'end': 39.844, 'confidence': 0.99, 'punctuated_word': 'कभी'}, {'word': 'apne', 'start': 39.844, 'end': 40.124, 'confidence': 0.99, 'punctuated_word': 'अपने'}, {'word': 'hi', 'start': 40.124, 'end': 40.234, 'confidence': 0.99, 'punctuated_word': 'ही'}, {'word': 'banaye', 'start': 40.234, 'end': 40.584, 'confidence': 0.99, 'punctuated_word': 'बनाए'}, {'word': 'usoolon', 'start': 40.584, 'end': 40.954, 'confidence': 0.97, 'punctuated_word': 'उसूलों'}, {'word': 'mein', 'start': 40.954, 'end': 41.154, 'confidence': 0.99, 'punctuated_word': 'में,'}, {'word': 'apni', 'start': 41.334, 'end': 41.544, 'confidence': 0.99, 'punctuated_word': 'अपनी'}, {'word': 'hi', 'start': 41.544, 'end': 41.644, 'confidence': 0.99, 'punctuated_word': 'ही'}, {'word': 'zid', 'start': 41.644, 'end': 41.854, 'confidence': 0.99, 'punctuated_word': 'ज़िद'}, {'word': 'mein', 'start': 41.854, 'end': 42.024, 'confidence': 0.99, 'punctuated_word': 'में'}, {'word': 'aise', 'start': 42.024, 'end': 42.254, 'confidence': 0.99, 'punctuated_word': 'ऐसे'}, {'word': 'hi', 'start': 42.254, 'end': 42.384, 'confidence': 0.99, 'punctuated_word': 'ही'}, {'word': 'phans', 'start': 42.384, 'end': 42.634, 'confidence': 0.99, 'punctuated_word': 'फंस'}, {'word': 'jaate', 'start': 42.634, 'end': 42.884, 'confidence': 0.99, 'punctuated_word': 'जाते'}, {'word': 'hain', 'start': 42.884, 'end': 43.034, 'confidence': 0.99, 'punctuated_word': 'हैं'}, {'word': 'na', 'start': 43.034, 'end': 43.234, 'confidence': 0.99, 'punctuated_word': 'ना?'}, {'word': 'kya', 'start': 43.684, 'end': 43.874, 'confidence': 0.99, 'punctuated_word': 'क्या'}, {'word': 'koi', 'start': 43.924, 'end': 44.154, 'confidence': 0.99, 'punctuated_word': 'कोई'}, {'word': 'aisi', 'start': 44.274, 'end': 44.524, 'confidence': 0.99, 'punctuated_word': 'ऐसी'}, {'word': 'pratigya', 'start': 44.524, 'end': 44.974, 'confidence': 0.99, 'punctuated_word': 'प्रतिज्ञा'}, {'word': 'hai', 'start': 44.974, 'end': 45.124, 'confidence': 0.99, 'punctuated_word': 'है'}, {'word': 'jo', 'start': 45.194, 'end': 45.364, 'confidence': 0.99, 'punctuated_word': 'जो'}, {'word': 'aapko', 'start': 45.414, 'end': 45.724, 'confidence': 0.99, 'punctuated_word': 'आपको'}, {'word': 'aage', 'start': 45.804, 'end': 46.064, 'confidence': 0.99, 'punctuated_word': 'आगे'}, {'word': 'badhne', 'start': 46.064, 'end': 46.344, 'confidence': 0.99, 'punctuated_word': 'बढ़ने'}, {'word': 'se', 'start': 46.344, 'end': 46.504, 'confidence': 0.99, 'punctuated_word': 'से'}, {'word': 'rok', 'start': 46.504, 'end': 46.734, 'confidence': 0.99, 'punctuated_word': 'रोक'}, {'word': 'rahi', 'start': 46.734, 'end': 46.944, 'confidence': 0.99, 'punctuated_word': 'रही'}, {'word': 'hai', 'start': 46.944, 'end': 47.114, 'confidence': 0.99, 'punctuated_word': 'है?'}, {'word': 'apne', 'start': 47.424, 'end': 47.654, 'confidence': 0.99, 'punctuated_word': 'अपने'}, {'word': 'dil', 'start': 47.654, 'end': 47.854, 'confidence': 0.99, 'punctuated_word': 'दिल'}, {'word': 'se', 'start': 47.854, 'end': 48.004, 'confidence': 0.99, 'punctuated_word': 'से'}, {'word': 'pucho', 'start': 48.004, 'end': 48.344, 'confidence': 0.99, 'punctuated_word': 'पूछो'}, {'word': 'aur', 'start': 48.514, 'end': 48.694, 'confidence': 0.99, 'punctuated_word': 'और'}, {'word': 'comment', 'start': 48.694, 'end': 49.024, 'confidence': 0.98, 'punctuated_word': 'कमेंट'}, {'word': 'mein', 'start': 49.024, 'end': 49.164, 'confidence': 0.99, 'punctuated_word': 'में'}, {'word': 'zaroor', 'start': 49.164, 'end': 49.474, 'confidence': 0.99, 'punctuated_word': 'ज़रूर'}, {'word': 'batana', 'start': 49.474, 'end': 49.904, 'confidence': 0.99, 'punctuated_word': 'बताना।'}], 'images_manifest': [{'start': '00:00', 'duration': '00:04', 'text': 'Doston, kabhi socha hai ki aapki sabse badi taakat hi aapki kamzori kaise ban sakti hai?', 'url': 'output/images/segment_1.png', 'source': 'Gemini', 'prompt': "A photorealistic digital painting in 8K resolution, vertical format (1080x1920). The scene depicts a close-up, dramatic portrait of Pitamah Bhishma on the Kurukshetra battlefield, but instead of showing a full battle scene, focus on his face and upper torso. Bhishma is an aged warrior, yet his face retains a regal quality despite the weariness and conflict visible in his eyes. His silver beard is long and meticulously groomed, catching the light. He wears ornate golden armor, slightly battle-worn with realistic scratches and dirt.\n\nThe focus is intensely on Bhishma's face, conveying a profound sense of internal conflict and resignation. His eyes, though aged, are sharp and intelligent, reflecting a deep understanding of the situation. A single tear streaks down his weathered cheek. Shikhandi is subtly visible in the extreme background, blurred beyond recognition, representing the cause of Bhishma's internal turmoil.\n\nCinematic rim lighting highlights the contours of his face and armor, separating him from the blurred background. Volumetric lighting illuminates subtle dust particles floating in the air around him, adding depth and atmosphere. The color palette is dominated by golds, browns, and greys, with subtle hints of red in the background suggesting the aftermath of battle. Rich color grading enhances the contrast and depth of the image.\n\nHyper-realistic textures are crucial: the metal of the armor should have microscopic scratches and imperfections, the beard should have individual strands visible, and the skin should show realistic pores and wrinkles. Subtle lens effects like chromatic aberration around the brightest highlights and a faint lens flare add to the photorealistic feel.\n\nReflections of the distant battle can be subtly seen in the polished surfaces of his armor, adding another layer of depth. Shadows are realistically cast across his face, emphasizing the contours and conveying his internal struggle. Ambient occlusion creates realistic contact shadows where his armor meets his skin.\n\nThe overall mood is one of solemnity, regret, and acceptance. The composition is dynamic, with Bhishma's gaze directed slightly off-center, drawing the viewer's eye into the scene. Ray-traced lighting creates realistic reflections and refractions, enhancing the photorealistic rendering. Subtly add volumetric fog in the background to further separate Bhishma from the battle. The depth of field is shallow, blurring the background and emphasizing the sharpness of Bhishma's face. There should be no text or words in the image."}, {'start': '00:04', 'duration': '00:04', 'text': 'Mahabharat yaad hai? Pitamah Bhishma, ichha mrityu ka vardaan tha unhe.', 'url': 'output/images/segment_2.png', 'source': 'Gemini', 'prompt': "Vertical 1080x1920 still image. Epic scene from the Mahabharata. Pitamah Bhishma, a towering figure, stands resolutely on a vibrant, war-torn Kurukshetra battlefield. He is clad in shining, intricately detailed golden armor, reflecting the warm, setting sun. His face is etched with a mixture of determination and inner turmoil, showcasing deep wrinkles and a stern expression. Before him stands Shikhandi, partially obscured by a swirling cloud of dust and smoke. Use volumetric lighting to backlight Shikhandi, creating a silhouette effect. Bhishma's hand is slowly lowering his golden bow, the gesture communicating resignation and adherence to his vow. The foreground is filled with realistically rendered, blood-stained earth and broken weapons. The background features a vast, chaotic battlefield with distant armies clashing under a dramatic, orange-hued sky. Implement a shallow depth of field, blurring the background to focus attention on Bhishma and Shikhandi. The overall mood is somber and reflective, emphasizing the tragic nature of Bhishma's predicament. Employ cinematic lighting techniques, including rim lighting to highlight Bhishma's silhouette against the chaotic background and subtle lens flare emanating from the setting sun. Use hyper-realistic digital art style, 8K resolution, with crystal clear details. Photorealistic textures and materials with microscopic details on the armor and clothing. Include subtle chromatic aberration around the edges of bright objects for realism. Implement ray-traced lighting effects for photorealistic rendering. Add subtle atmospheric elements like dust particles and volumetric fog to enhance depth and atmosphere. Rich color grading with complementary colors (gold/orange vs blue/grey) and HDR-like contrast."}, {'start': '00:08', 'duration': '00:07', 'text': 'Koi unhe hara nahi sakta tha. Lekin unki ek pratigya thi, woh kisi stri ya napunsak par shastra nahi uthayenge.', 'url': 'output/images/segment_3.png', 'source': 'Gemini', 'prompt': 'Vertical 1080x1920 portrait image: A dramatic, hyper-realistic digital painting depicting a climactic moment from the Mahabharata, focusing on Bhishma and Shikhandi on the Kurukshetra battlefield. Bhishma, the grand patriarch, stands tall and resolute, clad in intricately detailed golden armor, etched with ancient symbols and battle scars. His face, weathered and stoic, shows a hint of inner turmoil. He is visibly lowering his golden bow, his grip loosening, his expression conveying profound resignation. Opposite him stands Shikhandi, appearing androgynous and fierce, radiating a palpable aura of righteous anger and determination. Shikhandi is adorned in vibrant, contrasting colored armor, with intricate detailing and flowing fabrics that suggest movement. The background showcases a chaotic battlefield, rendered with photorealistic detail – scattered weapons, fallen warriors, dust clouds swirling in the air, and distant armies clashing under a fiery sunset sky. Employ cinematic lighting: a strong rim light from the setting sun highlights Bhishma’s silhouette, separating him from the background, while volumetric lighting filters through the dust clouds, creating a sense of depth and atmosphere. Use a shallow depth of field to focus sharply on Bhishma and Shikhandi, blurring the background chaos slightly. The art style should be hyper-realistic, crystal clear with 8K resolution, focusing on photorealistic textures and materials – the gleam of metal, the texture of fabric, the dust on skin. Implement subtle lens effects like chromatic aberration and lens flare to enhance realism. Include strategic reflections on the armor, shadows cast by the setting sun, and ambient occlusion to add dimensional realism. The color grading should be rich and vibrant, with complementary color schemes – perhaps warm tones for Bhishma and cooler tones for Shikhandi – and HDR-like contrast. Ray-traced lighting effects should be used for photorealistic rendering. Add subtle atmospheric elements like particles of dust and volumetric fog to enhance the sense of depth and scale. The overall composition should be dynamic, with a strong focal point on the interaction between Bhishma and Shikhandi, creating a visually compelling and emotionally resonant image. No text or words are to be included in the image.'}, {'start': '00:15', 'duration': '00:04', 'text': 'Aur phir Kurukshetra ke maidan mein aaye Shikhandi. Pehchante the Bhishma,', 'url': 'output/images/segment_4.png', 'source': 'Gemini', 'prompt': "Vertical 1080x1920, ultra-detailed hyperrealistic digital painting, 8K resolution: A wide shot depicting Shikhandi entering the Kurukshetra battlefield. Shikhandi, a warrior with androgynous features, clad in shining, ornate armor reflecting the fiery sunset, rides a magnificent war chariot pulled by two white steeds, their manes flowing dramatically. Behind Shikhandi, a swirling vortex of dust and fog obscures the rest of the Pandava army, creating a sense of depth and scale. In the foreground, Pitamah Bhishma stands resolute, his white beard flowing in the wind, his ancient, wise eyes filled with a profound inner conflict. He is bathed in a dramatic rim light that highlights the sorrow etched on his face. Bhishma's hand gently lowers his Gandiva bow, signaling his surrender. The battlefield is littered with broken chariots, discarded weapons, and the fallen. Use volumetric lighting to create god rays piercing through the dust clouds, adding to the epic scale. Employ a shallow depth of field, blurring the background army while keeping Shikhandi and Bhishma in sharp focus. Implement chromatic aberration and subtle lens flare effects emanating from the setting sun. The color palette consists of warm oranges, reds, and yellows for the sunset, contrasted with the cool blues and grays of the battlefield. Add realistic textures to the armor, clothing, and skin, emphasizing microscopic details. Enhance the realism with ray-traced lighting, realistic shadows, and ambient occlusion. Subtle particles of dust float in the air, adding to the atmosphere. Color grade for HDR-like contrast and vibrant colors. No text or words."}, {'start': '00:19', 'duration': '00:05', 'text': 'yeh Amba hai, pichle janam ki woh aatma jiska apmaan hua tha, ab ek naye roop mein.', 'url': 'output/images/segment_5.png', 'source': 'Gemini', 'prompt': "Vertical 1080x1920 portrait image: Hyper-realistic digital art depicting Shikhandi on the Kurukshetra battlefield, embodying Amba's reincarnation. The scene focuses on Shikhandi's face, a determined and resolute expression etched upon it. Shikhandi is depicted as androgynous, with a strong jawline, flowing dark hair partly obscuring one eye, and a serene yet fierce gaze directed slightly upwards. Dressed in intricately detailed, battle-worn warrior attire – a mix of bronze and leather armor with subtle embellishments. Focus on the texture of the armor showing scratches, dents, and wear. The background is a blurred battlefield scene filled with dust, smoke, and indistinct figures of warriors and chariots. Volumetric fog hangs low to the ground, illuminated by the setting sun. The key light is a dramatic rim light from the right, highlighting the contours of Shikhandi's face and armor, separating them from the chaos behind. Subtle chromatic aberration around the brightest highlights. A soft, warm fill light from the left creates a balanced contrast. Use strategic depth of field to keep Shikhandi's face razor-sharp while the background remains blurred. Rich color grading, with complementary colors of orange and teal. HDR-like contrast, emphasizing the highlights and shadows. Photorealistic textures and materials, with microscopic details visible on the armor and skin. Dynamic composition with Shikhandi positioned slightly off-center, creating visual flow towards the blurred battlefield. Subtle lens flare near the rim light. Reflections visible on the polished parts of the armor. Shadows are soft and diffused, adding depth to the scene. Ambient occlusion enhances the dimensional realism of the character and the environment. Ray-traced lighting effects for photorealistic rendering. Particles of dust and smoke floating in the air, catching the light and adding to the atmosphere. 8K resolution, crystal clear details. Avoid any text."}, {'start': '00:24', 'duration': '00:06', 'text': 'Shikhandi ko saamne dekh, Bhishma ne apna dhanush neeche rakh diya. Apni pratigya nibhai,', 'url': 'output/images/segment_6.png', 'source': 'Gemini', 'prompt': "A photorealistic, ultra-detailed digital painting in vertical format (1080x1920) depicting a pivotal moment from the Mahabharata: Bhishma facing Shikhandi on the Kurukshetra battlefield. Bhishma, a towering figure with a long, flowing white beard and clad in golden, battle-worn armor, lowers his bow with a look of profound inner conflict etched onto his face. His armor is intricately detailed, showing scratches, dents, and dust from the battle. Shikhandi, a figure of androgynous beauty, stands opposite him, holding a bow and arrow with unwavering resolve. Shikhandi is adorned in vibrant, colorful armor, contrasting with Bhishma's more muted tones. Volumetric fog hangs low to the ground, partially obscuring the carnage of the battlefield in the background, which includes broken chariots, fallen warriors, and distant flames. The scene is lit dramatically with rim lighting highlighting Bhishma's silhouette against the smoky sky, and a subtle lens flare emanating from the rising sun. Ray-traced lighting creates realistic reflections on the armor and weapons. Depth of field is shallow, blurring the background to emphasize the emotional tension between Bhishma and Shikhandi. Photorealistic textures are visible on the skin, armor, and clothing, with microscopic details adding to the realism. A complementary color scheme of gold, crimson, and deep blues creates a rich, cinematic feel. Subtle chromatic aberration adds to the photorealistic effect. Ambient occlusion deepens the shadows, adding to the sense of depth and drama. The composition is dynamic, with a strong diagonal line leading the viewer's eye from Shikhandi to Bhishma. The style is hyper-realistic digital art with crystal-clear details and 8K resolution, suitable for a modern tech aesthetic. No text or words are visible in the image."}, {'start': '00:30', 'duration': '00:04', 'text': 'apna dharm nibhaya. Aur usi pal, Arjun ne unhe baan shaiyya par lita diya.', 'url': 'output/images/segment_7.png', 'source': 'Gemini', 'prompt': "Vertical (1080x1920) cinematic shot depicting the moment Arjun strikes Bhishma with arrows, creating a 'baan shaiyya' (bed of arrows). Focus sharply on Bhishma, an aged warrior in golden armor, lying on a dense bed of countless arrows piercing the ground and slightly raised to cradle his body. His face expresses a mixture of pain, acceptance, and serene resignation. His eyes are open, gazing slightly upwards. Arjun, a youthful, powerful warrior, stands in the background, slightly blurred by depth of field, his bow still drawn, an arrow just released. He is partially obscured by dust and smoke from the battlefield.\n\nThe scene is set on the Kurukshetra battlefield, rendered in hyper-realistic detail. Ground is churned earth, littered with broken weapons and armor fragments. A faint mist hangs in the air, adding to the drama.\n\nLighting is dramatic and cinematic. A strong rim light from the right highlights the edges of Bhishma's armor and the arrowheads, creating a halo effect. Volumetric lighting pierces through the smoke and dust, creating god rays that illuminate Bhishma. The overall mood is somber and reflective.\n\nStyle is hyper-realistic digital art, 8K resolution, with crystal-clear details. Use photorealistic textures for the armor, skin, and battlefield elements, with microscopic details visible.\n\nColor grading should be rich and complementary, using warm tones for the light and cool tones for the shadows, creating an HDR-like contrast. Employ subtle lens effects like chromatic aberration and lens flare to enhance realism.\n\nReflections and shadows should be meticulously rendered, with ambient occlusion adding depth and dimension. Ray-traced lighting effects are essential for photorealistic rendering.\n\nThe composition is dynamic, with a strong focal point on Bhishma's face. The arrows create strong leading lines that draw the eye towards him. Subtle particles of dust and smoke float in the air, adding to the atmospheric depth. The background battlefield is slightly blurred, emphasizing the central figures."}, {'start': '00:34', 'duration': '00:04', 'text': 'Socho zara. Itna bada yoddha apne hi vachan se bandh gaya.', 'url': 'output/images/segment_8.png', 'source': 'Gemini', 'prompt': "Vertical 1080x1920. A close-up, highly detailed, photorealistic digital painting depicting the face of Pitamah Bhishma in the Kurukshetra battlefield. His face is weathered and etched with the fatigue of war, showing deep lines around his eyes and mouth. His eyes, though still holding a trace of immense power, are filled with a profound sadness and resignation. He is wearing intricately detailed, battle-worn golden armor, reflecting the muted colors of the battlefield. A single tear rolls down his cheek, catching the light. In the blurred background, Shikhandi stands partially obscured by volumetric fog, a figure of ambiguous gender, holding a bow but not aiming. The immediate background around Bhishma is dark and gritty, with subtle dust particles floating in the air. Rim lighting from the side highlights the details of his armor and face, separating him from the background. The overall mood is somber and melancholic. Use ray-traced lighting for realistic rendering of the metallic armor and skin textures. Subtle chromatic aberration around the bright highlights and a gentle lens flare add to the cinematic feel. Depth of field is shallow, focusing sharply on Bhishma's face and blurring the background elements. Color grading should lean towards a complementary scheme of gold and desaturated blues/greens to evoke a sense of loss and impending doom. The scene is rendered in 8K resolution with hyper-realistic textures, showing microscopic details like pores on the skin and scratches on the armor. Ambient occlusion and realistic shadows enhance the three-dimensionality. The composition is dynamic, drawing the viewer's eye to Bhishma's tearful face. A sense of weight and stillness should permeate the image, capturing the moment of his voluntary surrender. Avoid any text or words in the image."}, {'start': '00:38', 'duration': '00:05', 'text': 'Zindagi mein hum bhi toh kabhi kabhi apne hi banaye usoolon mein, apni hi zid mein aise hi phas jaate hain na?', 'url': 'output/images/segment_9.png', 'source': 'Gemini', 'prompt': "Vertical 1080x1920 portrait. Hyper-realistic digital art, 8K resolution. A close-up shot focusing on a modern, stylized interpretation of a person trapped within a fragmented glass cage. The person inside, gender-neutral, displays an expression of subtle frustration and introspection, not overt distress. The glass fragments are arranged in a way that suggests both confinement and self-imposed construction. The background is a blurred, abstract cityscape at twilight, subtly visible through the fractured glass, hinting at opportunities missed or paths not taken. Cinematic lighting: soft, volumetric light streams from behind the person, casting long, dramatic shadows within the cage. Rim lighting highlights the edges of the glass fragments, emphasizing their sharpness and the person's silhouette. Color grading: a complementary color scheme of deep blues and oranges, with HDR-like contrast. The cityscape in the background should have a cool blue tone, while the light illuminating the person should have a warm orange glow. Photorealistic textures: The glass should have subtle imperfections, scratches, and reflections. The person's skin should have photorealistic details, including pores and subtle wrinkles. Dynamic composition: The person is positioned slightly off-center, with their gaze directed towards the viewer, creating a sense of connection. Depth of field: the focus is sharply on the person's face and the closest glass fragments, with the background and the rest of the cage slightly blurred. Subtle lens effects: slight chromatic aberration around the edges of the glass fragments and a very subtle lens flare from the light source behind. Reflections and shadows should be realistically rendered using ray-traced lighting effects, with ambient occlusion adding depth and dimension. Atmospheric elements: subtle volumetric fog within the cage, adding a sense of depth and mystery. The overall mood is thoughtful and contemplative, suggesting the internal struggle of being bound by self-imposed rules. The image should evoke a sense of quiet intensity and introspection, prompting viewers to consider their own self-imposed limitations."}, {'start': '00:43', 'duration': '00:06', 'text': 'Kya koi aisi pratigya hai jo aapko aage badhne se rok rahi hai? Apne dil se poocho aur comment mein zaroor batana.', 'url': 'output/images/segment_10.png', 'source': 'Gemini', 'prompt': "Vertical format image, 1080x1920, ultra-detailed, hyper-realistic digital art, 8K resolution. Depict a close-up, emotionally charged scene inspired by the Mahabharata episode of Bhishma's downfall, focusing on the moment of realization and internal conflict. The primary subject is the face of an older, regal warrior, etched with lines of wisdom and regret. He is clad in ornate, battle-worn golden armor reflecting the warm light of the setting sun. His eyes, though aged, are sharp and filled with a mix of determination and profound sadness. He gazes downwards, suggesting introspection.\n\nSubtly behind him, slightly out of focus to create depth of field, is a blurred, ethereal figure representing Shikhandi, barely discernible as a warrior. This blurred figure should not be the main focus but should be recognizable as human and a warrior.\n\nLighting: Dramatic cinematic lighting with a strong rim light illuminating the warrior's right side, highlighting the texture of his armor and the lines on his face. Volumetric lighting creates god rays cutting through a subtle, hazy battlefield atmosphere in the background. The overall mood is somber and reflective.\n\nColor Palette: Rich, complementary color scheme using golds, browns, and deep blues. HDR-like contrast enhances the details and emotional impact.\n\nTextures: Photorealistic textures with microscopic details on the armor, skin, and hair. Show wear and tear on the armor to convey age and experience.\n\nComposition: Dynamic composition with the warrior's face slightly off-center, drawing the viewer's eye. Strategic depth of field keeps the warrior's face in sharp focus while subtly blurring the background and the figure of Shikhandi.\n\nLens Effects: Subtle chromatic aberration and lens flare around the rim light add realism.\n\nReflections, Shadows, and Ambient Occlusion: Realistic reflections on the polished armor, deep shadows that emphasize the contours of the face, and ambient occlusion that grounds the subject in the environment.\n\nRay-Traced Lighting: Use ray-traced lighting effects for photorealistic rendering of the light and shadows.\n\nAtmospheric Elements: Subtle particles of dust and volumetric fog in the background add depth and atmosphere.\n\nStyle: Modern, professional aesthetic suitable for tech content, avoiding any overtly fantastical or cartoonish elements. The overall feeling should be one of profound respect and solemnity. No text or words."}]}
    result = create_video_with_overlays(state)
    print(result)