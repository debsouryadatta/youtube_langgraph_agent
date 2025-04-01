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

def generate_detailed_transcript(audio_path):
    """Generate a detailed word-by-word transcript of the audio using Gemini's multimodal capabilities"""

    # Initialize the Gemini client
    client = genai.Client(
        api_key=os.getenv("GEMINI_API_KEY"),
    )

    # Upload the audio file to Gemini
    file = client.files.upload(file=audio_path)
    
    # Define the prompt for Gemini
    prompt = """
    Please transcribe this audio and provide a detailed word-by-word transcript with precise timing information.
    Format the result as a JSON array with the following structure for each word:
    [
      {
        "word": "example",
        "start": 0.085,
        "end": 0.403,
        "confidence": 0.99,
        "punctuated_word": "Example"
      },
      ... more words ...
    ]
    
    Important requirements:
    1. Each entry must represent a single word with extremely precise timing
    2. Start and end times must be in seconds with millisecond precision (e.g., 0.085, 1.253)
    3. Ensure the timing is strictly aligned with the actual audio - each timestamp must precisely match when the word begins and ends
    4. Include a confidence score between 0 and 1 for each word
    5. The "punctuated_word" field should include proper capitalization and punctuation
    6. If the audio is in Hindi, transcribe using English letters/Roman script
    7. Return ONLY the JSON array, no additional text
    8. Pay special attention to short words, ensuring they don't get artificially extended durations
    9. Verify that consecutive words have no significant gaps or overlaps in timing
    10. The transcript must perfectly synchronize with the audio when played back
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

    # Generate the detailed transcript
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
        detailed_transcript = json.loads(json_text)
        
        # Return the array directly
        print(f"Detailed transcript: {detailed_transcript}")
        return detailed_transcript
    except Exception as e:
        print(f"Error parsing Gemini response for detailed transcript: {e}")
        print(f"Raw response: {response.text}")
        
        # Fallback to a basic structure if parsing fails
        return [
            {
                "word": "transcription",
                "start": 0.0,
                "end": 1.0,
                "confidence": 0.99,
                "punctuated_word": "Transcription failed. Please try again."
            }
        ]


if __name__ == "__main__":
    audio_path = "output/audios/audio_1743498138.195549.mp3"
    generate_detailed_transcript(audio_path)
