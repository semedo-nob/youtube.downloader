import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
import yt_dlp
import threading
import shutil
import re
import os
from datetime import datetime

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    pygame = None

# ----------------- Helpers -----------------

def get_default_download_folder():
    """Get the user's Downloads folder or fallback to home directory."""
    try:
        return Path.home() / "Downloads"
    except Exception:
        return Path.home()

def check_ffmpeg():
    """Check if FFmpeg is installed and accessible."""
    if shutil.which("ffmpeg") is None:
        messagebox.showerror(
            "FFmpeg Not Found",
            "FFmpeg is required to convert audio.\n"
            "Please install FFmpeg and add it to your system PATH.\n"
            "Visit https://ffmpeg.org/download.html for instructions."
        )
        return False
    return True

def is_valid_youtube_url(url):
    """Validate YouTube URL format."""
    youtube_regex = (
        r'(https?://)?(www\.)?(youtube\.com|youtu\.be)/'
        r'(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})'
    )
    return bool(re.match(youtube_regex, url))

# ----------------- Main App -----------------

class YouTubeMP3Downloader(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("YouTube MP3 Downloader")
        self.geometry("600x450")
        self.resizable(False, False)

        self.dark_mode = tk.BooleanVar(value=True)
        self.last_downloaded_file = None
        self.is_downloading = False

        # Initialize pygame mixer safely if available
        if PYGAME_AVAILABLE:
            try:
                pygame.mixer.init()
                self.pygame_enabled = True
            except pygame.error as e:
                messagebox.showwarning("Pygame Error", f"Audio playback unavailable: {e}")
                self.pygame_enabled = False
        else:
            messagebox.showwarning("Pygame Missing", "Pygame is not installed. Audio playback will be disabled.")
            self.pygame_enabled = False

        self.setup_ui()
        self.configure_theme()

    def setup_ui(self):
        """Set up the GUI components."""
        # Dark mode toggle
        self.dark_mode_chk = tk.Checkbutton(
            self, text="Dark Mode", variable=self.dark_mode, command=self.configure_theme
        )
        self.dark_mode_chk.pack(anchor="ne", padx=10, pady=5)

        # URL input
        tk.Label(self, text="Enter YouTube URL (e.g., https://youtube.com/watch?v=...)").pack(pady=(10, 0))
        self.url_entry = tk.Entry(self, width=60)
        self.url_entry.pack(pady=5)

        # Bitrate selector
        tk.Label(self, text="Select Bitrate (kbps):").pack()
        self.bitrate_var = tk.StringVar(value="192")
        self.bitrate_menu = ttk.Combobox(
            self, textvariable=self.bitrate_var, values=["128", "192", "320"], state="readonly", width=5
        )
        self.bitrate_menu.pack(pady=5)

        # Download folder selection
        folder_frame = tk.Frame(self)
        folder_frame.pack(pady=5)
        tk.Label(folder_frame, text="Download Folder:").pack(side=tk.LEFT)
        self.folder_var = tk.StringVar(value=str(get_default_download_folder()))
        self.folder_entry = tk.Entry(folder_frame, textvariable=self.folder_var, width=40)
        self.folder_entry.pack(side=tk.LEFT, padx=5)
        browse_btn = tk.Button(folder_frame, text="Browse", command=self.browse_folder)
        browse_btn.pack(side=tk.LEFT)

        # Download button
        self.download_btn = tk.Button(self, text="Download MP3", command=self.start_download_thread)
        self.download_btn.pack(pady=15)

        # Progress bar
        self.progress = ttk.Progressbar(self, length=500, mode="determinate")
        self.progress.pack(pady=5)

        # Status label
        self.status_label = tk.Label(self, text="Ready")
        self.status_label.pack(pady=5)

        # Player controls
        self.player_frame = tk.Frame(self)
        self.player_frame.pack(pady=10)
        self.play_btn = tk.Button(
            self.player_frame, text="Play Last Downloaded", state=tk.DISABLED, command=self.play_audio
        )
        self.play_btn.pack(side=tk.LEFT, padx=5)
        self.pause_btn = tk.Button(
            self.player_frame, text="Pause", state=tk.DISABLED, command=self.pause_audio
        )
        self.pause_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn = tk.Button(
            self.player_frame, text="Stop", state=tk.DISABLED, command=self.stop_audio
        )
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        # Volume control (only if pygame is available)
        if self.pygame_enabled:
            tk.Label(self.player_frame, text="Volume:").pack(side=tk.LEFT, padx=(10, 0))
            self.volume_var = tk.DoubleVar(value=0.5)
            self.volume_slider = tk.Scale(
                self.player_frame, from_=0, to=1, resolution=0.1, orient=tk.HORIZONTAL,
                variable=self.volume_var, command=self.set_volume, length=100
            )
            self.volume_slider.pack(side=tk.LEFT, padx=5)
        else:
            tk.Label(self.player_frame, text="Audio playback disabled (Pygame not available)").pack(side=tk.LEFT, padx=10)

    def configure_theme(self):
        """Configure dark/light theme for all widgets."""
        bg = "#1E1E1E" if self.dark_mode.get() else "#F0F0F0"
        fg = "white" if self.dark_mode.get() else "black"
        entry_bg = "#3C3F41" if self.dark_mode.get() else "white"
        button_bg = "#007ACC" if self.dark_mode.get() else "#005F99"
        slider_bg = "#3C3F41" if self.dark_mode.get() else "#D3D3D3"

        self.configure(background=bg)

        # Configure ttk styles
        style = ttk.Style()
        style.theme_use("default")
        style.configure("TCombobox", fieldbackground=entry_bg, background=entry_bg, foreground=fg)
        style.configure("TProgressbar", troughcolor=bg, background="#007ACC")

        # Update all widgets
        for widget in self.winfo_children():
            if isinstance(widget, (tk.Label, tk.Checkbutton)):
                widget.configure(background=bg, foreground=fg)
            elif isinstance(widget, tk.Entry):
                widget.configure(background=entry_bg, foreground=fg)
            elif isinstance(widget, tk.Frame):
                widget.configure(background=bg)
                for child in widget.winfo_children():
                    if isinstance(child, tk.Button):
                        child.configure(background=button_bg, foreground="white")
                    elif isinstance(child, tk.Entry):
                        child.configure(background=entry_bg, foreground=fg)
                    elif isinstance(child, tk.Label):
                        child.configure(background=bg, foreground=fg)
                    elif isinstance(child, tk.Scale) and self.pygame_enabled:
                        child.configure(background=slider_bg, foreground=fg, troughcolor=bg)
            elif isinstance(widget, tk.Button):
                widget.configure(background=button_bg, foreground="white")

        self.status_label.configure(background=bg, foreground=fg)

    def browse_folder(self):
        """Open folder selection dialog."""
        folder_selected = filedialog.askdirectory(initialdir=self.folder_var.get())
        if folder_selected:
            self.folder_var.set(folder_selected)

    def start_download_thread(self):
        """Start download in a separate thread."""
        if self.is_downloading:
            messagebox.showwarning("Warning", "A download is already in progress.")
            return

        self.is_downloading = True
        self.download_btn.config(state=tk.DISABLED)
        self.progress["value"] = 0
        self.status_label.config(text="Starting download...")
        threading.Thread(target=self.start_download, daemon=True).start()

    def start_download(self):
        """Handle the download process."""
        url = self.url_entry.get().strip()
        if not url or not is_valid_youtube_url(url):
            messagebox.showwarning("Input Error", "Please enter a valid YouTube URL.")
            self.finalize_download()
            return

        folder = Path(self.folder_var.get())
        if not folder.exists() or not folder.is_dir():
            messagebox.showwarning("Folder Error", "Please select a valid download folder.")
            self.finalize_download()
            return

        if not check_ffmpeg():
            self.finalize_download()
            return

        bitrate = self.bitrate_var.get()

        def progress_hook(d):
            if d["status"] == "downloading":
                total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate", 1)
                downloaded_bytes = d.get("downloaded_bytes", 0)
                percent = min(downloaded_bytes / total_bytes * 100, 100)
                speed = d.get("speed", 0) / 1024  # KB/s
                self.progress["value"] = percent
                self.status_label.config(text=f"Downloading: {percent:.1f}% ({speed:.1f} KB/s)")
            elif d["status"] == "finished":
                self.progress["value"] = 100
                self.status_label.config(text="Converting to MP3...")

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": str(folder / "%(title)s.%(ext)s"),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": bitrate,
            }],
            "noplaylist": True,
            "progress_hooks": [progress_hook],
            "quiet": True,
            "no_warnings": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get("title", "audio").replace("/", "_").replace("\\", "_")
                ydl.download([url])
                self.last_downloaded_file = folder / f"{title}.mp3"

            downloads_log = folder / "yt_music_log.txt"
            with open(downloads_log, "a", encoding="utf-8") as log:
                log.write(f"{datetime.now()}: {url} -> {self.last_downloaded_file}\n")

            self.status_label.config(text=f"Downloaded: {self.last_downloaded_file.name}")
            messagebox.showinfo("Success", f"Downloaded to {self.last_downloaded_file}")
            if self.pygame_enabled:
                self.play_btn.config(state=tk.NORMAL)
                self.pause_btn.config(state=tk.NORMAL)
                self.stop_btn.config(state=tk.NORMAL)

        except yt_dlp.utils.DownloadError as e:
            messagebox.showerror("Download Error", f"Failed to download: {str(e)}")
            self.status_label.config(text="Download failed.")
        except Exception as e:
            messagebox.showerror("Error", f"An unexpected error occurred: {str(e)}")
            self.status_label.config(text="Download failed.")

        self.finalize_download()

    def finalize_download(self):
        """Reset UI after download."""
        self.is_downloading = False
        self.download_btn.config(state=tk.NORMAL)

    def play_audio(self):
        """Play the last downloaded audio file."""
        if not self.pygame_enabled:
            messagebox.showwarning("Playback Unavailable", "Audio playback is disabled (Pygame not available).")
            return
        if not self.last_downloaded_file or not self.last_downloaded_file.exists():
            messagebox.showwarning("No File", "No downloaded audio file to play.")
            return

        try:
            pygame.mixer.music.load(str(self.last_downloaded_file))
            pygame.mixer.music.set_volume(self.volume_var.get())
            pygame.mixer.music.play()
            self.status_label.config(text=f"Playing: {self.last_downloaded_file.name}")
            self.pause_btn.config(state=tk.NORMAL)
        except pygame.error as e:
            messagebox.showerror("Playback Error", f"Cannot play audio: {e}")

    def pause_audio(self):
        """Pause or unpause the current audio."""
        if not self.pygame_enabled:
            messagebox.showwarning("Playback Unavailable", "Audio playback is disabled (Pygame not available).")
            return
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.pause()
            self.status_label.config(text="Paused")
            self.pause_btn.config(text="Resume")
        else:
            pygame.mixer.music.unpause()
            self.status_label.config(text=f"Playing: {self.last_downloaded_file.name}")
            self.pause_btn.config(text="Pause")

    def stop_audio(self):
        """Stop audio playback."""
        if not self.pygame_enabled:
            messagebox.showwarning("Playback Unavailable", "Audio playback is disabled (Pygame not available).")
            return
        pygame.mixer.music.stop()
        self.status_label.config(text="Playback stopped.")
        self.pause_btn.config(text="Pause")

    def set_volume(self, val):
        """Set the audio volume."""
        if not self.pygame_enabled:
            return
        try:
            pygame.mixer.music.set_volume(self.volume_var.get())
        except pygame.error:
            pass

# ----------- Run App --------------

if __name__ == "__main__":
    app = YouTubeMP3Downloader()
    app.mainloop()