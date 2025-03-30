
from google.cloud import texttospeech
from datetime import datetime
from moviepy.editor import *
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



def generate_audio(state):
    print("Generating audio...")
    
    # Set the path to your service account key file
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "gcp_tts_key.json"
    
    # Initialize the client
    client = texttospeech.TextToSpeechClient()
    
    # Combine all text segments
    full_text = " ".join([seg["text"] for seg in state["script"]["videoScript"]])
    
    # Set the text input
    synthesis_input = texttospeech.SynthesisInput(text=full_text)
    
    # Configure voice parameters
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
        name="en-US-Chirp3-HD-Kore"
    )
    
    # Set audio configuration
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )
    
    # Generate speech
    response = client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config
    )
    
    audio_path = f"output/audios/audio_{datetime.now().timestamp()}.mp3"
    
    # Save the audio file
    with open(audio_path, "wb") as out:
        out.write(response.audio_content)
        print(f"Audio content written to file: {audio_path}")
    
    # Get audio duration
    with AudioFileClip(audio_path) as audio:
        duration = audio.duration
    
    # formatted_transcript = {
    #     "videoScript": [
    #         {
    #             "start": "00:00",
    #             "duration": f"{int(duration // 60):02d}:{int(duration % 60):02d}",
    #             "text": full_text
    #         }
    #     ],
    #     "totalDuration": f"{int(duration // 60):02d}:{int(duration % 60):02d}"
    # }
    formatted_transcript = process_transcription(audio_path=audio_path)
    print("Script after STT:", formatted_transcript)
    
    return {"audio_path": audio_path, "script": formatted_transcript}
