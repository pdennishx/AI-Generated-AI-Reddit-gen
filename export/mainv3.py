import os
import sys
import random
import threading
import asyncio
import re
import whisper
import torch
import customtkinter as ctk
from PIL import Image
import ollama
import edge_tts

# MoviePy Settings
magick_path = r"C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe"
os.environ["IMAGEMAGICK_BINARY"] = magick_path
from moviepy.config import change_settings
change_settings({"IMAGEMAGICK_BINARY": magick_path})
from moviepy.editor import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip
import moviepy.video.fx.all as vfx

# --- INITIAL SETTINGS ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

class VideoGenerator:
    def __init__(self, log_callback):
        self.log = log_callback
        self.whisper_model = None

    def load_whisper(self, model_type="base"):
        self.log(f"🧠 Lade Whisper {model_type}...")
        self.whisper_model = whisper.load_model(model_type)
        self.log("✅ Modell bereit.")

    def generate_story(self, topic, words, model_name):
        self.log(f"📝 KI schreibt Story über: {topic}...")
        prompt = f"Schreibe eine fesselnde Reddit-Story zu '{topic}'. Ca. {words} Wörter. Kurze Sätze. Deutsch."
        try:
            response = ollama.chat(model=model_name, messages=[{'role': 'user', 'content': prompt}])
            text = response['message']['content']
            text = re.sub(r"^(Hier ist|Sicher|Gerne).*?[:\n]", "", text, flags=re.IGNORECASE | re.DOTALL)
            return text.replace('"', '').strip()
        except Exception as e:
            self.log(f"❌ Ollama Error: {e}")
            return None

    def create_video(self, config, audio_path, story_text):
        self.log("🎬 Starte Video-Rendering...")
        
        # Whisper Sync
        result = self.whisper_model.transcribe(audio_path, word_timestamps=True, language="de")
        
        audio = AudioFileClip(audio_path).fx(vfx.speedx, config['speed'])
        videos = [f for f in os.listdir(config['v_folder']) if f.endswith(('.mp4', '.mov'))]
        
        video_clip = VideoFileClip(os.path.join(config['v_folder'], random.choice(videos))).without_audio()
        if video_clip.duration < audio.duration:
            video_clip = video_clip.fx(vfx.loop, duration=audio.duration + 0.5)
            
        video_clip = video_clip.subclip(0, audio.duration + 0.2).set_audio(audio)
        
        subs = []
        for segment in result['segments']:
            for w in segment['words']:
                txt = TextClip(w['word'].strip().upper(), font='Impact', 
                               fontsize=config['f_size'], color=random.choice(config['colors']),
                               stroke_color='black', stroke_width=2, method='label')
                
                # Sync & Speed Korrektur
                start = w['start'] / config['speed']
                end = w['end'] / config['speed']
                
                txt = txt.set_start(start).set_duration(end - start).set_position('center')
                if config['zoom']:
                    txt = txt.fx(vfx.resize, lambda t: 0.8 + 2*t if t < 0.1 else 1.0)
                subs.append(txt)

        final = CompositeVideoClip([video_clip] + subs)
        out_name = os.path.join(config['out'], f"viral_{random.randint(100,999)}.mp4")
        final.write_videofile(out_name, codec='libx264', audio_codec='aac', fps=24, threads=4, preset='ultrafast')
        return out_name

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("VIRAL ENGINE V6 PRO")
        self.geometry("1000x900")

        # Background Image
        if os.path.exists("wallpaper.png"):
            self.bg_img = ctk.CTkImage(Image.open("wallpaper.png"), size=(1000, 900))
            self.bg_lbl = ctk.CTkLabel(self, image=self.bg_img, text="")
            self.bg_lbl.place(x=0, y=0)

        # Main Layout (Karten-Stil)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.main_frame = ctk.CTkScrollableFrame(self, fg_color="#0a0a0a", border_width=2, border_color="#00FF00", corner_radius=15)
        self.main_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.8, relheight=0.85)

        # Title
        ctk.CTkLabel(self.main_frame, text="⚡ VIRAL ENGINE PRO", font=("Impact", 40), text_color="#00FF00").pack(pady=20)

        # --- SETTINGS SECTION ---
        self.create_card("📝 Story Content")
        self.topic_entry = self.add_input("Thema / Prompt:", "z.B. Horror Reddit Story")
        self.word_slider = self.add_slider("Länge (Wörter):", 50, 500, 150)
        
        self.create_card("🎙️ Voice & Sync")
        self.speed_slider = self.add_slider("Sprech-Geschwindigkeit:", 1.0, 2.0, 1.25)
        self.whisper_var = self.add_dropdown("Whisper Modell:", ["tiny", "base", "small"], "base")
        
        self.create_card("🎨 Visuals")
        self.font_slider = self.add_slider("Schriftgröße:", 40, 150, 90)
        self.zoom_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(self.last_card, text="Pop-In Animation (Zoom)", variable=self.zoom_var, text_color="white").pack(pady=5)

        # --- CONTROL SECTION ---
        self.btn = ctk.CTkButton(self.main_frame, text="GENERATE CONTENT 🚀", height=60, font=("Impact", 25), 
                                 fg_color="#00FF00", text_color="black", hover_color="#00CC00", command=self.start_process)
        self.btn.pack(pady=30, fill="x", padx=40)

        self.log_box = ctk.CTkTextbox(self.main_frame, height=150, fg_color="#111", text_color="#00FF00", border_color="#333", border_width=1)
        self.log_box.pack(pady=10, fill="x", padx=20)

        self.gen = VideoGenerator(self.log)

    def create_card(self, title):
        self.last_card = ctk.CTkFrame(self.main_frame, fg_color="#1a1a1a", corner_radius=10, border_width=1, border_color="#333")
        self.last_card.pack(pady=10, fill="x", padx=20)
        ctk.CTkLabel(self.last_card, text=title, font=("Impact", 20), text_color="#00FF00").pack(pady=5)

    def add_input(self, label, placeholder):
        ctk.CTkLabel(self.last_card, text=label, text_color="gray").pack()
        entry = ctk.CTkEntry(self.last_card, placeholder_text=placeholder, width=400, border_color="#00FF00")
        entry.pack(pady=5)
        return entry

    def add_slider(self, label, start, end, default):
        lbl = ctk.CTkLabel(self.last_card, text=f"{label} {default}", text_color="gray")
        lbl.pack()
        slider = ctk.CTkSlider(self.last_card, from_=start, to=end, command=lambda v: lbl.configure(text=f"{label} {round(v, 2)}"))
        slider.set(default)
        slider.pack(pady=5)
        return slider

    def add_dropdown(self, label, values, default):
        ctk.CTkLabel(self.last_card, text=label, text_color="gray").pack()
        var = ctk.StringVar(value=default)
        dd = ctk.CTkOptionMenu(self.last_card, values=values, variable=var, fg_color="#333", button_color="#00FF00", button_hover_color="#00CC00")
        dd.pack(pady=5)
        return var

    def log(self, msg):
        self.log_box.insert("end", f">> {msg}\n")
        self.log_box.see("end")

    def start_process(self):
        self.btn.configure(state="disabled")
        threading.Thread(target=self.work, daemon=True).start()

    def work(self):
        config = {
            'speed': self.speed_slider.get(),
            'f_size': int(self.font_slider.get()),
            'zoom': self.zoom_var.get(),
            'v_folder': "background_videos",
            'out': "output_shorts",
            'colors': ['#FF00FF', '#00FFFF', '#FFFF00', '#00FF00', '#FFFFFF']
        }
        
        topic = self.topic_entry.get()
        if not topic:
            self.log("⚠️ Bitte Thema eingeben!")
            self.btn.configure(state="normal")
            return

        # 1. Whisper laden falls nötig
        if not self.gen.whisper_model:
            self.gen.load_whisper(self.whisper_var.get())

        # 2. Story
        story = self.gen.generate_story(topic, int(self.word_slider.get()), "llama3")
        
        if story:
            # 3. Audio
            audio_file = f"temp_voice.mp3"
            asyncio.run(edge_tts.Communicate(story, "de-DE-KillianNeural").save(audio_file))
            
            # 4. Video
            try:
                final_path = self.gen.create_video(config, audio_file, story)
                self.log(f"💎 ERFOLG: {final_path}")
            except Exception as e:
                self.log(f"❌ Fehler: {e}")
            
            if os.path.exists(audio_file): os.remove(audio_file)
            
        self.btn.configure(state="normal")

if __name__ == "__main__":
    app = App()
    app.mainloop()
