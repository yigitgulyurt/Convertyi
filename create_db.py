from app import app, db

with app.app_context():
    # Veritabanı tablolarını oluştur
    db.create_all()
    print("Veritabanı tabloları başarıyla oluşturuldu!") 