import os
import io
import magic
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
from wtforms import FileField, SelectField, StringField, SubmitField, PasswordField, BooleanField
from wtforms.validators import DataRequired, Email, EqualTo, Length
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# .env dosyasından çevre değişkenlerini yükle
load_dotenv()

# Flask uygulamasını oluştur
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(24))
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///converter.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB
app.config['MAX_CONTENT_LENGTH_AUTHENTICATED'] = int(os.getenv('MAX_CONTENT_LENGTH_AUTHENTICATED', 32 * 1024 * 1024))  # 32MB

# Veritabanı ve kullanıcı yönetimi
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    ip_address = db.Column(db.String(45), nullable=True)
    conversions = db.relationship('Conversion', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Conversion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
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
    'görsel': {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'webp'},
    'video': {'mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv'},
    'ses': {'mp3', 'wav', 'ogg', 'flac', 'aac'},
    'belge': {'pdf', 'doc', 'docx', 'txt', 'rtf'},
    'arşiv': {'zip', 'rar', '7z', 'tar', 'gz'},
    'sunum': {'ppt', 'pptx', 'odp'},
    'font': {'ttf', 'otf', 'woff', 'woff2'},
    'e-kitap': {'epub', 'mobi', 'azw3', 'fb2'}
}

# Form sınıfları
class ConversionForm(FlaskForm):
    file = FileField('Dosya', validators=[DataRequired()])
    category = SelectField('Kategori', validators=[DataRequired()], choices=[])
    target_format = SelectField('Hedef Format', validators=[DataRequired()], choices=[])
    submit = SubmitField('Dönüştür')

    def __init__(self, *args, **kwargs):
        super(ConversionForm, self).__init__(*args, **kwargs)
        self.category.choices = [(k, k.title()) for k in ALLOWED_EXTENSIONS.keys()]
        if self.category.data:
            self.update_target_formats()

    def update_target_formats(self):
        if self.category.data:
            self.target_format.choices = [(ext, ext.upper()) for ext in ALLOWED_EXTENSIONS[self.category.data]]

class LoginForm(FlaskForm):
    email = StringField('E-posta', validators=[DataRequired(), Email()])
    password = PasswordField('Şifre', validators=[DataRequired()])
    remember_me = BooleanField('Beni Hatırla')
    submit = SubmitField('Giriş Yap')

class RegistrationForm(FlaskForm):
    username = StringField('Kullanıcı Adı', validators=[DataRequired(), Length(min=4, max=20)])
    email = StringField('E-posta', validators=[DataRequired(), Email()])
    password = PasswordField('Şifre', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField('Şifre Tekrar', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Kayıt Ol')

# Yükleme klasörü
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', '/var/www/convertyi/temp')
if not os.path.exists(UPLOAD_FOLDER):
    try:
        os.makedirs(UPLOAD_FOLDER, mode=0o775)
    except PermissionError:
        print(f"HATA: {UPLOAD_FOLDER} dizini oluşturulamadı. Lütfen izinleri kontrol edin.")
        raise
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename, category):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS[category]

def allowed_file_size(file_size, is_authenticated):
    max_size = app.config['MAX_CONTENT_LENGTH_AUTHENTICATED'] if is_authenticated else app.config['MAX_CONTENT_LENGTH']
    return file_size <= max_size

def convert_image(input_file, target_format):
    """Resim dosyasını dönüştür"""
    try:
        # Resmi aç
        img = Image.open(input_file)
        
        # RGBA modundaki resimleri RGB'ye dönüştür
        if img.mode in ('RGBA', 'LA'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1])
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Çıktı dosyası için BytesIO oluştur
        output = io.BytesIO()
        
        # Format ayarları
        format_settings = {
            'jpg': {'format': 'JPEG', 'quality': 95},
            'jpeg': {'format': 'JPEG', 'quality': 95},
            'png': {'format': 'PNG'},
            'webp': {'format': 'WEBP', 'quality': 95},
            'bmp': {'format': 'BMP'},
            'gif': {'format': 'GIF'},
            'tiff': {'format': 'TIFF'},
            'ico': {'format': 'ICO'}
        }
        
        # Hedef format ayarlarını al
        settings = format_settings.get(target_format.lower(), {'format': target_format.upper()})
        
        # Resmi kaydet
        img.save(output, **settings)
        output.seek(0)
        
        return output
    except Exception as e:
        print(f"Resim dönüştürme hatası: {str(e)}")
        raise

def convert_video(input_path, output_format, is_authenticated):
    with tempfile.NamedTemporaryFile(suffix=f'.{output_format}', delete=False) as temp_file:
        output_path = temp_file.name
    
    video = VideoFileClip(input_path)
    bitrate = '5000k' if is_authenticated else '2000k'
    video.write_videofile(output_path, codec='libx264', bitrate=bitrate)
    video.close()
    
    with open(output_path, 'rb') as f:
        output = io.BytesIO(f.read())
    
    os.unlink(output_path)
    return output

def convert_audio(input_path, output_format, is_authenticated):
    audio = AudioSegment.from_file(input_path)
    output = io.BytesIO()
    bitrate = '320k' if is_authenticated else '128k'
    audio.export(output, format=output_format, bitrate=bitrate)
    output.seek(0)
    return output

def convert_document(input_path, output_format, is_authenticated):
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

def detect_file_type(file_path):
    """Dosya türünü algıla"""
    try:
        # MIME türünü algıla
        mime = magic.Magic(mime=True)
        mime_type = mime.from_file(file_path)
        
        # MIME türüne göre kategori belirle
        if mime_type.startswith('image/'):
            return 'görsel'
        elif mime_type.startswith('video/'):
            return 'video'
        elif mime_type.startswith('audio/'):
            return 'ses'
        elif mime_type in ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
            return 'belge'
        elif mime_type in ['application/zip', 'application/x-rar-compressed', 'application/x-7z-compressed']:
            return 'arşiv'
        elif mime_type in ['application/vnd.ms-powerpoint', 'application/vnd.openxmlformats-officedocument.presentationml.presentation']:
            return 'sunum'
        elif mime_type in ['font/ttf', 'font/otf', 'application/font-woff']:
            return 'font'
        elif mime_type in ['application/epub+zip', 'application/x-mobipocket-ebook']:
            return 'e-kitap'
        
        # Uzantıya göre kontrol
        extension = file_path.split('.')[-1].lower()
        for category, formats in ALLOWED_EXTENSIONS.items():
            if extension in formats:
                return category
                
        return None
    except Exception as e:
        print(f"Dosya türü algılama hatası: {str(e)}")
        return None

@app.route('/')
def index():
    form = ConversionForm()
    return render_template('index.html', 
                         form=form,
                         categories=ALLOWED_EXTENSIONS.keys(),
                         ALLOWED_EXTENSIONS=ALLOWED_EXTENSIONS)

@app.route('/convert', methods=['POST'])
def convert_file():
    form = ConversionForm()
    if form.validate_on_submit():
        file = form.file.data
        category = form.category.data
        target_format = form.target_format.data
        
        if file:
            # Dosya türünü algıla
            detected_category = detect_file_type(file.filename)
            if detected_category and detected_category != category:
                flash(f'Seçilen dosya türü ({detected_category}) ile kategori uyuşmuyor.', 'warning')
                return redirect(url_for('index'))
            
            if allowed_file(file.filename, category):
                file_content = file.read()
                if not allowed_file_size(len(file_content), current_user.is_authenticated):
                    flash('Dosya boyutu çok büyük. Lütfen daha küçük bir dosya seçin.', 'error')
                    return redirect(url_for('index'))
                
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
                # Dosyayı kaydet
                with open(filepath, 'wb') as f:
                    f.write(file_content)
                
                try:
                    output = None
                    if category == 'görsel':
                        output = convert_image(filepath, target_format)
                    elif category == 'video':
                        output = convert_video(filepath, target_format, current_user.is_authenticated)
                    elif category == 'ses':
                        output = convert_audio(filepath, target_format, current_user.is_authenticated)
                    elif category == 'belge':
                        output = convert_document(filepath, target_format, current_user.is_authenticated)
                    
                    if output:
                        # Orijinal dosya adından uzantıyı kaldır
                        original_name = os.path.splitext(filename)[0]
                        converted_filename = f"{original_name}.{target_format}"
                        
                        if current_user.is_authenticated:
                            conversion = Conversion(
                                user_id=current_user.id,
                                original_filename=filename,
                                converted_filename=converted_filename,
                                original_format=filename.split('.')[-1],
                                target_format=target_format
                            )
                            db.session.add(conversion)
                            db.session.commit()
                        
                        # Dönüştürülen dosyayı geçici olarak kaydet
                        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], converted_filename)
                        with open(temp_path, 'wb') as f:
                            f.write(output.getvalue())
                        
                        return jsonify({
                            'success': True,
                            'message': 'Dönüştürme başarılı',
                            'filename': converted_filename
                        })
                    
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

@app.route('/download/<filename>')
def download_file(filename):
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(filepath):
            return send_file(
                filepath,
                as_attachment=True,
                download_name=filename
            )
        return 'Dosya bulunamadı', 404
    except Exception as e:
        return str(e), 500
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            return redirect(url_for('index'))
        flash('E-posta veya şifre hatalı. Lütfen tekrar deneyin.', 'error')
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        existing_user = User.query.filter_by(username=form.username.data).first()
        if existing_user:
            flash('Bu kullanıcı adı zaten kullanılıyor. Lütfen başka bir kullanıcı adı seçin.', 'error')
            return render_template('register.html', form=form)
        existing_email = User.query.filter_by(email=form.email.data).first()
        if existing_email:
            flash('Bu e-posta adresi zaten kayıtlı. Lütfen başka bir e-posta adresi kullanın.', 'error')
            return render_template('register.html', form=form)
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        user.ip_address = request.remote_addr
        db.session.add(user)
        db.session.commit()
        flash('Kayıt başarılı! Giriş yapabilirsiniz.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

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

@app.route('/preview/<filename>')
def preview_file(filename):
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(filepath):
        return send_file(filepath)
    return 'Dosya bulunamadı', 404

@app.route('/share/<conversion_id>')
def share_file(conversion_id):
    conversion = Conversion.query.get_or_404(conversion_id)
    if conversion.user_id != current_user.id:
        return 'Bu dosyaya erişim izniniz yok', 403
    return send_file(
        os.path.join(app.config['UPLOAD_FOLDER'], conversion.converted_filename),
        as_attachment=True,
        download_name=conversion.converted_filename
    )

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

# WSGI için application değişkeni
application = app

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    application.run(debug=True, host='0.0.0.0', port=5000) 