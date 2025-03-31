## YOUTUBE AI AGENT WITH LANGGRAPH
- Create youtube content with this ai agent (fully autonomous)
- Just provide the topic name, it will push the video to your youtube channel


<br>
<br>


## Agents

### Agent 1
- Specialised for: Tech updates yt shorts
- Services used:
    - Transcript agent: Tavily & Gemini
    - Title Desc agent: Gemini
    - Thumbnail agent: Fal
    - Audio agent: Google cloud tts & groq stt
    - Images agent: Google images
    - Avatar video agent: Simli
    - Video agent: no services used

### Agent 2
- Specialised for: No specialisation
- All in a single file
- Services used:
    - Transcript agent: Tavily & Gemini
    - Title Desc agent: Gemini
    - Thumbnail agent: Fal
    - Audio agent: Elevenlabs tts
    - Images agent: Fal
    - Avatar video agent: no avatar agent here
    - Video agent: no services used

### Agent 3
- Specialised for: ---Just for testing---

### Agent 4
- Specialised for: Psychological, Motivational, Story telling, Movie recommendation yt shorts in Hinglish
- Services used:
    - Transcript agent: Gemini with google search tool & Gemini
    - Title Desc agent: Gemini
    - Thumbnail agent: no services used
    - Audio agent: Google cloud tts & Gemini for stt
    - Images agent: Gemini Image gen
    - Avatar video agent: no avatar agent here
    - Video agent: no services used
    - Uploader agent: YouTube API v3


<br>
<br>


### Which file consists what?
- main.py -> Main langgraph agent with cleaned up code and better structure
- transcript_agent.py -> Researches about the topic and generates the transcript
- title_desc_agent.py -> Generates the title and description for the video based on the transcript
- thumbnail_agent.py -> Generate the thumbnail based on the title and description
- audio_agent.py -> Generate the audio from the transcript
- images_agent.py -> Generate the images based on the transcript
- avatar_video_agent.py -> Generate the avatar video from the audio
- video_agent.py -> Generate the video from the transcript and avatar video
- uploader_agent.py -> Uploads video to youtube using youtube api v3

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
- gemini_search.py -> Gemini response with google search tool
- upload_to_youtube.py -> Uploads video to youtube using youtube api v3


<br>
<br>


### To dos:
- [x] Basic Version with google text to speech and google images search
- [x] Beautify the captions overlay with words coming one after another -> test_video.py
- [x] Caption syncing with the audio, by getting the exact timestamp of the segments(Putting the texts over the screen according to those timestamps) -> audio_stt.py
- [x] Add the avatar api to the video with Simli api
- [x] Add a soft background music to the video
- [x] Clean up the code and make the overall structure better
- [x] Integrate YouTube Api to publish the video directly to the youtube channel
- [x] Add slight animations to the images in the video like zoom in/zoom out/slightly moving left and right
- [x] Add intro and outro animations
- [ ] Add another agent5 for tech updates and real use
- [ ] Make the prompts better to get more interesting output video
- [ ] Increase the types of video shorts by tweaking the overall workflow(Suppose we don't want avatar, we want a separate type of video)
- [ ] Think for images solution, as google images search might give same images or might have issue in downloading(although we have the placeholder image in place of that)


<br>
<br>


### Types of shorts/reels
- Will be based on Technology
- Tech news, Tech reviews, Tech updates, Tech motivation, Tech tips, Tech stories, anything related to Tech
- Domains - Ai, Blockchain, Tech Stack, New tech, General, Mobile, etc.
- Psycological(motivational), movie recommendation