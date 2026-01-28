@echo off
echo ==========================================
echo   VIRAL ENGINE V9 - INSTALLER
echo ==========================================

:: Erstelle virtuelle Umgebung
python -m venv venv
call venv\Scripts\activate

:: Upgrade pip
python -m pip install --upgrade pip

:: Installiere PyTorch (CUDA Version fuer schnellere Whisper-Transkription)
echo Installiere PyTorch mit CUDA Support...
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

:: Installiere die restlichen Requirements
echo Installiere Python-Bibliotheken...
pip install openai-whisper customtkinter Pillow ollama edge-tts moviepy matplotlib

echo.
echo ------------------------------------------
echo FERTIG! 
echo WICHTIG: Stelle sicher, dass ImageMagick installiert ist unter:
echo C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe
echo ------------------------------------------
pause