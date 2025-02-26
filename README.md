## YOUTUBE AI AGENT WITH LANGGRAPH
- Create youtube content with this ai agent (fully autonomous)
- Just provide the topic name, it will push the video to your youtube channel


### To dos:
- [x] Basic Version with google text to speech and google images search
- [x] Beautify the captions overlay with words coming one after another -> test_video.py
- [x] Caption syncing with the audio, by getting the exact timestamp of the segments(Putting the texts over the screen according to those timestamps) -> audio_stt.py
- [ ] Add the avatar api to the video with Simli api
- [ ] Add a soft background music to the video





<br>
<br>
<br>

### Which file consists what?

- main.py -> Main langgraph agent code with all the functionalities
- main2.py -> Main langgraph agent code with using google text to speech and google images

**lib folder:**
- youtube_api1.py -> Fetch the top viewed youtube videos on search query with youtube api
- youtube_api2.py -> Fetch the latest videos from youtube channels with youtube api
- create_video.py -> Create video from the text, images and audio with word by word highlighting
- google_tts.py -> Convert the text into audio with google cloud text to speech api
- google_images.py -> Fetch the images from google search images with bs4
- audio_stt.py -> Using groq whisper speech to text to convert the audio into text with timestamps then modifyng the timestamps -> It is done to sync the text overlays with the audio
- simli_avatar.py -> Get the avatar video from the simli api providing the audio file