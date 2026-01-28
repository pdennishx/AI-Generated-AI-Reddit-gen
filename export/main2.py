import os
import sys
import random
import threading
import asyncio
import re
import whisper
import torch

# --- IMAGEMAGICK PFAD ---
magick_path = r"C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe"
os.environ["IMAGEMAGICK_BINARY"] = magick_path

import customtkinter as ctk
from PIL import Image
import ollama
import edge_tts
from moviepy.config import change_settings
change_settings({"IMAGEMAGICK_BINARY": magick_path})
from moviepy.editor import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip
import moviepy.video.fx.all as vfx

# --- EINSTELLUNGEN ---
BACKGROUND_IMAGE = "wallpaper.png"
VIDEO_FOLDER = "background_videos"
OUTPUT_FOLDER = "output_shorts"
PLAYBACK_SPEED = 1.25
DOPAMINE_COLORS = ['#FF00FF', '#00FFFF', '#FFFF00', '#00FF00', '#FF3D00', '#FFFFFF']

EMOJI_MAP = {
    "geld": "💰", "money": "💵", "schock": "😱", "polizei": "🚔", "liebe": "❤️", 
    "tot": "💀", "error": "❌", "feuer": "🔥", "wütend": "😡", "essen": "🍔", "kuss": "💋"
}

class VideoGenerator:
    def __init__(self, update_log_callback):
        self.log = update_log_callback
        self.log("🚀 Lade Whisper KI Modell (Base)...")
        self.whisper_model = whisper.load_model("base")

    def clean_ai_text(self, text):
        text = re.sub(r"^(Hier ist|Gerne|Hier eine Story|Text für|Sicher|Folgend).*?[:\n]", "", text, flags=re.IGNORECASE | re.DOTALL)
        return text.replace('"', '').replace('*', '').strip()

    def generate_story(self, topic, target_words):
        self.log(f"🧠 Generiere Story: {topic}...")
        prompt = f"Schreibe eine fesselnde Reddit-Story zu '{topic}'. Ungefähr {target_words} Wörter. Starte direkt. Kurze Sätze. Deutsch."
        try:
            response = ollama.chat(model='llama3', messages=[{'role': 'user', 'content': prompt}])
            return self.clean_ai_text(response['message']['content'])
        except: return None

    async def generate_audio(self, text, filename):
        communicate = edge_tts.Communicate(text, "de-DE-KillianNeural")
        await communicate.save(filename)
        return filename

    def get_word_timestamps(self, audio_path):
        self.log("🎙️ Whisper analysiert Sprach-Timing...")
        result = self.whisper_model.transcribe(audio_path, word_timestamps=True, language="de")
        words_data = []
        for segment in result['segments']:
            for word in segment['words']:
                words_data.append({
                    "word": word['word'].strip(),
                    "start": word['start'] / PLAYBACK_SPEED, # Korrektur für Playback Speed
                    "end": word['end'] / PLAYBACK_SPEED
                })
        return words_data

    def create_video(self, words_data, audio_tmp, font_size, mode):
        self.log(f"🎬 Rendering {mode}...")
        
        audio = AudioFileClip(audio_tmp).fx(vfx.speedx, PLAYBACK_SPEED)
        videos = [f for f in os.listdir(VIDEO_FOLDER) if f.endswith(('.mp4', '.mov'))]
        if not videos: return
        
        video_clip = VideoFileClip(os.path.join(VIDEO_FOLDER, random.choice(videos))).without_audio()
        
        if video_clip.duration < audio.duration:
            video_clip = video_clip.fx(vfx.loop, duration=audio.duration + 0.5)

        start_time = random.uniform(0, max(0, video_clip.duration - audio.duration - 1))
        video_clip = video_clip.subclip(start_time, start_time + audio.duration + 0.2).set_audio(audio)

        subs = []
        if mode == "Word-by-Word":
            for data in words_data:
                word = data["word"]
                clean_word = word.lower().strip(".,!?")
                display_word = word.upper()
                if clean_word in EMOJI_MAP: display_word += f" {EMOJI_MAP[clean_word]}"

                color = random.choice(DOPAMINE_COLORS)
                txt = TextClip(display_word, font='Impact', fontsize=font_size, color=color, 
                               stroke_color='black', stroke_width=4, method='label')
                
                duration = data["end"] - data["start"]
                txt = (txt.set_start(data["start"])
                          .set_duration(duration)
                          .set_position('center')
                          .fx(vfx.resize, lambda t: 0.8 + 2*t if t < 0.1 else 1.0))
                subs.append(txt)
        
        else: # Sentence Mode mit Whisper Sync
            sentence_group = []
            for i, data in enumerate(words_data):
                sentence_group.append(data)
                # Wenn Punkt oder letztes Wort, dann als Satz rendern
                if any(char in data["word"] for char in ".!?") or i == len(words_data) - 1:
                    full_text = " ".join([w["word"] for w in sentence_group]).upper()
                    s_start = sentence_group[0]["start"]
                    s_end = sentence_group[-1]["end"]
                    
                    txt = TextClip(full_text, font='Impact', fontsize=font_size-20, color="white", 
                                   stroke_color='black', stroke_width=3, method='caption', size=(video_clip.w*0.8, None))
                    txt = txt.set_start(s_start).set_duration(s_end - s_start).set_position('center')
                    subs.append(txt)
                    sentence_group = []

        final_video = CompositeVideoClip([video_clip] + subs)
        out_path = os.path.join(OUTPUT_FOLDER, f"short_{random.randint(1000,9999)}.mp4")
        final_video.write_videofile(out_path, codec='libx264', audio_codec='aac', fps=24, preset='ultrafast', threads=4)
        audio.close(); video_clip.close()

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Dopamine Viral Engine V6 - Whisper Edition")
        self.geometry("900x850")

        # Hintergrundbild setzen
        if os.path.exists(BACKGROUND_IMAGE):
            self.bg_image = ctk.CTkImage(Image.open(BACKGROUND_IMAGE), size=(900, 850))
            self.bg_label = ctk.CTkLabel(self, image=self.bg_image, text="")
            self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)

        self.frame = ctk.CTkFrame(self, fg_color="transparent") # Transparent damit Bild sichtbar
        self.inner_frame = ctk.CTkFrame(self.frame, fg_color="#000000", corner_radius=20, border_width=2, border_color="#00FF00")
        self.inner_frame.pack(expand=True, fill="both", padx=20, pady=20)
        self.frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.85, relheight=0.95)

        ctk.CTkLabel(self.inner_frame, text="⚡ WHISPER SYNC V6", font=("Impact", 45), text_color="#00FF00").pack(pady=15)
        
        self.topic_input = ctk.CTkEntry(self.inner_frame, placeholder_text="THEMA...", width=450, height=40)
        self.topic_input.pack(pady=5)

        self.mode_var = ctk.StringVar(value="Word-by-Word")
        self.mode_switch = ctk.CTkSegmentedButton(self.inner_frame, values=["Word-by-Word", "Sentence"], variable=self.mode_var)
        self.mode_switch.pack(pady=15)

        self.word_slider = ctk.CTkSlider(self.inner_frame, from_=50, to=500)
        self.word_slider.set(150); self.word_slider.pack(pady=5)
        
        self.font_slider = ctk.CTkSlider(self.inner_frame, from_=40, to=150)
        self.font_slider.set(90); self.font_slider.pack(pady=5)

        self.btn = ctk.CTkButton(self.inner_frame, text="START HUSTLE 🚀", fg_color="#00FF00", text_color="black", font=("Impact", 22), height=60, command=self.start)
        self.btn.pack(pady=25)

        self.log_box = ctk.CTkTextbox(self.inner_frame, width=650, height=200, fg_color="#111", text_color="#00FF00")
        self.log_box.pack(pady=10)
        
        self.gen = VideoGenerator(self.update_log)

    def update_log(self, msg): self.log_box.insert("end", f">> {msg}\n"); self.log_box.see("end")
    def start(self):
        self.btn.configure(state="disabled")
        threading.Thread(target=self.work, daemon=True).start()

    def work(self):
        topic = self.topic_input.get()
        if not topic: self.btn.configure(state="normal"); return
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        story = self.gen.generate_story(topic, int(self.word_slider.get()))
        if story:
            audio_tmp = f"aud_{random.randint(100,999)}.mp3"
            loop.run_until_complete(self.gen.generate_audio(story, audio_tmp))
            
            # Whisper Syncing
            words_data = self.gen.get_word_timestamps(audio_tmp)
            
            try:
                self.gen.create_video(words_data, audio_tmp, int(self.font_slider.get()), self.mode_var.get())
                self.update_log("💎 VIDEO FERTIG!")
            except Exception as e:
                self.update_log(f"❌ Fehler: {e}")
            
            if os.path.exists(audio_tmp): os.remove(audio_tmp)
        
        self.btn.configure(state="normal")

if __name__ == "__main__":
    app = App()
    app.mainloop()
