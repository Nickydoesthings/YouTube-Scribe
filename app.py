from flask import Flask, render_template, request, jsonify
import os
import whisper
import yt_dlp
import openai
import logging
import markdown

# Initialize the Flask application
app = Flask(__name__)

# Set up logging to track and debug any issues during runtime
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the OpenAI client using the API key from environment variables
openai.api_key = os.getenv("OPENAI_API_KEY")

def download_youtube_audio(video_url, save_path='.'):
    """
    Downloads the audio from a YouTube video using yt_dlp and saves it as an MP3 file.

    Args:
        video_url (str): The URL of the YouTube video.
        save_path (str): The path where the audio file will be saved.

    Returns:
        str: The path to the downloaded MP3 file, or None if an error occurs.
    """
    try:
        ydl_opts = {
            'format': 'bestaudio/best',  # Download the best available audio quality
            'outtmpl': f'{save_path}/%(title)s.%(ext)s',  # Template for output filename
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',  # Extract audio using FFmpeg
                'preferredcodec': 'mp3',  # Convert audio to MP3 format
                'preferredquality': '192',  # Set the audio quality
            }],
            'postprocessor_args': [
                '-ar', '44100'  # Set the audio sample rate
            ],
            'prefer_ffmpeg': True,  # Prefer using FFmpeg for processing
            'keepvideo': False,  # Do not keep the video file after extracting audio
        }

        # Download the audio using yt-dlp with the provided options
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(video_url)  # Extract video information
            filename = ydl.prepare_filename(info_dict)  # Prepare the filename based on the video title
            audio_file_path = os.path.splitext(filename)[0] + ".mp3"  # Change the extension to MP3
        
        return audio_file_path  # Return the path to the downloaded MP3 file
    except Exception as e:
        logger.error(f"An error occurred while downloading audio: {e}")  # Log any errors that occur
        return None  # Return None if an error occurs

def transcribe_audio_with_whisper(audio_file_path):
    """
    Transcribes audio using the Whisper model.

    Args:
        audio_file_path (str): The path to the audio file.

    Returns:
        str: The transcribed text, or None if an error occurs.
    """
    try:
        model = whisper.load_model("base")  # Load the Whisper model
        result = model.transcribe(audio_file_path)  # Transcribe the audio file
        return result['text']  # Return the transcribed text
    except Exception as e:
        logger.error(f"An error occurred during transcription: {e}")  # Log any errors that occur
        return None  # Return None if an error occurs

from openai import OpenAI

# Initialize the OpenAI client
client = OpenAI()

from openai import OpenAI

# Initialize the OpenAI client
client = OpenAI()

def summarize_text(text):
    """
    Summarizes a given text using OpenAI's GPT model.

    Args:
        text (str): The text to be summarized.

    Returns:
        str: The summarized text in Markdown format, or None if an error occurs.
    """
    try:
        # Use the OpenAI API to generate a summary
        completion = client.chat.completions.create(
            model="gpt-4o-mini",  # Replace with the correct model if different
            messages=[
                {"role": "system", "content": "You are a tutorial maker. You create written tutorials that are easy to follow."},
                {
                    "role": "user",
                    "content": f"""
                    This is an audio transcript of a tutorial or DIY project. 
                    Make a written tutorial in Markdown based off this audio transcript. 
                    Start with a summary and list out what the user will need (if relevant) - 
                    then list out the steps they should take. 
                    Please use Markdown syntax, with headers for sections, ordered lists for steps, 
                    and appropriate spacing for readability. Assume the reader has only basic knowledge of the subject at hand. 
                    Don't include links unless necessary.

                    Transcript:
                    {text}
                    """
                }
            ]
        )

        # Access the content directly from the `message` attribute
        summary = completion.choices[0].message.content.strip()
        return summary
    except Exception as e:
        logger.error(f"An error occurred during text summarization: {e}")
        return None  # Return None if an error occurs





@app.route('/', methods=['GET', 'POST'])
def home():
    error = None  # Initialize error variable to None
    html_summary = None  # Initialize summary variable to None

    if request.method == 'POST':
        youtube_link = request.form.get('youtubeLink')  # Get the YouTube link from the form
        if not youtube_link:
            error = "Please provide a YouTube video URL."  # Error if no URL is provided
            return render_template('generator.html', error=error)  # Render the page with the error message
        
        try:
            audio_file_path = download_youtube_audio(youtube_link)  # Download the YouTube audio
            if audio_file_path:
                transcript = transcribe_audio_with_whisper(audio_file_path)  # Transcribe the audio to text
                if transcript:
                    summary = summarize_text(transcript)  # Summarize the transcript
                    if summary:
                        html_summary = markdown.markdown(summary)  # Convert the summary to HTML
                    else:
                        error = "Failed to generate summary."  # Error if summary generation fails
                else:
                    error = "Failed to transcribe the audio."  # Error if transcription fails
            else:
                error = "Failed to download the YouTube audio."  # Error if audio download fails
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")  # Log unexpected errors
            error = f"An unexpected error occurred: {e}"  # Set the error message for the user

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Return only the summary section as a response to the AJAX request
            return render_template('summary_partial.html', summary=html_summary, error=error)
        else:
            return render_template('generator.html', summary=html_summary, error=error)  # Render the page with the summary or error message

    return render_template('generator.html', summary=html_summary, error=error)  # Render the page for GET requests


@app.route('/about')
def about():
    """
    Handles the about route, rendering a simple 'About' page.

    Returns:
        str: The rendered HTML page for the 'About' section.
    """
    return render_template('about.html')

if __name__ == '__main__':
    # Run the Flask application in debug mode
    app.run(debug=True)
