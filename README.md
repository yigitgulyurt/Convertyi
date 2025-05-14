# Dosya Dönüştürücü

Bu proje, kullanıcıların dosyalarını farklı formatlara dönüştürmelerini sağlayan bir web uygulaması ve Telegram botudur.

## Özellikler

- **Web Arayüzü**
  - JPG ↔ PNG dönüşümü
  - MP4 → MP3 dönüşümü
  - Dosya boyutu sınırlaması (20MB)
  - Kullanıcı dostu arayüz

- **Telegram Botu**
  - Otomatik format tanıma
  - Dosya boyutu kontrolü
  - Kolay kullanım

## Kurulum

1. Gerekli paketleri yükleyin:
   ```bash
   pip install -r requirements.txt
   ```

2. `.env` dosyasını oluşturun:
   ```bash
   cp .env.example .env
   ```
   `.env` dosyasını düzenleyerek gerekli değişkenleri ayarlayın.

3. Geçici dosya dizinini oluşturun:
   ```bash
   mkdir temp
   ```

## Kullanım

### Web Uygulaması
```bash
python app.py
```
Tarayıcıda `http://localhost:5000` adresine gidin.

### Telegram Botu
```bash
python telegram_bot.py
```
Botu Telegram'da başlatın ve dosya gönderin.

## Desteklenen Formatlar

- **Görsel**
  - JPG/JPEG → PNG
  - PNG → JPG

- **Video**
  - MP4 → MP3

## Güvenlik

- Dosya boyutu sınırlaması
- Güvenli dosya isimlendirme
- Geçici dosyaların otomatik temizlenmesi
- İzin verilen dosya türleri kontrolü

## Geliştirme

1. Yeni format desteği eklemek için:
   - `converters/` klasörüne yeni bir dönüştürücü modülü ekleyin
   - `app.py` ve `telegram_bot.py` dosyalarında gerekli güncellemeleri yapın

2. Yeni özellik eklemek için:
   - İlgili modülleri güncelleyin
   - Gerekli testleri yapın

## Lisans

MIT 