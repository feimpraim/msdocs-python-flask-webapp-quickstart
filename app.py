import os
import certifi
import ssl
import zipfile
from functools import wraps
from pytube import YouTube
from pytube.cli import on_progress
from pytube.exceptions import PytubeError, VideoUnavailable, VideoPrivate, LiveStreamError
from flask_oauthlib.client import OAuth
from io import BytesIO
from flask import Flask, redirect, render_template, request, send_file, url_for, session
from dotenv import load_dotenv

ssl._create_default_https_context = ssl._create_unverified_context

app = Flask(__name__)

secret_key = os.urandom(24)
app.secret_key = secret_key  # Change this to a more secure secret key

oauth = OAuth(app)

google = oauth.remote_app(
    'google',
    consumer_key='4replace,
    consumer_secret='replace',
    request_token_params={'scope': 'email'},
    base_url='https://www.googleapis.com/oauth2/v1/',
    request_token_url=None,
    access_token_method='POST',
    access_token_url='https://accounts.google.com/o/oauth2/token',
    authorize_url='https://accounts.google.com/o/oauth2/auth',
)

app.config['OAUTH_CREDENTIALS'] = {
    'google': {
        'id': 'replcae',
        'secret': 'repalce',
        'redirect_uri': 'replace',
    },
}

# Dictionary to store download progress for each user
download_progress = {}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('login_page', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login_page')
def login_page():
    if 'user_email' in session:
        return redirect(url_for('index'))
    return render_template("login.html")

@app.route('/')
@login_required
def index():
    return render_template("index.html")

@app.route('/login')
def login():
    return google.authorize(callback=url_for('authorized', _external=True))

@app.route('/logout')
def logout():
    session.pop('google_token', None)
    session.pop('user_email', None)
    return redirect(url_for('login_page'))

@app.route('/login/authorized')
def authorized():
    response = google.authorized_response()
    
    if response is None or response.get('access_token') is None:
        return 'Access denied: reason={} error={}'.format(
            request.args['error_reason'],
            request.args['error_description']
        )

    session['google_token'] = (response['access_token'], '')
    user_info = google.get('userinfo')
    session['user_email'] = user_info.data['email']

    return redirect(url_for('index'))

def download_audio_and_video(yt):
    try:
        audio = yt.streams.filter(only_audio=True, file_extension='mp4').order_by('abr').desc().first()
        video = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()

        if not audio:
            return None, "Couldn't find a suitable audio stream for the provided URL."
        if not video:
            return None, "Couldn't find a suitable video stream for the provided URL."

        audio_buffer = BytesIO()
        video_buffer = BytesIO()

        audio.stream_to_buffer(audio_buffer)
        video.stream_to_buffer(video_buffer)

        audio_buffer.seek(0)
        video_buffer.seek(0)

        return audio_buffer, video_buffer, None
    except PytubeError as e:
        return None, None, f"An error occurred while processing the audio and video: {str(e)}"

    try:
        audio = yt.streams.filter(only_audio=True).order_by('abr').desc().first()
        video = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()

        if not audio:
            return None, "Couldn't find a suitable audio stream for the provided URL."
        if not video:
            return None, "Couldn't find a suitable video stream for the provided URL."

        audio_buffer = BytesIO()
        video_buffer = BytesIO()

        audio.stream_to_buffer(audio_buffer)
        video.stream_to_buffer(video_buffer)

        audio_buffer.seek(0)
        video_buffer.seek(0)

        return audio_buffer, video_buffer, None
    except PytubeError as e:
        return None, None, f"An error occurred while processing the audio and video: {str(e)}"

@app.route('/hello', methods=['POST'])
@login_required
def hello():
    url = request.form.get('name')
    if not url:
        return render_template("error.html", message="URL is missing. Please provide a valid YouTube URL.", back_url=url_for('index'))

    try:
        yt = YouTube(url, on_progress_callback=on_progress)

        audio_buffer, video_buffer, download_error = download_audio_and_video(yt)
        if download_error:
            return render_template("error.html", message=download_error, back_url=url_for('index'))

        # Create a ZIP archive containing audio and video
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            zip_file.writestr(f"{yt.title}.mp3", audio_buffer.read())
            zip_file.writestr(f"{yt.title}.mp4", video_buffer.read())

        zip_buffer.seek(0)

        return send_file(
            zip_buffer,
            as_attachment=True,
            attachment_filename=f"{yt.title}.zip",
            mimetype="application/zip",
        )
    except VideoUnavailable:
        return render_template("error.html", message="The provided YouTube video is unavailable.", back_url=url_for('index'))
    except VideoPrivate:
        return render_template("error.html", message="The provided YouTube video is private and cannot be accessed.", back_url=url_for('index'))
    except LiveStreamError:
        return render_template("error.html", message="Live streams cannot be downloaded.", back_url=url_for('index'))
    except PytubeError as e:
        return render_template("error.html", message=f"An error occurred while processing the video: {str(e)}", back_url=url_for('index'))

@app.route('/error', methods=['GET'])
@login_required
def error():
    message = request.args.get('message')
    back_url = request.args.get('back_url')
    return render_template("error.html", message=message, back_url=back_url)

@google.tokengetter
def get_google_oauth_token():
    return session.get('google_token')

if __name__ == "__main__":
    # Set the SSL certificate file for urllib
    os.environ["SSL_CERT_FILE"] = certifi.where()

    app.run(debug=True, port=5000)
