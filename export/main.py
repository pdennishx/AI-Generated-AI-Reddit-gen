import os
import sys
import random
import threading
import asyncio
import re

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

    def clean_ai_text(self, text):
        text = re.sub(r"^(Hier ist|Gerne|Hier eine Story|Text für|Sicher|Folgend).*?[:\n]", "", text, flags=re.IGNORECASE | re.DOTALL)
        text = text.replace('"', '').replace('*', '').strip()
        return text.strip()

    def get_related_topics(self, topic):
        self.log(f"🔍 Suche nach ähnlichen Viral-Themen für '{topic}'...")
        prompt = f"Nenne mir 3 extrem virale, kontroverse Reddit-Themen (nur Stichpunkte), ähnlich wie: {topic}."
        try:
            response = ollama.chat(model='llama3', messages=[{'role': 'user', 'content': prompt}])
            lines = response['message']['content'].strip().split('\n')
            return [re.sub(r'^\d+\.\s*', '', l).strip("- ").strip() for l in lines if l.strip()][:3]
        except: return []

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

    def create_video(self, story_text, audio_tmp, font_size, mode):
        self.log(f"🎬 Rendering {mode}...")
        
        audio = AudioFileClip(audio_tmp).fx(vfx.speedx, PLAYBACK_SPEED)
        videos = [f for f in os.listdir(VIDEO_FOLDER) if f.endswith(('.mp4', '.mov'))]
        if not videos: return
        
        video_clip = VideoFileClip(os.path.join(VIDEO_FOLDER, random.choice(videos))).without_audio()
        start_time = random.uniform(0, max(0, video_clip.duration - audio.duration - 1))
        video_clip = video_clip.subclip(start_time, start_time + audio.duration + 0.3).set_audio(audio)

        subs = []
        words = story_text.split()
        duration_per_word = audio.duration / len(words)

        if mode == "Word-by-Word":
            for i, word in enumerate(words):
                clean_word = word.lower().strip(".,!?")
                display_word = word.upper()
                if clean_word in EMOJI_MAP: display_word += f" {EMOJI_MAP[clean_word]}"

                color = random.choice(DOPAMINE_COLORS)
                txt = TextClip(display_word, font='Impact', fontsize=font_size, color=color, stroke_color='black', stroke_width=4, method='label')
                t_start = i * duration_per_word
                txt = txt.set_start(t_start).set_duration(duration_per_word).set_position('center')
                txt = txt.fx(vfx.resize, lambda t: 0.7 + 3*t if t < 0.1 else 1.0)
                subs.append(txt)
        
        else: # Sentence-Build Mode
            sentences = re.split(r'(?<=[.!?]) +', story_text)
            current_time = 0
            for sentence in sentences:
                s_words = sentence.split()
                if not s_words: continue
                s_duration = len(s_words) * duration_per_word
                for i in range(len(s_words)):
                    build_up = " ".join(s_words[:i+1])
                    color = DOPAMINE_COLORS[i % len(DOPAMINE_COLORS)]
                    txt = TextClip(build_up.upper(), font='Impact', fontsize=font_size-15, color=color, 
                                   stroke_color='black', stroke_width=3, method='caption', size=(video_clip.w*0.85, None))
                    t_start = current_time + (i * duration_per_word)
                    txt = txt.set_start(t_start).set_duration(duration_per_word).set_position('center')
                    subs.append(txt)
                current_time += s_duration

        final_video = CompositeVideoClip([video_clip] + subs)
        if not os.path.exists(OUTPUT_FOLDER): os.makedirs(OUTPUT_FOLDER)
        out_path = os.path.join(OUTPUT_FOLDER, f"short_{random.randint(1000,9999)}.mp4")
        final_video.write_videofile(out_path, codec='libx264', fps=24, preset='ultrafast', threads=4)
        audio.close(); video_clip.close()

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Dopamine Viral Engine V6")
        self.geometry("900x850")
        
        self.frame = ctk.CTkFrame(self, fg_color="#000000", corner_radius=20, border_width=2, border_color="#00FF00")
        self.frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.85, relheight=0.95)

        ctk.CTkLabel(self.frame, text="⚡ VIRAL ENGINE V6", font=("Impact", 45), text_color="#00FF00").pack(pady=15)
        
        self.topic_input = ctk.CTkEntry(self.frame, placeholder_text="START-THEMA...", width=450, height=40)
        self.topic_input.pack(pady=5)

        # Similar Themes Checkbox
        self.related_on = ctk.BooleanVar(value=False)
        self.rel_check = ctk.CTkCheckBox(self.frame, text="Ähnliche Themen automatisch generieren", variable=self.related_on, text_color="white", fg_color="#00FF00")
        self.rel_check.pack(pady=10)

        # Mode Selection
        self.mode_var = ctk.StringVar(value="Word-by-Word")
        self.mode_switch = ctk.CTkSegmentedButton(self.frame, values=["Word-by-Word", "Sentence-Build"], variable=self.mode_var)
        self.mode_switch.pack(pady=5)

        # Sliders
        self.word_label = ctk.CTkLabel(self.frame, text="Länge: 150 Wörter", text_color="white")
        self.word_label.pack(pady=(10,0))
        self.word_slider = ctk.CTkSlider(self.frame, from_=50, to=500, command=self.update_word_label)
        self.word_slider.set(150); self.word_slider.pack(pady=5)

        self.font_label = ctk.CTkLabel(self.frame, text="Schriftgröße: 90", text_color="white")
        self.font_label.pack(pady=(10,0))
        self.font_slider = ctk.CTkSlider(self.frame, from_=40, to=150, command=self.update_font_label)
        self.font_slider.set(90); self.font_slider.pack(pady=5)

        self.btn = ctk.CTkButton(self.frame, text="START CONTENT HUSTLE 🚀", fg_color="#00FF00", text_color="black", font=("Impact", 22), height=60, command=self.start)
        self.btn.pack(pady=25)

        self.log_box = ctk.CTkTextbox(self.frame, width=650, height=180, fg_color="#111", text_color="#00FF00")
        self.log_box.pack(pady=10)
        self.gen = VideoGenerator(self.update_log)

    def update_word_label(self, val): self.word_label.configure(text=f"Länge: {int(val)} Wörter")
    def update_font_label(self, val): self.font_label.configure(text=f"Schriftgröße: {int(val)}")
    def update_log(self, msg): self.log_box.insert("end", f">> {msg}\n"); self.log_box.see("end")

    def start(self):
        self.btn.configure(state="disabled")
        threading.Thread(target=self.work, daemon=True).start()

    def work(self):
        topic = self.topic_input.get()
        if not topic: self.btn.configure(state="normal"); return
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        topics = [topic]
        if self.related_on.get():
            topics += self.gen.get_related_topics(topic)

        for t in topics:
            story = self.gen.generate_story(t, int(self.word_slider.get()))
            if story:
                audio_tmp = f"aud_{random.randint(100,999)}.mp3"
                loop.run_until_complete(self.gen.generate_audio(story, audio_tmp))
                try:
                    self.gen.create_video(story, audio_tmp, int(self.font_slider.get()), self.mode_var.get())
                except Exception as e:
                    self.update_log(f"❌ Fehler bei {t}: {e}")
                if os.path.exists(audio_tmp): os.remove(audio_tmp)
        
        loop.close()
        self.update_log("💎 CONTENT-MASCHINE FERTIG!")
        self.btn.configure(state="normal")

if __name__ == "__main__":
    app = App()
    app.mainloop()
