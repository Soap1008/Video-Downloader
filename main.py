import os
import time
import subprocess
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
import yt_dlp

app = FastAPI(title="Video Downloader")

# Pobieramy dokładny katalog, w którym fizycznie znajduje się ten plik (main.py)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def clean_old_files(max_age_hours=24):
    """Usuwa pliki starsze niż określona liczba godzin"""
    now = time.time()
    max_age_seconds = max_age_hours * 3600
    if os.path.exists(DOWNLOAD_DIR):
        for f in os.listdir(DOWNLOAD_DIR):
            file_path = os.path.join(DOWNLOAD_DIR, f)
            if os.path.isfile(file_path):
                if now - os.path.getmtime(file_path) > max_age_seconds:
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass

class URLRequest(BaseModel):
    url: str

@app.get("/", response_class=HTMLResponse)
def read_root():
    """Serwuje główny interfejs użytkownika"""
    index_path = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "Brak pliku index.html w katalogu aplikacji."

@app.get("/manifest.json")
def get_manifest():
    path = os.path.join(BASE_DIR, "manifest.json")
    if os.path.exists(path):
        return FileResponse(path, media_type="application/json")
    raise HTTPException(status_code=404, detail="Brak pliku manifest.json")

@app.get("/sw.js")
def get_sw():
    path = os.path.join(BASE_DIR, "sw.js")
    if os.path.exists(path):
        return FileResponse(path, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="Brak pliku sw.js")

@app.get("/ikona.png")
def get_icon():
    path = os.path.join(BASE_DIR, "ikona.png")
    if os.path.exists(path):
        return FileResponse(path, media_type="image/png")
    raise HTTPException(status_code=404, detail="Nie znaleziono pliku ikona.png")

@app.post("/api/download")
def download_video(data: URLRequest):
    url = data.url
    if not url:
        raise HTTPException(status_code=400, detail="Brak adresu URL")

    # Automatycznie porządkujemy stare pliki przy każdej próbie pobrania
    clean_old_files(max_age_hours=24)

    ydl_opts = {
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),
        'format': 'best',
        'restrictfilenames': True,
        'noplaylist': True,
    }

    try:
        # 1. Pobieranie pliku przez yt-dlp
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
        if not os.path.exists(filename):
            raise HTTPException(status_code=500, detail="Nie udało się pobrać pliku wideo.")

        # 2. Przygotowanie ścieżki dla przekonwertowanego pliku MP4
        base_path, _ = os.path.splitext(filename)
        fixed_filename = base_path + "_fixed.mp4"

        # 3. Konwersja przez FFmpeg dla pełnej kompatybilności z Windows/telefonami
        ffmpeg_cmd = [
            'ffmpeg', '-y', '-i', filename,
            '-c:v', 'libx264', '-c:a', 'aac',
            fixed_filename
        ]
        
        result = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if result.returncode == 0 and os.path.exists(fixed_filename):
            final_file = fixed_filename
            try:
                os.remove(filename)  # Usuwamy surowy plik tymczasowy
            except:
                pass
        else:
            final_file = filename

        return FileResponse(
            path=final_file,
            filename=os.path.basename(final_file),
            media_type='application/octet-stream'
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))