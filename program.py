import os
import subprocess
import requests
import whisper
import random
import time
from datetime import timedelta
from google import genai

# ==========================================
# 1. YENİ API ANAHTARLARINIZI BURAYA GİRİN
# ==========================================
GEMINI_API_KEY = "BURAYA_YENI_GEMINI_ANAHTARINI_YAZ"
ELEVENLABS_API_KEY = "BURAYA_YENI_ELEVENLABS_ANAHTARINI_YAZ"
VOICE_ID = "IKne3meq5aSn9XLyUdCD" 

client = genai.Client(api_key=GEMINI_API_KEY)

# ==========================================
# 2. KLASÖR YAPISI VE AYARLAR
# ==========================================
KLASORLER = ["stok_videolar", "sesler", "altyazilar", "bitmis_videolar"]
URETILECEK_VIDEO_SAYISI = 14 # Tek seferde kaç video üretilecek?

# Klasörler yoksa otomatik oluşturulur
for klasor in KLASORLER:
    os.makedirs(klasor, exist_ok=True)

def metin_uret_gemini():
    prompt = """
    Sen usta bir tarihçi ve felsefe arşivcisisin. 
    Bana Marcus Aurelius, Seneca, Epictetos veya Zeno gibi gerçek Stoacı filozofların tarihte bizzat söylediği, doğrulanmış ve etkileyici bir sözünü ver. 

    Kurallar:
    1. Söz, Instagram Reels'te tok bir sesle okunduğunda tam 15 saniye (yaklaşık 25-35 kelime) sürecek uzunlukta olmalı.
    2. Her defasında daha önce pek duyulmamış, derinliği olan farklı bir söz seç.
    3. Sözün bittiği yere bir boşluk bırakıp tire (-) koyarak sadece filozofun adını yaz.
    4. Sadece ve sadece metni ver. Tırnak işareti, başlık, hashtag, açıklama veya ekstra hiçbir kelime ekleme.
    """
    
    max_deneme = 3
    for deneme in range(max_deneme):
        try:
            response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
            metin = response.text.replace('"', '').replace('\n', ' ').strip()
            return metin
        except Exception as hata:
            if "503" in str(hata) or "UNAVAILABLE" in str(hata):
                print(f"   [!] Sunucu yoğun. {deneme+1}. deneme başarısız. 5 sn bekleniyor...")
                time.sleep(5)
            else:
                raise hata 
    raise Exception("Gemini sunucuları şu an çok yoğun.")

def ses_uret(metin, kayit_yolu):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    headers = {"Accept": "audio/mpeg", "Content-Type": "application/json", "xi-api-key": ELEVENLABS_API_KEY}
    data = {"text": metin, "model_id": "eleven_multilingual_v2", "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}
    
    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 200:
        with open(kayit_yolu, 'wb') as f:
            f.write(response.content)
    else:
        raise Exception(f"ElevenLabs Hatası: {response.text}")

def format_zaman(saniye):
    td = timedelta(seconds=saniye)
    toplam_saniye = int(td.total_seconds())
    saat = toplam_saniye // 3600
    dakika = (toplam_saniye % 3600) // 60
    saniye = toplam_saniye % 60
    milisaniye = int(td.microseconds / 1000)
    return f"{saat:02d}:{dakika:02d}:{saniye:02d},{milisaniye:03d}"

def altyazi_uret(ses_yolu, srt_yolu):
    model = whisper.load_model("base") 
    sonuc = model.transcribe(ses_yolu, language="tr")
    
    with open(srt_yolu, "w", encoding="utf-8") as f:
        for i, segment in enumerate(sonuc["segments"], start=1):
            baslangic = format_zaman(segment["start"])
            bitis = format_zaman(segment["end"])
            metin = segment["text"].strip()
            f.write(f"{i}\n{baslangic} --> {bitis}\n{metin}\n\n")

def videoyu_olustur(arkaplan_yolu, ses_yolu, srt_yolu, cikti_yolu):
    # Windows yollarındaki ters slash işaretlerini, FFmpeg'in hata vermemesi için düz slash yapıyoruz
    srt_yolu_ffmpeg = srt_yolu.replace("\\", "/")
    
    ffmpeg_komutu = (
        f'ffmpeg -y -i "{arkaplan_yolu}" -i "{ses_yolu}" '
        f'-vf "crop=\'ih*9/16:ih\',scale=1080:1920,subtitles={srt_yolu_ffmpeg}:force_style=\'FontSize=22,PrimaryColour=&H0000FFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=1,Alignment=2,Bold=-1,MarginV=45\'" '
        f'-c:v libx264 -c:a aac -shortest "{cikti_yolu}" -loglevel error'
    )
    subprocess.run(ffmpeg_komutu, shell=True)

if __name__ == "__main__":
    print(f"--- İÇERİK FABRİKASI BAŞLATILDI ({URETILECEK_VIDEO_SAYISI} Video Üretilecek) ---")
    
    # 1. Stok videoları bul
    stok_videolar = [f for f in os.listdir("stok_videolar") if f.endswith((".mp4", ".mov"))]
    
    if not stok_videolar:
        print("HATA: 'stok_videolar' klasörü boş! Lütfen içine birkaç arkaplan videosu atın.")
        exit()

    print(f"Bulunan stok video sayısı: {len(stok_videolar)}")

    for i in range(1, URETILECEK_VIDEO_SAYISI + 1):
        print(f"\n[{i}/{URETILECEK_VIDEO_SAYISI}] Video hazırlanıyor...")
        try:
            # Dosya yollarını belirle
            ses_yolu = os.path.join("sesler", f"ses_{i}.mp3")
            srt_yolu = os.path.join("altyazilar", f"altyazi_{i}.srt")
            cikti_yolu = os.path.join("bitmis_videolar", f"motivasyon_reels_{i}.mp4")
            
            # Arkaplanı rastgele seç
            secilen_arkaplan = random.choice(stok_videolar)
            arkaplan_yolu = os.path.join("stok_videolar", secilen_arkaplan)
            
            print(" -> Metin yazılıyor...")
            metin = metin_uret_gemini()
            
            print(" -> Seslendiriliyor...")
            ses_uret(metin, ses_yolu)
            
            print(" -> Altyazı çıkarılıyor (Whisper)...")
            altyazi_uret(ses_yolu, srt_yolu)
            
            print(f" -> Video kurgulanıyor (Kullanılan arkaplan: {secilen_arkaplan})...")
            videoyu_olustur(arkaplan_yolu, ses_yolu, srt_yolu, cikti_yolu)
            
            print(f" [BAŞARILI] motivasyon_reels_{i}.mp4 hazır!")
            
            # API'leri üst üste yormamak için her videodan sonra ufak bir mola
            time.sleep(2)
            
        except Exception as e:
            print(f" [HATA] {i}. video üretilirken bir sorun oluştu: {e}")

    print("\n--- TÜM İŞLEMLER TAMAMLANDI! Videolar 'bitmis_videolar' klasöründe seni bekliyor. ---")