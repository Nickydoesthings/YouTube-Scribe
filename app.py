from flask import Flask, render_template, request, jsonify, send_file
import os
import whisper
import yt_dlp
import openai
import logging
import markdown
from io import BytesIO
from weasyprint import HTML
from openai import OpenAI

# Initialize the Flask application
app = Flask(__name__)

# Set up logging to track and debug any issues during runtime
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the OpenAI client using the API key from environment variables
client = OpenAI()

# Set the OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

def download_youtube_audio(video_url, save_path='.'):
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f'{save_path}/%(title)s.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'postprocessor_args': [
                '-ar', '44100'
            ],
            'prefer_ffmpeg': True,
            'keepvideo': False,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(video_url)
            filename = ydl.prepare_filename(info_dict)
            audio_file_path = os.path.splitext(filename)[0] + ".mp3"
        
        return audio_file_path
    except Exception as e:
        logger.error(f"An error occurred while downloading audio: {e}")
        return None

def transcribe_audio_with_whisper(audio_file_path):
    try:
        model = whisper.load_model("base")
        result = model.transcribe(audio_file_path)
        
        if os.path.exists(audio_file_path):
            os.remove(audio_file_path)
            logger.info(f"Deleted audio file: {audio_file_path}")
        
        return result['text']
    except Exception as e:
        logger.error(f"An error occurred during transcription: {e}")
        
        if os.path.exists(audio_file_path):
            os.remove(audio_file_path)
            logger.info(f"Deleted audio file due to error: {audio_file_path}")
        
        return None

def summarize_text(text):
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a tutorial maker. You create written tutorials that are easy to follow."},
                {
                    "role": "user",
                    "content": f"""
                    This is an audio transcript of a tutorial or DIY project. Please create a detailed, structured written tutorial in Markdown format based on this transcript. 

                    **Structure**:
                    1. **Summary**: Start with a brief summary of the tutorial. Summarize the goal and the key steps involved.
                    2. **What You Will Need**: List all the materials, tools, or prerequisites the user will need. Use bullet points.
                    3. **Step-by-Step Instructions**: Break down the process into clear, ordered steps. Use headers (### Step 1: ..., ### Step 2: ...) and ordered lists where appropriate.
                        - Include sub-steps if necessary.
                        - Use bullet points for additional notes or tips.
                    4. **Additional Notes**: If applicable, include a section for tips, common issues, or additional resources.

                    **Markdown Syntax**:
                    - Use `#` for main sections (e.g., Summary, What You Will Need).
                    - Use `##` for major steps or sections within the tutorial.
                    - Use `###` for sub-steps.
                    - Use bullet points for lists and additional tips or notes.

                    **Tone and Language**:
                    - Write in a clear, concise, and friendly tone.
                    - Assume the reader has only basic knowledge of the subject, and provide explanations where necessary.

                    **Handling Non-Essential Content**:
                    - Exclude any non-instructive content such as jokes, personal anecdotes, or irrelevant tangents from the final tutorial.

                    **Error Handling**:
                    - If a part of the transcript is unclear or seems incorrect, indicate this in the tutorial with a note (e.g., `[Note: This part of the audio was unclear]`).

                    **Transcript**:
                    {text}
                    """     
                }
            ]
        )

        summary = completion.choices[0].message.content.strip()
        return summary
    except Exception as e:
        logger.error(f"An error occurred during text summarization: {e}")
        return None

@app.route('/', methods=['GET', 'POST'])
def home():
    error = None
    html_summary = None

    if request.method == 'POST':
        youtube_link = request.form.get('youtubeLink')
        if not youtube_link:
            error = "Please provide a YouTube video URL."
            return render_template('generator.html', error=error)

        try:
            audio_file_path = download_youtube_audio(youtube_link)
            if audio_file_path:
                transcript = transcribe_audio_with_whisper(audio_file_path)
                if transcript:
                    summary = summarize_text(transcript)
                    if summary:
                        html_summary = markdown.markdown(summary)
                    else:
                        error = "Failed to generate summary."
                else:
                    error = "Failed to transcribe the audio."
            else:
                error = "Failed to download the YouTube audio."
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            error = f"An unexpected error occurred: {e}"

        return render_template('generator.html', summary=html_summary, error=error)

    return render_template('generator.html', summary=html_summary, error=error)

@app.route('/download/pdf')
def download_pdf():
    summary = request.args.get('summary')
    
    if not summary:
        return "No summary available to download.", 400
    
    html_content = f"<html><body>{markdown.markdown(summary)}</body></html>"
    pdf_file = BytesIO()
    HTML(string=html_content).write_pdf(pdf_file)
    pdf_file.seek(0)

    return send_file(pdf_file, as_attachment=True, download_name="summary.pdf")

@app.route('/about')
def about():
    return render_template('about.html')

if __name__ == '__main__':
    app.run(debug=True)
