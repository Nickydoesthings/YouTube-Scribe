from flask import Flask, render_template, request, jsonify
import os
import whisper
import yt_dlp
from openai import OpenAI
import logging

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the OpenAI client
client = OpenAI()

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
            ydl.download([video_url])

        info_dict = ydl.extract_info(video_url, download=False)
        filename = ydl.prepare_filename(info_dict)
        audio_file_path = os.path.splitext(filename)[0] + ".mp3"
        
        return audio_file_path
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def transcribe_audio_with_whisper(audio_file_path):
    model = whisper.load_model("base")
    result = model.transcribe(audio_file_path)
    return result['text']

def summarize_text(text):
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a tutorial maker. You seek to make written tutorials that are easy to follow and easy to read."},
                {"role": "user", "content": f"This is an audio transcript of a tutorial or DIY project. Make a written tutorial based off this audio transcript. Start with a summary and list out what the user will need (if relevant) - then list out the steps they should take. Produce your output with visually pleasing style that's easy to follow. Don't include links unless necessary. :\n\n{text}"}
            ]
        )

        # Access the content directly from the message object
        summary = completion.choices[0].message.content.strip()
        return summary
    except AttributeError as e:
        logger.error(f"AttributeError occurred: {e}. This might be due to unexpected response structure.")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return None

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        youtube_link = request.form['youtubeLink']
        save_path = './'  # You can customize this path as needed

        try:
            # Download the audio
            audio_file_path = download_youtube_audio(youtube_link, save_path)
            
            if audio_file_path:
                # Transcribe the audio
                transcript = transcribe_audio_with_whisper(audio_file_path)
                
                if transcript:
                    # Summarize the transcript
                    summary = summarize_text(transcript)
                    
                    if summary:
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return summary  # Return just the summary for AJAX requests
                        else:
                            return render_template('generator.html', summary=summary)
                    else:
                        error = "Failed to generate summary."
                else:
                    error = "Failed to transcribe the audio."
            else:
                error = "Failed to download the YouTube audio."
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': error}), 400
            else:
                return render_template('generator.html', error=error)

        except Exception as e:
            error = f"An unexpected error occurred: {str(e)}"
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': error}), 500
            else:
                return render_template('generator.html', error=error)

    return render_template('generator.html')

@app.route('/about')
def about():
    return render_template('about.html')


if __name__ == '__main__':
    app.run(debug=True)
