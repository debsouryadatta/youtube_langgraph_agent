## YOUTUBE AI AGENT WITH LANGGRAPH
- Create youtube content with this ai agent (fully autonomous)
- Just provide the topic name, it will push the video to your youtube channel


### To dos:
- [x] Basic Version with google text to speech and google images search
- [x] Beautify the captions overlay with words coming one after another -> test_video.py
- [x] Caption syncing with the audio, by getting the exact timestamp of the segments(Putting the texts over the screen according to those timestamps) -> audio_stt.py
- [x] Add the avatar api to the video with Simli api
- [x] Add a soft background music to the video
- [x] Clean up the code and make the overall structure better
- [ ] Make the prompts better to get more interesting output video
- [ ] Increase the types of video shorts by tweaking the overall workflow(Suppose we don't want avatar, we want a separate type of video)
- [ ] Integrate YouTube Api to publish the video directly to the youtube channel
- [ ] Think for images solution, as google images search might give same images or might have issue in downloading(although we have the placeholder image in place of that)





<br>
<br>
<br>

### Which file consists what?

- main.py -> Main langgraph agent with cleaned up code and better structure
- main2.py -> Main langgraph agent code with all the functionalities



**nodes folder:**
- transcript_agent.py -> Researches about the topic and generates the transcript
- title_desc_agent.py -> Generates the title and description for the video based on the transcript
- thumbnail_agent.py -> Generate the thumbnail based on the title and description
- audio_agent.py -> Generate the audio from the transcript
- images_agent.py -> Generate the images based on the transcript
- avatar_video_agent.py -> Generate the avatar video from the audio
- video_agent.py -> Generate the video from the transcript and avatar video



**lib folder:**
- youtube_api1.py -> Fetch the top viewed youtube videos on search query with youtube api
- youtube_api2.py -> Fetch the latest videos from youtube channels with youtube api
- create_video.py -> Create video from the text, images and audio with word by word highlighting
- google_tts.py -> Convert the text into audio with google cloud text to speech api
- google_images.py -> Fetch the images from google search images with bs4
- audio_stt.py -> Using groq whisper speech to text to convert the audio into text with timestamps then modifyng the timestamps -> It is done to sync the text overlays with the audio
- simli_avatar.py -> Get the avatar video from the simli api providing the audio file
- create_video2.py -> Create video from the text and the video with audio(generated with simli api)
- create_video3.py -> Create video from the text and the video with audio(generated with simli api) + included google searched images to stick on the top of the video.
- create_video4.py -> Create video from the text and the video with audio(generated with simli api) + included google searched images to stick on the top of the video + included the background music to the video
