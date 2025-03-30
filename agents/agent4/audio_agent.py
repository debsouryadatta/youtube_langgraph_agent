from google.cloud import texttospeech
from datetime import datetime
from moviepy.editor import *
from datetime import timedelta
import os
import json
import re
from google import genai
from dotenv import load_dotenv
load_dotenv()


def format_time(seconds):
    """Convert seconds to MM:SS format"""
    time_obj = timedelta(seconds=seconds)
    minutes, seconds = divmod(time_obj.seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"

def process_transcription(audio_path):
    """Process transcription data into the desired video script format using Gemini's multimodal capabilities"""

    # Initialize the Gemini client
    client = genai.Client(
        api_key=os.getenv("GEMINI_API_KEY"),
    )

    # Get audio duration
    with AudioFileClip(audio_path) as audio:
        total_duration = audio.duration

    # Upload the audio file to Gemini
    file = client.files.upload(file=audio_path)
    
    # Define the prompt for Gemini
    prompt = """
    Please transcribe this Hindi audio and write the transcription using English letters (Roman script). Format the result as a JSON object with the following structure:
    {
        "videoScript": [
            {
                "start": "MM:SS",
                "duration": "MM:SS",
                "text": "transcribed Hindi text in Roman script"
            },
            ...more segments...
        ]
    }
    
    Important requirements:
    1. Each segment should be between 4-7 seconds in duration
    2. Start times should be in MM:SS format (e.g., "00:05")
    3. Durations should also be in MM:SS format
    4. Ensure segments flow naturally and don't cut off mid-sentence
    5. Transcribe the Hindi audio using English letters/Roman script (like: "Aaj main aapko ek kahani sunane wala hoon")
    6. Maintain all Hindi expressions, interjections, and natural speech patterns in the transcription
    7. Example of expected transcription style: "Tum kya kar rahe ho? Kal chalo party karne jaate hain park mein"
    8. Return ONLY the JSON object, no additional text
    """

    # Create the content for the model
    contents = [
        genai.types.Content(
            role="user",
            parts=[
                genai.types.Part.from_uri(
                    file_uri=file.uri,
                    mime_type=file.mime_type,
                ),
                genai.types.Part.from_text(text=prompt),
            ],
        ),
    ]

    # Configure the response
    generate_content_config = genai.types.GenerateContentConfig(
        response_mime_type="text/plain",
    )

    # Generate the transcript with segments
    response = client.models.generate_content(
        model="gemini-2.5-pro-exp-03-25",
        contents=contents,
        config=generate_content_config,
    )

    # Extract and parse the JSON response
    try:
        # Extract JSON from the response text
        json_text = response.text
        # Sometimes the model might wrap the JSON in markdown code blocks, so we need to clean that
        json_text = re.sub(r'^```json\s*', '', json_text)
        json_text = re.sub(r'\s*```$', '', json_text)
        
        # Parse the JSON
        transcript_data = json.loads(json_text)
        
        # Add totalDuration to the output
        transcript_data["totalDuration"] = format_time(total_duration)
        
        return transcript_data
    except Exception as e:
        print(f"Error parsing Gemini response: {e}")
        print(f"Raw response: {response.text}")
        
        # Fallback to a basic structure if parsing fails
        return {
            "videoScript": [
                {
                    "start": "00:00",
                    "duration": format_time(total_duration),
                    "text": "Transcription failed. Please try again."
                }
            ],
            "totalDuration": format_time(total_duration)
        }

def generate_audio(state):
    print("Generating audio...")
    
    # Set the path to your service account key file
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "gcp_tts_key.json"
    
    # Initialize the client
    client = texttospeech.TextToSpeechClient()
    
    # Combine all text segments
    full_text = state["script"]
    
    # Set the text input
    synthesis_input = texttospeech.SynthesisInput(text=full_text)
    
    # Configure voice parameters
    voice = texttospeech.VoiceSelectionParams(
        language_code="hi-IN",
        ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
        name="hi-IN-Chirp3-HD-Leda"
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
    
    formatted_transcript = process_transcription(audio_path=audio_path)
    print("\n\nScript after STT:", formatted_transcript)
    
    return {"audio_path": audio_path, "script": formatted_transcript}
