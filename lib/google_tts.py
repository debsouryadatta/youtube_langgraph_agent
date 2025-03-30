from google.cloud import texttospeech
import os
import json

def text_to_speech(text, output_filename):
    # Set the path to your service account key file
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "gcp_tts_key.json"
    
    # Initialize the client
    client = texttospeech.TextToSpeechClient()
    
    # Set the text input
    synthesis_input = texttospeech.SynthesisInput(text=text)
    
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
    
    # Save the audio file
    with open(output_filename, "wb") as out:
        out.write(response.audio_content)
        print(f"Audio content written to file: {output_filename}")

# Example usage
if __name__ == "__main__":
    text = """Hey buddy! Oh my gosh, you won't believe what happened today! 
    I was walking down the street and saw this super cute puppy... absolutely adorable! 
    By the way, are we still on for coffee this weekend? 
    I've been dying to tell you about this awesome new show I started watching. 
    Let me know when you're free - can't wait to catch up!"""
    output_file = "output/output.mp3"
    text_to_speech(text, output_file)