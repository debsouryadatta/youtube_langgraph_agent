# youtube langraph agent
from typing import TypedDict, List
from langgraph.graph import END, StateGraph

from input_agent import take_input
from audio_agent import process_audio
from images_agent import generate_images
from video_agent import create_video_with_overlays
from dotenv import load_dotenv

load_dotenv()

# 1. Define State Schema
class AgentState(TypedDict):
    topic: str
    script: str
    audio_path: str
    detailed_transcript: List[dict]
    images_manifest: List[dict]
    final_video_path: str
    bg_music_path: str

# 2. Initialize Tools and Models


# 3. Define Nodes/Agents
def input_agent(state: AgentState):
    result = take_input(state)
    return {"script": result["script"], "audio_path": result["audio_path"], "bg_music_path": result["bg_music_path"]}

def audio_agent(state: AgentState):
    result = process_audio(state)
    return {"images_manifest": result["images_manifest"], "detailed_transcript": result["detailed_transcript"]}

def images_agent(state: AgentState):
    result = generate_images(state)
    return {"images_manifest": result["images_manifest"]}

def video_agent(state: AgentState):
    result = create_video_with_overlays(state)
    return {"final_video_path": result["final_video_path"]}



# 4. Build Workflow
workflow = StateGraph(AgentState)

workflow.add_node("input_agent", input_agent)
workflow.add_node("audio_agent", audio_agent)
workflow.add_node("images_agent", images_agent)
workflow.add_node("video_agent", video_agent)

workflow.set_entry_point("input_agent")
workflow.add_edge("input_agent", "audio_agent")
workflow.add_edge("audio_agent", "images_agent")
workflow.add_edge("images_agent", "video_agent")
workflow.add_edge("video_agent", END)

app = workflow.compile()

# 5. Execution
if __name__ == "__main__":
    result = app.invoke({
        "topic": "Recent launch of Gemini 2.5 pro"
    })
    print(f"Final video created at: {result['final_video_path']}")
