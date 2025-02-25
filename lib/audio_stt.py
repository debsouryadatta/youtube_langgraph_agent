import os
import json
from groq import Groq
from datetime import timedelta

def format_time(seconds):
    """Convert seconds to MM:SS format"""
    time_obj = timedelta(seconds=seconds)
    minutes, seconds = divmod(time_obj.seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"

def process_transcription(audio_path):
    """Process transcription data into the desired video script format"""

    # Initialize the Groq client
    client = Groq()
    with open(audio_path, "rb") as file:
        transcription = client.audio.transcriptions.create(
            file=(audio_path, file.read()),
            model="whisper-large-v3-turbo",
            prompt="Specify context or spelling",
            response_format="verbose_json",
            language="en",
            temperature=0.0
        )
    

    # Extract segments from the transcription
    segments = transcription.segments
    total_duration = transcription.duration
    
    # Initialize variables for combining segments
    video_script = []
    current_segment = {
        "start": format_time(segments[0]["start"]),
        "text": segments[0]["text"].strip(),
        "start_seconds": segments[0]["start"],
        "end_seconds": segments[0]["end"]
    }
    
    # Combine segments to achieve 4-7 second durations
    for i in range(1, len(segments)):
        segment = segments[i]
        segment_duration = current_segment["end_seconds"] - current_segment["start_seconds"]
        
        # If adding this segment keeps us within the 4-7 second range, combine it
        if segment["end"] - current_segment["start_seconds"] <= 7:
            current_segment["text"] += " " + segment["text"].strip()
            current_segment["end_seconds"] = segment["end"]
        else:
            # Finalize the current segment and start a new one
            current_segment["duration"] = format_time(current_segment["end_seconds"] - current_segment["start_seconds"])
            # Remove the temporary keys used for calculation
            final_segment = {
                "start": current_segment["start"],
                "duration": current_segment["duration"],
                "text": current_segment["text"]
            }
            video_script.append(final_segment)
            
            # Start a new segment
            current_segment = {
                "start": format_time(segment["start"]),
                "text": segment["text"].strip(),
                "start_seconds": segment["start"],
                "end_seconds": segment["end"]
            }
    
    # Add the last segment
    current_segment["duration"] = format_time(current_segment["end_seconds"] - current_segment["start_seconds"])
    final_segment = {
        "start": current_segment["start"],
        "duration": current_segment["duration"],
        "text": current_segment["text"]
    }
    video_script.append(final_segment)
    
    # Create the final output structure
    output = {
        "videoScript": video_script,
        "totalDuration": format_time(total_duration)
    }
    
    return output

# Main execution
def main():
    # Initialize the Groq client
    client = Groq()
    
    # Specify the path to the audio file
    filename = "output/audio_1740510098.255412.mp3"  # Replace with your audio file path
    
    with open(filename, "rb") as file:
        transcription = client.audio.transcriptions.create(
            file=(filename, file.read()),
            model="whisper-large-v3-turbo",
            prompt="Specify context or spelling",
            response_format="verbose_json",
            language="en",
            temperature=0.0
        )
    
    # Process the transcription into the desired format
    formatted_output = process_transcription(transcription)
    
    # Print the formatted output
    print(json.dumps(formatted_output, indent=4))
    
    # Optionally, save to a file
    with open("formatted_transcription.json", "w") as f:
        json.dump(formatted_output, f, indent=4)
    
    print(f"Formatted transcription saved to formatted_transcription.json")

if __name__ == "__main__":
    main()