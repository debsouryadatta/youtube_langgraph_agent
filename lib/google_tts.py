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
        language_code="hi-IN",
        ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
        # name="en-US-Chirp3-HD-Kore"
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
    
    # Save the audio file
    with open(output_filename, "wb") as out:
        out.write(response.audio_content)
        print(f"Audio content written to file: {output_filename}")

# Example usage
if __name__ == "__main__":
    text = """Arrey yaar! Oh my god, aaj kya hua, tu believe nahi karega! 
    Main road pe chal raha tha aur achanak ek super cute puppy dikha... ekdum fluffy and adorable! 
    By the way, kya humara weekend pe coffee ka plan abhi bhi on hai? 
    Mujhe tujhe ek naya amazing show ke baare mein batana hai jo maine recently start kiya hai. 
    Tu bata de kab free hai - I'm really excited to catch up!"""
    output_file = "output/audios/testing.mp3"
    text_to_speech(text, output_file)