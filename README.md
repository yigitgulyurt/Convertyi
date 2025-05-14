# Dosya Dönüştürücü

Bu proje, kullanıcıların dosyalarını farklı formatlara kolayca dönüştürebilmelerini sağlayan bir web uygulaması ve Telegram botu içerir.

## Özellikler

- **Web Arayüzü**
  - JPG ↔ PNG dönüşümü
  - MP4 → MP3 dönüşümü
  - Dosya boyutu sınırı (20MB)
  - Kullanıcı dostu ve basit arayüz

- **Telegram Botu**
  - Gönderilen dosyanın formatını otomatik algılama
  - Dosya boyutu kontrolü
  - Kolay ve hızlı kullanım

## Kurulum

1. Gerekli Python paketlerini yükleyin:
   ```bash
   pip install -r requirements.txt
   ```

2. Ortam değişkenleri için `.env` dosyasını oluşturun:
   ```bash
   cp .env.example .env
   ```
   Ardından `.env` dosyasını düzenleyin.

3. Geçici dosyalar için klasör oluşturun:
   ```bash
   mkdir temp
   ```

## Kullanım

### Web Uygulaması
```bash
python app.py
```
Tarayıcıda `http://localhost:5000` adresine giderek uygulamayı kullanabilirsiniz.

### Telegram Botu
```bash
python telegram_bot.py
```
Telegram'da bota dosya göndererek dönüştürme işlemini başlatabilirsiniz.

## Desteklenen Formatlar

- **Görsel**
  - JPG/JPEG ↔ PNG
- **Video**
  - MP4 → MP3

## Güvenlik

- Dosya boyutu sınırı (20MB)
- Güvenli dosya isimlendirme
- Geçici dosyaların otomatik temizlenmesi
- Sadece izin verilen dosya türlerinin kabul edilmesi

## Katkı ve Geliştirme

- Yeni format desteği eklemek için `converters/` klasörüne yeni bir dönüştürücü modülü ekleyin ve ilgili dosyalarda gerekli güncellemeleri yapın.
- Yeni özellikler eklemek için ilgili modülleri güncelleyip test edin.

