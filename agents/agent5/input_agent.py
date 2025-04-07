def take_input(state):
    print("Taking input...")
    script = """
    Hey tech enthusiasts! Guess what? Meta just dropped Llama 4... and wow, it's a game-changer! They've released two initial models: Scout and Maverick.

    Scout runs on a single H100 GPU but packs a punch with 17 billion active parameters and—get this—a context window of 10 MILLION tokens! That's insane for document processing.

    Maverick is the multilingual beast with 400 billion total parameters supporting 12 languages and amazing multimodal abilities.

    But here's the juicy part... they're still training the most powerful version called 'Behemoth' with a mind-blowing 2 TRILLION parameters! Can you imagine what that will do?

    What makes Llama 4 special? It uses a Mixture of Experts architecture and early fusion for handling text, images, and video seamlessly.

    The best part? It's open-source! You can download it now from llama.com or try it on Meta's platforms.

    Ready to build something amazing with Llama 4? Let me know in the comments!
    """
    audio_path = "assets/audios/audio.mp3"
    bg_music_path = "assets/audios/bg_music3.mp3"
    return {"script": script, "audio_path": audio_path, "bg_music_path": bg_music_path}