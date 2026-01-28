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
try:
    import matplotlib.font_manager as fm
except ImportError:
    os.system('pip install matplotlib')
    import matplotlib.font_manager as fm

# MoviePy Settings
magick_path = r"C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe"
os.environ["IMAGEMAGICK_BINARY"] = magick_path
from moviepy.config import change_settings
change_settings({"IMAGEMAGICK_BINARY": magick_path})
from moviepy.editor import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, ColorClip
import moviepy.video.fx.all as vfx

# --- INITIAL SETTINGS ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

def get_system_fonts():
    fonts = sorted(list(set([f.name for f in fm.fontManager.ttflist])))
    return [f for f in fonts if len(f) < 20 and not f.startswith("@")]

SYSTEM_FONTS = get_system_fonts()
COLOR_PRESETS = {
    "Dopamine (Random)": ['#FF00FF', '#00FFFF', '#FFFF00', '#00FF00', '#FF3D00', '#FFFFFF'],
    "Cyberpunk": ['#fdf000', '#ff003c', '#00e0ff', '#711c91'],
    "Minimal White": ['#FFFFFF'],
    "Toxic Green": ['#00FF00', '#ADFF2F'],
    "Fire & Ice": ['#FF4500', '#1E90FF'],
    "Gold & Black": ['#FFD700', '#B8860B']
}

class VideoGenerator:
    def __init__(self, log_callback):
        self.log = log_callback
        self.whisper_model = None

    def load_whisper(self, model_type):
        if not self.whisper_model:
            self.log(f"🧠 Lade Whisper {model_type}...")
            self.whisper_model = whisper.load_model(model_type)

    def create_video(self, config, audio_path, story_text):
        self.log("🎬 Rendering gestartet...")
        result = self.whisper_model.transcribe(audio_path, word_timestamps=True, language="de")
        
        audio = AudioFileClip(audio_path).fx(vfx.speedx, config['speed'])
        videos = [f for f in os.listdir("background_videos") if f.endswith(('.mp4', '.mov'))]
        
        video_clip = VideoFileClip(os.path.join("background_videos", random.choice(videos))).without_audio()
        if video_clip.duration < audio.duration:
            video_clip = video_clip.fx(vfx.loop, duration=audio.duration + 0.5)
            
        video_clip = video_clip.subclip(0, audio.duration + 0.2).set_audio(audio)
        if config['darken'] > 0:
            video_clip = video_clip.fx(vfx.colorx, 1 - config['darken'])

        subs = []
        for segment in result['segments']:
            for w in segment['words']:
                word_text = w['word'].strip().upper()
                preset_list = COLOR_PRESETS.get(config['color_mode'], ['#FFFFFF'])
                chosen_color = random.choice(preset_list)

                txt = TextClip(word_text, font=config['font'], 
                               fontsize=config['f_size'], color=chosen_color,
                               stroke_color='black', stroke_width=config['stroke'], method='label')
                
                start = w['start'] / config['speed']
                end = w['end'] / config['speed']
                pos = ('center', config['pos_y']) 

                if config['bg_box']:
                    bg = ColorClip(size=(txt.w + 25, txt.h + 15), color=(0,0,0)).set_opacity(0.7)
                    bg = bg.set_start(start).set_duration(end - start).set_position(pos)
                    subs.append(bg)

                txt = txt.set_start(start).set_duration(end - start).set_position(pos)
                if config['zoom']:
                    txt = txt.fx(vfx.resize, lambda t: 0.8 + 1.5*t if t < 0.1 else 1.0)
                subs.append(txt)

        final = CompositeVideoClip([video_clip] + subs)
        if not os.path.exists("output_shorts"): os.makedirs("output_shorts")
        out_name = os.path.join("output_shorts", f"viral_{random.randint(1000,9999)}.mp4")
        final.write_videofile(out_name, codec='libx264', audio_codec='aac', fps=24, threads=4, preset='ultrafast')
        return out_name

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("VIRAL ENGINE V9 - AUTO-PILOT")
        self.geometry("1200x950")
        self.is_running = False

        if os.path.exists("wallpaper.png"):
            self.bg_img = ctk.CTkImage(Image.open("wallpaper.png"), size=(1200, 950))
            ctk.CTkLabel(self, image=self.bg_img, text="").place(x=0, y=0)

        self.main_frame = ctk.CTkScrollableFrame(self, fg_color="#0a0a0a", border_width=2, border_color="#00FF00")
        self.main_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.9, relheight=0.9)

        ctk.CTkLabel(self.main_frame, text="🤖 VIRAL AUTO-PILOT V9", font=("Impact", 50), text_color="#00FF00").pack(pady=20)

        self.settings_grid = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.settings_grid.pack(fill="x", padx=20)

        # CARD 1: STORY & AUTO-PILOT
        self.card_story = self.create_card(self.settings_grid, "📝 CONTENT ENGINE", 0, 0)
        self.topic_entry = self.add_input(self.card_story, "Start-Thema:", "Creepypasta Deutsch")
        self.word_slider = self.add_slider(self.card_story, "Wörter:", 30, 600, 150)
        
        self.auto_pilot_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(self.card_story, text="INFINITE MODE (Ähnliche Themen finden)", variable=self.auto_pilot_var, text_color="#00FF00", font=("Arial", 14, "bold")).pack(pady=10)

        # CARD 2: VOICE
        self.card_voice = self.create_card(self.settings_grid, "🎙️ VOICE & SYNC", 0, 1)
        self.voice_var = self.add_dropdown(self.card_voice, "Stimme:", ["Killian (Männlich)", "Conrad (Männlich)", "Katja (Weiblich)", "Amala (Weiblich)"], "Killian (Männlich)")
        self.speed_slider = self.add_slider(self.card_voice, "Speed:", 0.5, 2.0, 1.25)
        self.whisper_var = self.add_dropdown(self.card_voice, "Whisper-Model:", ["tiny", "base", "small"], "base")

        # CARD 3: TYPO
        self.card_typo = self.create_card(self.settings_grid, "🎨 TYPO & PREVIEW", 1, 0)
        self.font_var = self.add_dropdown(self.card_typo, "Schriftart:", SYSTEM_FONTS, "Impact" if "Impact" in SYSTEM_FONTS else SYSTEM_FONTS[0], command=self.update_preview)
        self.color_var = self.add_dropdown(self.card_typo, "Color Theme:", list(COLOR_PRESETS.keys()), "Dopamine (Random)", command=self.update_preview)
        self.preview_lbl = ctk.CTkLabel(self.card_typo, text="VORSCHAU", font=("Impact", 35), text_color="#00FF00")
        self.preview_lbl.pack(pady=10)
        self.font_slider = self.add_slider(self.card_typo, "Größe:", 20, 200, 80)
        self.stroke_slider = self.add_slider(self.card_typo, "Randstärke:", 0, 10, 2)

        # CARD 4: FX
        self.card_fx = self.create_card(self.settings_grid, "🎬 VIDEO FX", 1, 1)
        self.pos_var = self.add_dropdown(self.card_fx, "Position (Y):", ["center", "top", "bottom"], "center")
        self.dark_slider = self.add_slider(self.card_fx, "Video abdunkeln:", 0.0, 1.0, 0.4)
        self.zoom_v = ctk.BooleanVar(value=True); self.box_v = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(self.card_fx, text="Zoom-FX", variable=self.zoom_v).pack(pady=2)
        ctk.CTkCheckBox(self.card_fx, text="Text-Box", variable=self.box_v).pack(pady=2)

        # BUTTONS
        self.btn = ctk.CTkButton(self.main_frame, text="START CONTENT HUSTLE 🚀", height=80, font=("Impact", 32), fg_color="#00FF00", text_color="black", command=self.toggle_process)
        self.btn.pack(pady=30, fill="x", padx=100)

        self.log_box = ctk.CTkTextbox(self.main_frame, height=200, fg_color="#111", text_color="#00FF00")
        self.log_box.pack(pady=10, fill="x", padx=20)
        
        self.gen = VideoGenerator(self.log)
        self.update_preview()

    def create_card(self, parent, title, r, c):
        f = ctk.CTkFrame(parent, fg_color="#161616", corner_radius=15, border_width=1, border_color="#333")
        f.grid(row=r, column=c, padx=10, pady=10, sticky="nsew")
        ctk.CTkLabel(f, text=title, font=("Impact", 22), text_color="#00FF00").pack(pady=10)
        return f

    def add_input(self, card, label, placeholder):
        ctk.CTkLabel(card, text=label).pack()
        e = ctk.CTkEntry(card, placeholder_text=placeholder, width=250); e.pack(pady=5); return e

    def add_slider(self, card, label, start, end, default):
        lbl = ctk.CTkLabel(card, text=f"{label} {default}")
        lbl.pack()
        s = ctk.CTkSlider(card, from_=start, to=end, command=lambda v: [lbl.configure(text=f"{label} {round(v, 2)}"), self.update_preview()])
        s.set(default); s.pack(pady=5); return s

    def add_dropdown(self, card, label, values, default, command=None):
        ctk.CTkLabel(card, text=label).pack()
        v = ctk.StringVar(value=default)
        ctk.CTkOptionMenu(card, values=values, variable=v, width=200, command=command).pack(pady=5); return v

    def update_preview(self, *args):
        try:
            self.preview_lbl.configure(font=(self.font_var.get(), 35), text_color=COLOR_PRESETS[self.color_var.get()][0])
        except: pass

    def log(self, msg):
        self.log_box.insert("end", f">> {msg}\n"); self.log_box.see("end")

    def toggle_process(self):
        if not self.is_running:
            self.is_running = True
            self.btn.configure(text="STOP HUSTLE 🛑", fg_color="red")
            threading.Thread(target=self.work_loop, daemon=True).start()
        else:
            self.is_running = False
            self.btn.configure(text="START CONTENT HUSTLE 🚀", fg_color="#00FF00")

    def work_loop(self):
        current_topic = self.topic_entry.get()
        v_map = {"Killian (Männlich)": "de-DE-KillianNeural", "Conrad (Männlich)": "de-DE-ConradNeural", "Katja (Weiblich)": "de-DE-KatjaNeural", "Amala (Weiblich)": "de-DE-AmalaNeural"}
        p_map = {"center": "center", "top": 0.2, "bottom": 0.8}

        self.gen.load_whisper(self.whisper_var.get())

        while self.is_running:
            try:
                self.log(f"🔥 Bearbeite Thema: {current_topic}")
                
                # 1. Story generieren
                prompt = f"Schreibe eine fesselnde Reddit-Story zu '{current_topic}'. benutze keine satzzeichen. Ungefähr {int(self.word_slider.get())} Wörter. Starte direkt mit der Story. Deutsch."
                story_resp = ollama.chat(model='llama3', messages=[{'role': 'user', 'content': prompt}])
                story = re.sub(r"^(Hier ist|Sicher|Gerne).*?[:\n]", "", story_resp['message']['content'], flags=re.IGNORECASE | re.DOTALL).strip()

                # 2. Audio generieren
                audio_file = f"temp_{random.randint(100,999)}.mp3"
                asyncio.run(edge_tts.Communicate(story, v_map[self.voice_var.get()]).save(audio_file))
                
                # 3. Video rendern
                config = {
                    'speed': self.speed_slider.get(), 'font': self.font_var.get(), 'f_size': int(self.font_slider.get()),
                    'color_mode': self.color_var.get(), 'stroke': self.stroke_slider.get(), 'zoom': self.zoom_v.get(),
                    'bg_box': self.box_v.get(), 'darken': self.dark_slider.get(), 'pos_y': p_map[self.pos_var.get()]
                }
                self.gen.create_video(config, audio_file, story)
                if os.path.exists(audio_file): os.remove(audio_file)

                # 4. Nächstes Thema finden oder stoppen
                if self.auto_pilot_var.get() and self.is_running:
                    self.log("🔍 Suche nach nächstem viralen Thema...")
                    next_prompt = f"Basierend auf dem Thema '{current_topic}', nenne mir ein einziges, ähnliches, extrem virales Reddit-Thema. Antworte NUR mit dem Thema, kein Satz drumherum."
                    next_resp = ollama.chat(model='llama3', messages=[{'role': 'user', 'content': next_prompt}])
                    current_topic = next_resp['message']['content'].strip().replace('"', '')
                else:
                    break # Stoppe wenn Infinite Mode aus ist

            except Exception as e:
                self.log(f"❌ Fehler: {e}")
                break

        self.is_running = False
        self.btn.configure(text="START CONTENT HUSTLE 🚀", fg_color="#00FF00")
        self.log("💎 LOOP BEENDET.")

if __name__ == "__main__":
    App().mainloop()
