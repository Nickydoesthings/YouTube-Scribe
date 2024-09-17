from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length
from flask_migrate import Migrate
import os
import yt_dlp
from openai import OpenAI  # Use OpenAI class from openai-enterprise library
import logging
import markdown
from io import BytesIO
from weasyprint import HTML
from flask_wtf.csrf import CSRFProtect, generate_csrf
import webvtt
from io import StringIO

# Initialize the Flask application
app = Flask(__name__)

# Configuration for database and login management
app.config['SECRET_KEY'] = 'your_secret_key_here'  # Replace with a secure secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)  # Initialize Flask-Migrate with the app and database
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Set up logging to track and debug any issues during runtime
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the OpenAI client using the API key from environment variables
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Provide csrf_token to all templates
@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf())

# Define User model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    usage_count = db.Column(db.Integer, default=0)
    plan = db.Column(db.String(50), default='free')  # Field to track user's plan

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Define the forms
class SignupForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=150)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password', message="Passwords must match.")])
    submit = SubmitField('Sign Up')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=150)])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Log In')

@login_manager.unauthorized_handler
def unauthorized():
    # Redirect to the login page without flashing a message
    return redirect(url_for('login'))

# Routes for user authentication
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form = SignupForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        # Check if the user already exists
        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email already exists.', 'danger')
            return redirect(url_for('signup'))

        # Create a new user
        try:
            new_user = User(email=email, password=generate_password_hash(password, method='pbkdf2:sha256'))
            db.session.add(new_user)
            db.session.commit()
            flash('Account created successfully. Please log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()  # Rollback in case of error
            logger.error(f"Error creating user: {e}")
            flash('An error occurred while creating the account. Please try again.', 'danger')

    # Check for form validation errors
    elif form.errors:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{error}", 'danger')  # Flash only the error message, not the field name

    return render_template('signup.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        # Check if the user exists and verify the password
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('generator'))
        else:
            flash('Invalid email or password.', 'danger')

    return render_template('login.html', form=form)

@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/', methods=['GET', 'POST'])
def landing():
    if request.method == 'POST':
        youtube_link = request.form.get('youtubeLink')
        return redirect(url_for('generator') + f"?youtubeLink={youtube_link}")
    return render_template('landing.html')

@app.route('/generator', methods=['GET', 'POST'])
def generator():
    error = None
    html_summary = None  # Make sure this is set to None by default
    youtube_link = request.args.get('youtubeLink', '')  # Retrieve YouTube link from query params (for GET request)
    video_title = None
    thumbnail_url = None
    show_upgrade_popup = False  # Flag to control the display of the upgrade popup
    upgrade_reason = request.args.get('upgrade_reason', None)  # Get upgrade reason from query parameters

    if request.method == 'POST':
        youtube_link = request.form.get('youtubeLink')
        if not youtube_link:
            error = "Please provide a YouTube video URL."
        else:
            # Fetch video metadata (title, thumbnail, duration)
            _, video_title, thumbnail_url, duration = download_youtube_audio(youtube_link, metadata_only=True)

            if not video_title or not thumbnail_url:
                error = "Failed to fetch video metadata."
                return render_template('generator.html', error=error, youtube_link=youtube_link)
            # Check video duration based on user's plan
            if current_user.is_authenticated and current_user.plan == 'pro':
                max_duration = 7200  # 2 hours in seconds
            else:
                max_duration = 900  # 15 minutes in seconds

            if duration > max_duration:
                show_upgrade_popup = True
                upgrade_reason = 'video_duration'  # Set upgrade reason
                return render_template('generator.html', error=error, youtube_link=youtube_link, video_title=video_title, thumbnail_url=thumbnail_url, show_upgrade_popup=show_upgrade_popup, upgrade_reason=upgrade_reason)

            # Proceed with summary generation
            # First, try to download captions
            captions = download_youtube_captions(youtube_link)
            if captions:
                transcript = captions
            else:
                # Proceed to download audio and transcribe via Whisper API
                audio_file_path, _, _, _ = download_youtube_audio(youtube_link)
                transcript = transcribe_audio_with_whisper_api(audio_file_path)
                # Delete the audio file after transcription
                if os.path.exists(audio_file_path):
                    os.remove(audio_file_path)
                    logger.info(f"Deleted audio file: {audio_file_path}")

            try:
                if transcript:
                    summary = summarize_text(transcript)
                    if summary:
                        html_summary = markdown.markdown(summary)
                        if current_user.is_authenticated:
                            current_user.usage_count += 1
                            db.session.commit()
                    else:
                        error = "Failed to generate summary."
                else:
                    error = "Failed to obtain transcript."
            except Exception as e:
                logger.error(f"An unexpected error occurred: {e}")
                error = f"An unexpected error occurred: {e}"

    # Pass video title and thumbnail to the template
    return render_template('generator.html', summary=html_summary, error=error, youtube_link=youtube_link, video_title=video_title, thumbnail_url=thumbnail_url, show_upgrade_popup=show_upgrade_popup, upgrade_reason=upgrade_reason)


@app.route('/download/pdf', methods=['POST'])
@login_required
def download_pdf():
    if current_user.plan != 'pro':
        # Redirect to generator page with a flag to show the upgrade popup
        return redirect(url_for('generator', show_upgrade_popup=True, upgrade_reason='download_pdf'))

    summary = request.form.get('summary')

    if not summary:
        flash("No summary available for download. Please generate a summary first.", "danger")
        return redirect(url_for('generator'))

    html_content = f"<html><body>{markdown.markdown(summary)}</body></html>"
    pdf_file = BytesIO()
    HTML(string=html_content).write_pdf(pdf_file)
    pdf_file.seek(0)

    return send_file(pdf_file, as_attachment=True, download_name="summary.pdf")

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/pricing')
def pricing():
    return render_template('pricing.html')

@app.route('/my_account')
@login_required
def my_account():
    return render_template('my_account.html', email=current_user.email, plan=current_user.plan)


@app.route('/upgrade_to_pro', methods=['GET', 'POST'])
@login_required
def upgrade_to_pro():
    # Here you would handle the payment process
    # For now, we'll directly upgrade the user's plan
    current_user.plan = 'pro'
    db.session.commit()
    flash('You have been upgraded to the Pro plan.', 'success')
    return redirect(url_for('pricing'))

@app.route('/fetch_metadata', methods=['POST'])
def fetch_metadata():
    youtube_link = request.json.get('youtubeLink')

    if not youtube_link:
        return jsonify({'error': 'No YouTube link provided.'}), 400

    try:
        # Fetch video metadata (title, thumbnail, duration)
        _, video_title, thumbnail_url, duration = download_youtube_audio(youtube_link, metadata_only=True)

        if not video_title or not thumbnail_url:
            return jsonify({'error': 'Failed to fetch video metadata.'}), 500

        return jsonify({
            'video_title': video_title,
            'thumbnail_url': thumbnail_url,
            'duration': duration
        }), 200

    except Exception as e:
        logger.error(f"An error occurred while fetching metadata: {e}")
        return jsonify({'error': 'An unexpected error occurred.'}), 500

# Function to download YouTube audio and fetch metadata
def download_youtube_audio(video_url, save_path='.', metadata_only=False):
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
            'skip_download': metadata_only,  # Skip download if only metadata is needed
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(video_url, download=not metadata_only)
            if not metadata_only:
                filename = ydl.prepare_filename(info_dict)
                audio_file_path = os.path.splitext(filename)[0] + ".mp3"
            else:
                audio_file_path = None
            video_title = info_dict.get('title', 'Unknown Title')
            thumbnail_url = info_dict.get('thumbnail', '')
            duration = info_dict.get('duration', 0)  # Duration in seconds

        return audio_file_path, video_title, thumbnail_url, duration
    except Exception as e:
        logger.error(f"An error occurred while downloading audio: {e}")
        return None, None, None, None

def download_youtube_captions(video_url):
    try:
        ydl_opts = {
            'skip_download': True,
            'writesubtitles': True,
            'writeautomaticsub': True,  # Enable downloading auto-generated subtitles
            'subtitlesformat': 'vtt',
            'subtitleslangs': ['en'],  # Specify languages, can be modified as needed
            'outtmpl': '%(id)s.%(ext)s',
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(video_url, download=False)

            # Check for both manual and auto-generated captions
            subtitles = info_dict.get('subtitles', {})
            automatic_captions = info_dict.get('automatic_captions', {})

            captions_available = False

            if 'en' in subtitles:
                captions_available = True
                caption_type = 'subtitles'
            elif 'en' in automatic_captions:
                captions_available = True
                caption_type = 'automatic_captions'
            else:
                captions_available = False

            if captions_available:
                # Now download the subtitles
                ydl.download([video_url])
                # The subtitles will be saved as {video_id}.en.vtt
                video_id = info_dict.get('id')
                caption_file = f"{video_id}.en.vtt"
                if os.path.exists(caption_file):
                    # Read the captions file
                    with open(caption_file, 'r', encoding='utf-8') as f:
                        captions_content = f.read()
                    # Remove the captions file
                    os.remove(caption_file)
                    # Convert VTT to plain text
                    captions = convert_vtt_to_text(captions_content)
                    return captions
                else:
                    return None
            else:
                # No captions available
                return None
    except Exception as e:
        logger.error(f"An error occurred while downloading captions: {e}")
        return None


# Function to convert VTT captions to plain text
def convert_vtt_to_text(vtt_content):
    try:
        vtt_file = StringIO(vtt_content)
        text = ''
        for caption in webvtt.read_buffer(vtt_file):
            text += caption.text + '\n'
        return text
    except Exception as e:
        logger.error(f"An error occurred while converting VTT to text: {e}")
        return ''

# Function to transcribe audio with Whisper API
def transcribe_audio_with_whisper_api(audio_file_path):
    try:
        with open(audio_file_path, 'rb') as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        return transcript.text
    except Exception as e:
        logger.error(f"An error occurred during transcription: {e}")
        return None

# Function to summarize text using OpenAI
def summarize_text(text):
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a tutorial maker. You create written tutorials that are easy to follow."},
                {
                    "role": "user",
                    "content": f"""
                    This is an audio transcript of a tutorial, DIY project, or recipe video. Please create a detailed, structured written tutorial in Markdown format based on this transcript.

                    **Structure**:
                    1. **Summary**: Start with a brief summary of the tutorial. Summarize the goal and the key steps involved.
                    2. **What You Will Need**: List all the materials, tools, or prerequisites the user will need. Use bullet points.
                    3. **Step-by-Step Instructions**: Break down the process into clear, ordered steps. Use headers (### Step 1: ..., ### Step 2: ...) and ordered lists where appropriate.
                        - Include sub-steps if necessary.
                        - Use bullet points for additional notes or tips.
                    4. **Additional Notes**: If applicable, include a section for tips, common issues, or additional resources.

                    **Markdown Syntax**:
                    - Use # for main sections (e.g., Summary, What You Will Need).
                    - Use ## for major steps or sections within the tutorial.
                    - Use ### for sub-steps.
                    - Use bullet points for lists and additional tips or notes.

                    **Tone and Language**:
                    - Write in a clear, concise, and friendly tone.
                    - Assume the reader has only basic knowledge of the subject, and provide explanations where necessary.

                    **Handling Non-Essential Content**:
                    - Exclude any non-instructive content such as jokes, personal anecdotes, or irrelevant tangents from the final tutorial.

                    **Error Handling**:
                    - If a part of the transcript is unclear or seems incorrect, indicate this in the tutorial with a note (e.g., [Note: This part of the audio was unclear]).

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


if __name__ == '__main__':
    app.run(debug=True)
