from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from moviepy.editor import VideoFileClip, concatenate_videoclips
import os
import time
import google.generativeai as genai

app = FastAPI()

# Google API configuration
GOOGLE_API_KEY = "AIzaSyDKJNuipzxjT12FLvbMwoOP83keVAvXSDk"
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# Create output folder if it doesn't exist
output_folder = "static/output"
if not os.path.exists(output_folder):
    os.makedirs(output_folder)
output_path = os.path.join(output_folder, "output.mp4")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def time_to_seconds(time_str):
    parts = time_str.split(':')
    parts = [float(part) for part in parts]
    return sum(part * 60 ** (len(parts) - 1 - i) for i, part in enumerate(parts))

@app.post("/upload/", response_class=HTMLResponse)
async def upload_video(request: Request, file: UploadFile = File(...)):
    file_location = f"temp_{file.filename}"
    with open(file_location, "wb+") as file_object:
        file_object.write(file.file.read())

    video = VideoFileClip(file_location)
    genai_file = genai.upload_file(file_location)

    def wait_for_files_active():
        time.sleep(5 + (video.duration // 100) * 10)
    wait_for_files_active()

    chat_session = model.start_chat(
        history=[
            {
                "role": "user",
                "parts": [
                    genai_file,
                ],
            },
        ]
    )

    response = chat_session.send_message("""Please provide a list of most important scenes from this video, with timestamps in the format 0:00-0:08, focusing on the most significant or memorable moments. 

    **Only provide timestamps within the video's actual duration.**

    **Don't give any unnecessary text.**""")
    key_moments_text = response.text
    key_moments = [line.strip() for line in key_moments_text.strip().split('\n') if line.strip()]
    key_moments = key_moments[:-2]

    highlight_clips = []
    for moment in key_moments:
        start_str, end_str = moment.split('-')
        start = time_to_seconds(start_str)
        end = time_to_seconds(end_str)
        clip = video.subclip(start, end)
        highlight_clips.append(clip)

    final_clip = concatenate_videoclips(highlight_clips, method="compose")
    final_clip.write_videofile(output_path, codec="libx264")

    return templates.TemplateResponse("upload_response.html", {"request": request})

@app.get("/download/")
async def download_video():
    return FileResponse(path=output_path, filename="output.mp4")

@app.get("/", response_class=HTMLResponse)
async def main(request: Request):
    return templates.TemplateResponse("main.html", {"request": request})
