from PIL import Image
import os

def convert_image(input_path, target_format):
    """
    input_path: Yüklü dosyanın tam yolu
    target_format: 'jpg' veya 'png'
    """
    img = Image.open(input_path)
    base, _ = os.path.splitext(input_path)
    output_path = f"{base}_converted.{target_format}"
    if target_format == 'jpg':
        img = img.convert('RGB')  # PNG'den JPG'ye dönüşümde gerekebilir
    img.save(output_path, target_format.upper())
    return output_path 