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
            
            # Position each clip in the center of the screen
            # No need to reposition as we're already setting position to center in create_word_by_word_clips
            text_overlays.extend(word_clips)
        
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
    state = {'topic': "Arjuna's celestial weapons and how he acquired them from gods", 'script': {'videoScript': [{'start': '00:00', 'duration': '00:07', 'text': 'Arre yaar, Mahabharat ke Arjun pata hai na? Main bahut excited hoon aapko unke celestial weapons ke baare mein batane ke liye.'}, {'start': '00:07', 'duration': '00:07', 'text': 'Socho zara, Arjun ke paas kitne amazing weapons the? Gandiv bow toh legend hai, hai na? Lekin Pashupatastra.'}, {'start': '00:14', 'duration': '00:05', 'text': 'Arre bhai woh toh Lord Shiva se mila tha. Kya penance kiya tha Arjun ne? Kamaal!'}, {'start': '00:19', 'duration': '00:04', 'text': 'Indra se bhi weapons mile. Indralok mein training bhi hui. Kya baat hai!'}, {'start': '00:23', 'duration': '00:04', 'text': 'Agneyastra, Varunastra, Power, high power! Lekin yeh weapons aaye kaise?'}, {'start': '00:27', 'duration': '00:04', 'text': 'Devtaaon ne unhe kyun diye? Is question ka answer chahiye?'}, {'start': '00:31', 'duration': '00:06', 'text': 'Toh jaldi se subscribe karo aur comment mein batao ki Arjun ka kaunsa weapon aapko sabse zyada pasand hai?'}], 'totalDuration': '00:36'}, 'title': "🤯Arjuna's Secret Weapons REVEALED! #Mahabharat #Mythology", 'description': "OMG! Arjuna's celestial weapons are INSANE! 🔥 Gandiva & Pashupatastra! Which is your fave? 🤔 Subscribe & comment! 👇 #Arjuna #Hinduism #Shorts", 'thumbnail_url': 'https://avatars.githubusercontent.com/u/91617309?v=4', 'audio_path': 'output/audios/audio_1743451794.334516.mp3', 'images_manifest': [{'start': '00:00', 'duration': '00:07', 'text': 'Arre yaar, Mahabharat ke Arjun pata hai na? Main bahut excited hoon aapko unke celestial weapons ke baare mein batane ke liye.', 'url': 'output/images/segment_1.png', 'source': 'Gemini', 'prompt': "A hyper-realistic, 8K resolution digital art portrait (1080x1920, vertical) depicting Arjuna from the Mahabharata bathed in celestial light. Arjuna is not a direct depiction but a symbolic representation. Imagine a strong, athletic, youthful male figure, his skin radiating a subtle golden luminescence, clad in intricately detailed, ancient Indian warrior armor, but reimagined with a futuristic, high-tech aesthetic. The armor is crafted from a shimmering, otherworldly metal, engraved with glowing Sanskrit runes. He stands against a backdrop of swirling cosmic nebulae, rendered with breathtaking realism and depth.\n\nHis right hand is outstretched, emanating a vibrant beam of pure energy, suggesting the power of a celestial weapon. This energy beam is intensely bright near his hand, gradually diffusing into a soft, ethereal glow as it extends into the cosmic background. Subtle, almost imperceptible lens flares emanate from the energy source, adding to the otherworldly feel.\n\nThe lighting is dramatic and cinematic, employing rim lighting to highlight the contours of his armor and physique, separating him from the complex background. Volumetric lighting creates visible shafts of light piercing through the nebulae, enhancing the sense of depth and scale. The overall mood is one of power, grace, and divine connection.\n\nThe color palette is rich and vibrant, utilizing complementary colors like deep blues and golds to create visual harmony. HDR-like contrast adds to the dynamic range, making the image pop. Photorealistic textures are crucial – the armor should appear metallic and worn, reflecting the light in a realistic manner. Subtle chromatic aberration around the brightest highlights adds a touch of realism.\n\nStrategic depth of field blurs the cosmic background slightly, keeping Arjuna as the primary focal point. Ray-traced lighting effects provide realistic reflections and shadows, adding depth and dimension. Subtle atmospheric elements, such as particles of stardust and volumetric fog, further enhance the sense of realism and depth. Ambient occlusion creates realistic shadowing in the crevices of the armor. The composition is dynamic, with a strong focal point on Arjuna’s outstretched hand and the emanating energy, drawing the viewer's eye."}, {'start': '00:07', 'duration': '00:07', 'text': 'Socho zara, Arjun ke paas kitne amazing weapons the? Gandiv bow toh legend hai, hai na? Lekin Pashupatastra.', 'url': 'output/images/segment_2.png', 'source': 'Gemini', 'prompt': "A vertical portrait image, 1080x1920. Hyper-realistic digital art, 8K resolution. Arjuna, the legendary warrior from the Mahabharata, stands in a majestic, otherworldly realm. He is depicted as a young, powerful warrior, clad in intricately detailed golden armor, reflecting the ethereal light around him. He holds the Gandiva bow, its design ornate and powerful, radiating a soft, celestial glow. Behind him, a swirling vortex of cosmic energy manifests, hinting at the divine power of the Pashupatastra. The background should consist of a breathtaking landscape of floating islands and celestial formations, bathed in the light of multiple distant suns. The lighting is dramatic, with strong rim lighting highlighting Arjuna's form and volumetric lighting creating depth and atmosphere within the cosmic vortex. The mood is awe-inspiring and powerful. The style is modern, professional, and cinematic, suitable for tech content. Focus should be on photorealistic textures and materials, with microscopic details visible on Arjuna's armor and the Gandiva bow. Strategic depth of field effects should blur the background slightly, bringing Arjuna and the Gandiva bow into sharp focus. Rich color grading with complementary color schemes of gold, blue, and purple, creates an HDR-like contrast. Subtle lens effects like chromatic aberration and lens flare add to the realism. Reflections and shadows enhance the dimensional realism. Ray-traced lighting effects create a photorealistic rendering. Atmospheric elements like particles and volumetric fog add depth and mystery to the scene. Dynamic composition with a strong focal point on Arjuna and the Gandiva bow, guiding the viewer's eye through the image. Avoid any text or words in the image."}, {'start': '00:14', 'duration': '00:05', 'text': 'Arre bhai woh toh Lord Shiva se mila tha. Kya penance kiya tha Arjun ne? Kamaal!', 'url': 'output/images/segment_3.png', 'source': 'Gemini', 'prompt': "Vertical 1080x1920 hyperrealistic digital art of Arjuna in deep meditation, having just received Pashupatastra from Lord Shiva. Arjuna, youthful and muscular, sits cross-legged on a slightly elevated rocky outcrop in the Himalayas. He is clad in simple, saffron-colored robes, slightly tattered from his penance. His eyes are closed, but a faint glow emanates from his forehead. Lord Shiva stands before him, towering and majestic. Shiva has matted dreadlocks adorned with a crescent moon and a cobra coiled around his neck. His skin is a vibrant blue, and he wears tiger skin around his waist. He holds the Pashupatastra, a divine arrow radiating intense energy, suspended just above Arjuna's outstretched hands. The background features towering, snow-capped Himalayan peaks shrouded in mist. Volumetric fog swirls around the rocks and peaks, creating a sense of depth. Use rim lighting to highlight the contours of Arjuna and Shiva, separating them from the background. Employ volumetric lighting to showcase the beams of light piercing through the mist. The Pashupatastra emits a powerful, ethereal glow that illuminates both figures. The overall mood is one of divine power, reverence, and accomplishment. Rich color grading with complementary colors: blues, oranges, and yellows. HDR-like contrast. Photorealistic textures on the rocks, clothing, and skin, with microscopic details visible. Dynamic composition with a strong focal point on the Pashupatastra and a visual flow leading from Arjuna to Shiva. Subtle lens flare originating from the Pashupatastra's energy. Reflections in the melting snow patches on the rocks. Shadows cast by the mountains and figures. Ray-traced lighting effects for photorealistic rendering. Subtly incorporate chromatic aberration around the brightest light sources. 8K resolution."}, {'start': '00:19', 'duration': '00:04', 'text': 'Indra se bhi weapons mile. Indralok mein training bhi hui. Kya baat hai!', 'url': 'output/images/segment_4.png', 'source': 'Gemini', 'prompt': "Vertical 1080x1920 portrait image: Hyper-realistic digital art depicting Arjuna, the legendary archer from the Mahabharata, standing in a celestial training ground within Indralok. Arjuna is depicted as a young, athletic warrior, radiating power and determination. He is clad in divine armor, intricately designed with gold and celestial patterns, catching the light. He holds Gandiva, his divine bow, its surface gleaming with an ethereal sheen. In the background, Indralok is visualized as a breathtaking city of gold and crystal, floating amidst swirling clouds and radiant energy. Celestial beings, partially obscured by volumetric fog, are observing Arjuna.\n\nThe lighting is dramatic and cinematic, with a strong rim light illuminating Arjuna from behind, separating him from the background. Volumetric lighting streams through the clouds, creating god rays and adding depth. Use a complementary color scheme of golds, blues, and whites to create visual harmony.\n\nDepth of field is shallow, focusing sharply on Arjuna's face and bow, blurring the background slightly to draw the viewer's eye. Subtle lens flares and chromatic aberration effects add to the realism. Photorealistic textures are crucial – the armor should show microscopic details, the bow should reflect the surrounding light realistically, and the clouds should have a tangible, three-dimensional quality.\n\nRay-traced lighting effects are essential for creating realistic reflections and shadows. Ambient occlusion should be used to ground the figures and add depth to the scene. Particles of light and energy should be subtly swirling around Arjuna, adding to the magical atmosphere. The overall mood should be awe-inspiring and powerful. The composition should lead the eye towards Arjuna, with the background elements providing context and enhancing the feeling of grandeur. 8K resolution, crystal clear details, photorealistic rendering. No text or words in the image."}, {'start': '00:23', 'duration': '00:04', 'text': 'Agneyastra, Varunastra, Power, high power! Lekin yeh weapons aaye kaise?', 'url': 'output/images/segment_5.png', 'source': 'Gemini', 'prompt': "A vertical (1080x1920) digital painting depicting Arjuna, a muscular and handsome warrior with a determined expression, kneeling before a radiant and powerful Lord Indra in his celestial abode. Arjuna is dressed in ornate, golden battle armor, slightly battle-worn but gleaming. Indra, depicted as a regal figure with a flowing beard and divine aura, is extending the Agneyastra towards Arjuna. The Agneyastra glows with intense, swirling flames, rendered with photorealistic textures and vibrant orange and red hues. Behind Indra, a glimpse of his celestial court can be seen, with ethereal beings and architectural details rendered in intricate detail.\n\nThe background should feature a breathtaking landscape of Mount Meru, bathed in golden sunlight, with cascading waterfalls and lush vegetation. Volumetric fog and subtle particles of light should add depth and atmosphere to the scene. The lighting should be dramatic and cinematic, with rim lighting highlighting Arjuna's silhouette and volumetric lighting casting long, dynamic shadows. Employ a rich color grading with complementary colors, emphasizing gold, blue, and fiery orange tones.\n\nThe style should be hyper-realistic digital art with crystal-clear details in 8K resolution. Use strategic depth of field to focus on Arjuna and the Agneyastra, subtly blurring the background elements. Photorealistic textures and materials with microscopic details should be applied to the armor, weapons, and environment. Add subtle lens effects like chromatic aberration and lens flare to enhance realism.\n\nIncorporate reflections, shadows, and ambient occlusion for dimensional realism. Ray-traced lighting effects should be used for photorealistic rendering. The composition should be dynamic, with strong focal points and visual flow leading the viewer's eye. Aim for a modern, professional aesthetic suitable for tech content, avoiding any text or words in the image. The overall mood should be awe-inspiring and powerful, reflecting the significance of Arjuna receiving the Agneyastra."}, {'start': '00:27', 'duration': '00:04', 'text': 'Devtaaon ne unhe kyun diye? Is question ka answer chahiye?', 'url': 'output/images/segment_6.png', 'source': 'Gemini', 'prompt': "Vertical image, 1080x1920. Hyper-realistic digital art of Arjuna, the legendary archer, kneeling reverently before a celestial, otherworldly manifestation of multiple divine weapons. The scene should be set in a shimmering, ethereal realm, perhaps a high mountain peak shrouded in swirling clouds and faint, mystical fog. Focus on Arjuna's face, conveying a mix of awe, humility, and determination. He should be depicted as a young, strong warrior, clad in ancient Indian armor, but with subtle, modern design elements. The divine weapons – a vibrant Vajra (thunderbolt), a radiant Brahmastra (celestial weapon), and a gleaming Pashupatastra (lord shiva's weapon) – should be swirling around him, each emitting its own unique light and energy. These weapons should appear as tangible, powerful objects, not just abstract concepts. Use a complementary color scheme of blues and golds, with pops of vibrant reds and greens emanating from the weapons. Employ cinematic rim lighting to highlight Arjuna's silhouette against the bright background, and volumetric lighting to accentuate the swirling clouds and fog. Ray-traced lighting effects should create realistic reflections and shadows on Arjuna's armor and the surrounding environment. Use subtle lens flare and chromatic aberration effects to add depth and realism. Depth of field should be shallow, blurring the background slightly to focus attention on Arjuna and the weapons. Photorealistic textures and materials are crucial – the armor should have minute scratches and imperfections, the weapons should gleam with otherworldly polish. Atmospheric particles, like dust motes or floating embers, should add to the ethereal feel. The overall mood should be one of reverence, power, and mystery. 8K resolution, crystal clear details. No text or words."}, {'start': '00:31', 'duration': '00:06', 'text': 'Toh jaldi se subscribe karo aur comment mein batao ki Arjun ka kaunsa weapon aapko sabse zyada pasand hai?', 'url': 'output/images/segment_7.png', 'source': 'Gemini', 'prompt': "Vertical image, portrait orientation, 1080x1920. Hyper-realistic digital art of Arjuna, the legendary archer from Mahabharata, standing in a dynamic pose, surrounded by ethereal representations of his celestial weapons. Arjuna should be depicted as a young, strong warrior with determined eyes and a subtle smile. He wears ornate golden armor with intricate carvings and a flowing red sash. Behind him, faintly glowing and semi-transparent, are visualizations of his most prominent weapons: the Gandiva bow (his signature weapon), the Brahmastra (a divine weapon of immense power), and the Pashupatastra (Shiva's irresistible and most destructive personal weapon). Each weapon should be depicted with distinctive energy signatures and unique visual characteristics. The Gandiva could have a subtle golden aura, the Brahmastra a swirling vortex of fire, and the Pashupatastra a sharp, piercing light. The background should be a stylized representation of the heavens, with swirling nebulae and faint constellations. Utilize rim lighting to highlight Arjuna’s silhouette and the edges of his armor, separating him from the background. Employ volumetric lighting to create depth and atmosphere, with beams of light emanating from the celestial weapons. The overall mood is one of power, divinity, and awe. Use a rich color grading with complementary colors like gold and deep blues for a vibrant and visually appealing look. Implement HDR-like contrast for enhanced detail. Focus should be razor-sharp on Arjuna's face and upper body, with a slight depth of field blurring the background and the lower portions of the weapons. Add subtle lens flare and chromatic aberration effects to enhance the photorealism. Include realistic reflections on the armor and weapons, along with subtle shadows and ambient occlusion for dimensional realism. Render with ray-traced lighting for a photorealistic rendering. Incorporate subtle atmospheric elements like floating particles of light or volumetric fog to add depth and mystery to the scene. The textures of the armor, skin, and weapons should be photorealistic with microscopic details. Aim for an 8K resolution image with crystal clear details. Modern, professional aesthetic suitable for tech content. No text or words in the image."}]}
    result = create_video_with_overlays(state)
    print(result)