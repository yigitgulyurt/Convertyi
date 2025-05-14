from moviepy.editor import VideoFileClip
import os

def convert_video(input_path, target_format):
    """
    input_path: Yüklü dosyanın tam yolu
    target_format: 'mp3'
    """
    if target_format != 'mp3':
        raise ValueError('Şu anda sadece MP4 -> MP3 destekleniyor.')
    base, _ = os.path.splitext(input_path)
    output_path = f"{base}_converted.{target_format}"
    video = VideoFileClip(input_path)
    video.audio.write_audiofile(output_path)
    video.close()
    return output_path 