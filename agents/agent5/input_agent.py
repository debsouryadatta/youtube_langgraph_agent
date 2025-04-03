def take_input(state):
    print("Taking input...")
    script = """
    Wow! Google just dropped Gemini 2.5 Pro! Can you believe it? This AI model is absolutely breaking barriers with some incredible features! What are they? First, a million token context window - that's huge! Second, advanced reasoning capabilities that blow previous models away. And third, dramatically improved multimodal understanding! 
    
    What does this mean for users? It can analyze entire codebases, books, or even hours of video in one go! Isn't that amazing? But wait - the most impressive feature? It's definitely the "function calling" capability that lets developers create complex AI applications faster than ever before! How cool is that?
    
    Want to try it yourself? Gemini 2.5 Pro is available right now through Google AI Studio and Vertex AI! Don't miss out on experiencing this revolutionary technology!
    """
    audio_path = "output/audios/audio.mp3"
    bg_music_path = "assets/bg_music.mp3"
    return {"script": script, "audio_path": audio_path, "bg_music_path": bg_music_path}