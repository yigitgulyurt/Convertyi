import os
import io
import magic
import ffmpeg
import tempfile
from datetime import datetime
from flask import Flask, render_template, request, send_file, flash, redirect, url_for, session, jsonify
from werkzeug.utils import secure_filename
from PIL import Image
from pydub import AudioSegment
from moviepy.editor import VideoFileClip
from PyPDF2 import PdfReader, PdfWriter
from docx import Document
from ebooklib import epub
import zipfile
import rarfile
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import FileField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///converter.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB max file size

# Veritabanı ve kullanıcı yönetimi
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    conversions = db.relationship('Conversion', backref='user', lazy=True)

class Conversion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    converted_filename = db.Column(db.String(255), nullable=False)
    original_format = db.Column(db.String(10), nullable=False)
    target_format = db.Column(db.String(10), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Dosya yükleme için izin verilen uzantılar
ALLOWED_EXTENSIONS = {
    'image': {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'webp'},
    'video': {'mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv'},
    'audio': {'mp3', 'wav', 'ogg', 'flac', 'aac'},
    'document': {'pdf', 'doc', 'docx', 'txt', 'rtf'},
    'archive': {'zip', 'rar', '7z', 'tar', 'gz'},
    'presentation': {'ppt', 'pptx', 'odp'},
    'font': {'ttf', 'otf', 'woff', 'woff2'},
    'ebook': {'epub', 'mobi', 'azw3', 'fb2'}
}

# Form sınıfları
class ConversionForm(FlaskForm):
    file = FileField('Dosya', validators=[DataRequired()])
    category = SelectField('Kategori', validators=[DataRequired()])
    target_format = SelectField('Hedef Format', validators=[DataRequired()])
    submit = SubmitField('Dönüştür')

class LoginForm(FlaskForm):
    username = StringField('Kullanıcı Adı', validators=[DataRequired()])
    password = StringField('Şifre', validators=[DataRequired()])
    submit = SubmitField('Giriş Yap')

# Yükleme klasörü
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename, category):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS[category]

def convert_image(input_path, output_format):
    img = Image.open(input_path)
    output = io.BytesIO()
    img.save(output, format=output_format.upper())
    output.seek(0)
    return output

def convert_video(input_path, output_format):
    with tempfile.NamedTemporaryFile(suffix=f'.{output_format}', delete=False) as temp_file:
        output_path = temp_file.name
    
    video = VideoFileClip(input_path)
    video.write_videofile(output_path, codec='libx264')
    video.close()
    
    with open(output_path, 'rb') as f:
        output = io.BytesIO(f.read())
    
    os.unlink(output_path)
    return output

def convert_audio(input_path, output_format):
    audio = AudioSegment.from_file(input_path)
    output = io.BytesIO()
    audio.export(output, format=output_format)
    output.seek(0)
    return output

def convert_document(input_path, output_format):
    if output_format == 'pdf':
        reader = PdfReader(input_path)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        output = io.BytesIO()
        writer.write(output)
        output.seek(0)
        return output
    elif output_format in ['docx', 'doc']:
        doc = Document()
        with open(input_path, 'r', encoding='utf-8') as f:
            doc.add_paragraph(f.read())
        output = io.BytesIO()
        doc.save(output)
        output.seek(0)
        return output

@app.route('/')
def index():
    form = ConversionForm()
    form.category.choices = [(k, k.title()) for k in ALLOWED_EXTENSIONS.keys()]
    return render_template('index.html', 
                         form=form,
                         categories=ALLOWED_EXTENSIONS.keys(),
                         ALLOWED_EXTENSIONS=ALLOWED_EXTENSIONS)

@app.route('/convert', methods=['POST'])
@login_required
def convert_file():
    form = ConversionForm()
    if form.validate_on_submit():
        file = form.file.data
        category = form.category.data
        target_format = form.target_format.data
        
        if file and allowed_file(file.filename, category):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            try:
                output = None
                if category == 'image':
                    output = convert_image(filepath, target_format)
                elif category == 'video':
                    output = convert_video(filepath, target_format)
                elif category == 'audio':
                    output = convert_audio(filepath, target_format)
                elif category == 'document':
                    output = convert_document(filepath, target_format)
                
                if output:
                    # Dönüşüm kaydını veritabanına ekle
                    conversion = Conversion(
                        user_id=current_user.id,
                        original_filename=filename,
                        converted_filename=f'converted.{target_format}',
                        original_format=filename.split('.')[-1],
                        target_format=target_format
                    )
                    db.session.add(conversion)
                    db.session.commit()
                    
                    return send_file(
                        output,
                        mimetype=f'application/octet-stream',
                        as_attachment=True,
                        download_name=f'converted.{target_format}'
                    )
                
                flash('Bu format dönüşümü henüz desteklenmiyor')
                return redirect(url_for('index'))
                
            except Exception as e:
                flash(f'Dönüştürme hatası: {str(e)}')
                return redirect(url_for('index'))
            finally:
                if os.path.exists(filepath):
                    os.remove(filepath)
    
    flash('İzin verilmeyen dosya formatı')
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.password == form.password.data:  # Gerçek uygulamada şifre hash'lenmelidir
            login_user(user)
            return redirect(url_for('index'))
        flash('Geçersiz kullanıcı adı veya şifre')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/history')
@login_required
def history():
    conversions = Conversion.query.filter_by(user_id=current_user.id).order_by(Conversion.timestamp.desc()).all()
    return render_template('history.html', conversions=conversions)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000) 