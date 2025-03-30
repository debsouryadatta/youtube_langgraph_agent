# import base64
# import os
# from google import genai
# from google.genai import types
# from dotenv import load_dotenv
# from langchain_core.tools import tool
# from pydantic.v1 import tools

# load_dotenv()

# def generate(query):
#     client = genai.Client(
#         api_key=os.environ.get("GEMINI_API_KEY"),
#     )

#     model = "gemini-2.5-pro-exp-03-25"
#     contents = [
#         types.Content(
#             role="user",
#             parts=[
#                 types.Part.from_text(text=f"""{query}"""),
#             ],
#         ),
#     ]
#     tools = [
#         types.Tool(google_search=types.GoogleSearch())
#     ]
#     generate_content_config = types.GenerateContentConfig(
#         tools=tools,
#         response_mime_type="text/plain",
#     )

#     response = client.models.generate_content(
#         model=model,
#         contents=contents,
#         config=generate_content_config,
#     )

#     print(response.text)

# if __name__ == "__main__":
#     generate("Why is ghibli style photos generated with new gpt-4o so popular?")
    

import base64
import os
import mimetypes
from google import genai
from google.genai import types


def save_binary_file(file_name, data):
    f = open(file_name, "wb")
    f.write(data)
    f.close()


def generate():
    client = genai.Client(
        api_key=os.environ.get("GEMINI_API_KEY"),
    )

    model = "gemini-2.0-flash-exp-image-generation"
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text="""INSERT_INPUT_HERE"""),
            ],
        ),
    ]
    generate_content_config = types.GenerateContentConfig(
        response_modalities=[
            "image",
            "text",
        ],
        response_mime_type="text/plain",
    )

    for chunk in client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=generate_content_config,
    ):
        if not chunk.candidates or not chunk.candidates[0].content or not chunk.candidates[0].content.parts:
            continue
        if chunk.candidates[0].content.parts[0].inline_data:
            file_name = "ENTER_FILE_NAME"
            inline_data = chunk.candidates[0].content.parts[0].inline_data
            file_extension = mimetypes.guess_extension(inline_data.mime_type)
            save_binary_file(
                f"{file_name}{file_extension}", inline_data.data
            )
            print(
                "File of mime type"
                f" {inline_data.mime_type} saved"
                f"to: {file_name}"
            )
        else:
            print(chunk.text)

if __name__ == "__main__":
    generate()
