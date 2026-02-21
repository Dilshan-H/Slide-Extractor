"""
Lecture Slide Extractor - v3
---------------------------
Extracts slide screenshots from screen-recorded lecture videos using FFmpeg
scene-change detection followed by a perceptual-similarity deduplication pass.

Born out of one simple injustice: a lecturer who records everything but
shares nothing. You're welcome, future students.

Authors: Dilshan-H & Claude AI (Sonnet 4.6)
License: MIT (see LICENSE)

Dependencies:
    pip install customtkinter pillow reportlab imageio-ffmpeg
"""

import os
import sys
import shutil
import tempfile
import threading
import subprocess
import logging
from pathlib import Path

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger("slide_extractor")

# ── Bundled FFmpeg ──────────────────────────────────────────────────────────
try:
    import imageio_ffmpeg
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
    log.info(f"Using bundled FFmpeg: {FFMPEG_PATH}")
except Exception:
    FFMPEG_PATH = "ffmpeg"
    log.warning("imageio-ffmpeg not found — falling back to PATH ffmpeg")


# ════════════════════════════════════════════════════════════════════════════
#  APPEARANCE
# ════════════════════════════════════════════════════════════════════════════
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

THUMB_W, THUMB_H = 220, 140
GRID_COLS        = 4
PAD              = 12


# ════════════════════════════════════════════════════════════════════════════
#  PERCEPTUAL HASH  (pure Pillow, no extra deps)
# ════════════════════════════════════════════════════════════════════════════
_HASH_SIZE = 16

def _phash(img: Image.Image) -> int:
    """Difference hash — fast perceptual fingerprint."""
    small  = img.convert("L").resize((_HASH_SIZE + 1, _HASH_SIZE), Image.LANCZOS)
    pixels = list(small.getdata())
    bits   = 0
    for row in range(_HASH_SIZE):
        for col in range(_HASH_SIZE):
            idx   = row * (_HASH_SIZE + 1) + col
            bits  = (bits << 1) | (1 if pixels[idx] > pixels[idx + 1] else 0)
    return bits

def _hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")

def deduplicate(paths: list, similarity_threshold: float) -> list:
    """
    Remove frames too visually similar to the previous kept frame.
    similarity_threshold  0.0-1.0  (higher = keep more, lower = discard more aggressively)
    """
    max_dist = int((1.0 - similarity_threshold) * (_HASH_SIZE * _HASH_SIZE))
    log.info(f"Deduplication: {len(paths)} frames in | "
             f"hamming cutoff={max_dist} (similarity={similarity_threshold:.2f})")
    kept        = []
    kept_hashes = []
    for path in paths:
        try:
            h = _phash(Image.open(path))
        except Exception as exc:
            log.warning(f"Skipping unreadable frame {path}: {exc}")
            continue
        if not kept_hashes or _hamming(h, kept_hashes[-1]) > max_dist:
            kept.append(path)
            kept_hashes.append(h)
    log.info(f"Deduplication: {len(kept)} unique slides kept")
    return kept


# ════════════════════════════════════════════════════════════════════════════
#  CORE EXTRACTION
# ════════════════════════════════════════════════════════════════════════════

def extract_slides(video_path, out_dir, scene_threshold,
                   similarity_threshold, progress_cb=None, done_cb=None):
    """
    Pass 1 — FFmpeg scene-change detection.
    Pass 2 — Perceptual-hash deduplication.
    Callbacks run on a background thread; schedule UI updates with after().
    """
    def run():
        try:
            os.makedirs(out_dir, exist_ok=True)
            if progress_cb:
                progress_cb("Pass 1/2 — Running FFmpeg scene detection …")
            log.info(f"Video: {video_path} | scene_threshold={scene_threshold:.2f}")

            vf  = (f"select=eq(n\\,0)+gt(scene\\,{scene_threshold}),"
                   "setpts=N/FRAME_RATE/TB")
            cmd = [
                FFMPEG_PATH, "-i", video_path,
                "-vf", vf,
                "-vsync", "vfr",
                "-q:v", "2",
                os.path.join(out_dir, "slide_%06d.png"),
            ]
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=(subprocess.CREATE_NO_WINDOW
                               if sys.platform == "win32" else 0),
            )
            if result.returncode != 0:
                err = result.stderr.decode(errors="replace")
                log.error(f"FFmpeg failed (code {result.returncode})")
                if done_cb:
                    done_cb([], error=f"FFmpeg failed:\n{err[-2000:]}")
                return

            raw = sorted(
                Path(out_dir).glob("slide_*.png"),
                key=lambda p: p.name)   # %06d → lexicographic = numerical order
            log.info(f"FFmpeg produced {len(raw)} raw frames")

            if not raw:
                if done_cb:
                    done_cb([], error=(
                        "FFmpeg produced no frames.\n"
                        "Try lowering the scene detection threshold."))
                return

            if progress_cb:
                progress_cb(f"Pass 2/2 — Deduplicating {len(raw)} frames …")

            unique = deduplicate([str(p) for p in raw], similarity_threshold)

            if progress_cb:
                progress_cb(f"Done — {len(unique)} unique slide(s) detected.")
            if done_cb:
                done_cb(unique)

        except Exception as exc:
            log.exception("Unexpected extraction error")
            if done_cb:
                done_cb([], error=str(exc))

    threading.Thread(target=run, daemon=True).start()


def build_pdf(image_paths, pdf_path):
    if not image_paths:
        raise ValueError("No images selected.")
    log.info(f"Building PDF: {len(image_paths)} slides → {pdf_path}")
    c = canvas.Canvas(pdf_path)
    for img_path in image_paths:
        img = Image.open(img_path)
        iw, ih   = img.size
        pw, ph   = (A4[1], A4[0]) if iw >= ih else A4
        c.setPageSize((pw, ph))
        m        = 20
        scale    = min((pw - 2*m)/iw, (ph - 2*m)/ih)
        dw, dh   = iw*scale, ih*scale
        c.drawImage(img_path, (pw-dw)/2, (ph-dh)/2, dw, dh)
        c.showPage()
    c.save()
    log.info("PDF saved successfully")


def export_images(image_paths, dest_folder):
    """Copy selected slide images into dest_folder, renamed slide_001.png …"""
    if not image_paths:
        raise ValueError("No images selected.")
    os.makedirs(dest_folder, exist_ok=True)
    log.info(f"Exporting {len(image_paths)} images -> {dest_folder}")
    for i, src in enumerate(image_paths, start=1):
        ext  = Path(src).suffix or ".png"
        dest = os.path.join(dest_folder, f"slide_{i:03d}{ext}")
        shutil.copy2(src, dest)
    log.info("Image export complete")


# ════════════════════════════════════════════════════════════════════════════
#  SLIDE CARD WIDGET
# ════════════════════════════════════════════════════════════════════════════

class SlideCard(ctk.CTkFrame):
    SELECTED_BG   = "#1f538d"
    DESELECTED_BG = "#3a3a3a"
    OVERLAY_ALPHA = 160

    def __init__(self, master, img_path, index, **kwargs):
        super().__init__(master, corner_radius=8, **kwargs)
        self.img_path = img_path
        self.index    = index
        self.selected = True
        self._thumb_normal = self._load_thumb(img_path)
        self._thumb_dimmed = self._make_dimmed(self._thumb_normal)
        self._img_lbl = ctk.CTkLabel(self, image=self._thumb_normal, text="")
        self._img_lbl.pack(padx=6, pady=(6, 2))
        self._num_lbl = ctk.CTkLabel(self, text=f"#{index + 1}",
                                     font=ctk.CTkFont(size=11),
                                     text_color="#aaaaaa")
        self._num_lbl.pack(pady=(0, 6))
        self._refresh_style()
        for w in (self, self._img_lbl, self._num_lbl):
            w.bind("<Button-1>", self._toggle)

    def _load_thumb(self, path):
        img = Image.open(path).convert("RGB")
        img.thumbnail((THUMB_W, THUMB_H), Image.LANCZOS)
        padded = Image.new("RGB", (THUMB_W, THUMB_H), (30, 30, 30))
        padded.paste(img, ((THUMB_W - img.width)//2, (THUMB_H - img.height)//2))
        return ctk.CTkImage(light_image=padded, dark_image=padded,
                            size=(THUMB_W, THUMB_H))

    def _make_dimmed(self, base):
        orig    = base._light_image.copy().convert("RGBA")
        overlay = Image.new("RGBA", orig.size, (0, 0, 0, self.OVERLAY_ALPHA))
        orig.paste(overlay, mask=overlay)
        rgb = orig.convert("RGB")
        return ctk.CTkImage(light_image=rgb, dark_image=rgb,
                            size=(THUMB_W, THUMB_H))

    def _refresh_style(self):
        if self.selected:
            self.configure(fg_color=self.SELECTED_BG,
                           border_width=2, border_color="#4a9eff")
            self._img_lbl.configure(image=self._thumb_normal)
        else:
            self.configure(fg_color=self.DESELECTED_BG,
                           border_width=2, border_color="#555555")
            self._img_lbl.configure(image=self._thumb_dimmed)

    def _toggle(self, _=None):
        self.selected = not self.selected
        self._refresh_style()
        w = self.master
        while w is not None:
            if isinstance(w, ReviewWindow):
                w._on_card_toggle(); break
            w = getattr(w, "master", None)


# ════════════════════════════════════════════════════════════════════════════
#  REVIEW WINDOW
# ════════════════════════════════════════════════════════════════════════════

class ReviewWindow(ctk.CTkToplevel):

    def __init__(self, master, image_paths, video_path):
        super().__init__(master)
        self.title("Review Detected Slides")
        self.grab_set()

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w  = min(1200, int(sw * 0.85))
        h  = min(820,  int(sh * 0.85))
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        self.minsize(700, 500)

        self._image_paths = image_paths
        self._video_path  = video_path
        self._cards       = []
        self._build_ui()

    def _build_ui(self):
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=PAD, pady=(PAD, 0))

        ctk.CTkLabel(top, text="Review Extracted Slides",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        self._count_label = ctk.CTkLabel(top, text="",
                                         font=ctk.CTkFont(size=13))
        self._count_label.pack(side="left", padx=20)

        btns = ctk.CTkFrame(top, fg_color="transparent")
        btns.pack(side="right")
        ctk.CTkButton(btns, text="Select All", width=100,
                      command=self._select_all).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Deselect All", width=110,
                      fg_color="#555", hover_color="#666",
                      command=self._deselect_all).pack(side="left", padx=4)

        ctk.CTkLabel(self,
                     text="Click a slide to toggle  •  Dimmed = excluded  "
                          "•  Slides are in playback order",
                     font=ctk.CTkFont(size=11),
                     text_color="#888888").pack(padx=PAD, pady=(4, 0), anchor="w")

        self._scroll = ctk.CTkScrollableFrame(self)
        self._scroll.pack(fill="both", expand=True, padx=PAD, pady=PAD)

        for i, path in enumerate(self._image_paths):
            card = SlideCard(self._scroll, path, i)
            card.grid(row=i // GRID_COLS, column=i % GRID_COLS,
                      padx=6, pady=6, sticky="nw")
            self._cards.append(card)

        self._update_count()

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=PAD, pady=(0, PAD))
        ctk.CTkButton(bottom, text="✕  Cancel", width=100,
                      fg_color="#555", hover_color="#666",
                      command=self.destroy).pack(side="left")
        ctk.CTkButton(bottom, text="📄  Generate PDF",
                      font=ctk.CTkFont(size=14, weight="bold"),
                      width=180, height=40,
                      command=self._generate_pdf).pack(side="right")

        ctk.CTkButton(bottom, text="🖼  Save Images",
                      font=ctk.CTkFont(size=14, weight="bold"),
                      width=160, height=40,
                      fg_color="#2d6a4f", hover_color="#1b4332",
                      command=self._save_images).pack(side="right", padx=(0, 8))

    def _update_count(self):
        sel = sum(c.selected for c in self._cards)
        self._count_label.configure(
            text=f"{sel} / {len(self._cards)} slides selected")

    def _on_card_toggle(self):
        self._update_count()

    def _select_all(self):
        for c in self._cards:
            c.selected = True;  c._refresh_style()
        self._update_count()

    def _deselect_all(self):
        for c in self._cards:
            c.selected = False; c._refresh_style()
        self._update_count()

    def _generate_pdf(self):
        selected = [c.img_path for c in self._cards if c.selected]
        if not selected:
            messagebox.showwarning("Nothing selected",
                                   "Select at least one slide.", parent=self)
            return
        stem    = Path(self._video_path).stem
        pdf_path = filedialog.asksaveasfilename(
            parent=self,
            initialdir=str(Path(self._video_path).parent),
            initialfile=f"{stem}_extracted-slides.pdf",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            title="Save PDF as …",
        )
        if not pdf_path:
            return
        try:
            build_pdf(selected, pdf_path)
            messagebox.showinfo("Done!", f"PDF saved:\n{pdf_path}", parent=self)
            self.destroy()
        except Exception as exc:
            log.error(f"PDF error: {exc}")
            messagebox.showerror("Error", str(exc), parent=self)

    def _save_images(self):
        selected = [c.img_path for c in self._cards if c.selected]
        if not selected:
            messagebox.showwarning("Nothing selected",
                                   "Select at least one slide.", parent=self)
            return

        stem        = Path(self._video_path).stem
        suggest_dir = str(Path(self._video_path).parent / f"{stem}_extracted-slides")

        dest_folder = filedialog.askdirectory(
            parent=self,
            initialdir=suggest_dir,
            title="Choose (or create) a folder to save images into",
        )
        if not dest_folder:
            return
        try:
            export_images(selected, dest_folder)
            messagebox.showinfo(
                "Done!",
                f"{len(selected)} image(s) saved to:\n{dest_folder}",
                parent=self,
            )
            self.destroy()
        except Exception as exc:
            log.error(f"Image export error: {exc}")
            messagebox.showerror("Error", str(exc), parent=self)


# ════════════════════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ════════════════════════════════════════════════════════════════════════════

def resource_path(relative: str) -> str:
    """
    Resolve a bundled resource path that works both:
      - when running from source  (relative to the script)
      - when running from a PyInstaller EXE  (unpacked to sys._MEIPASS)
    """
    base = getattr(sys, "_MEIPASS", Path(__file__).parent)
    return str(Path(base) / relative)


class App(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("Lecture Slide Extractor")
        
        # Set window icon safely -- works both from source and inside the EXE
        icon = resource_path("icon.ico")
        if os.path.isfile(icon):
            try:
                self.iconbitmap(icon)
            except Exception:
                pass   # non-critical, silently skip if anything goes wrong

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w  = min(600, int(sw * 0.40))
        h  = min(580, int(sh * 0.65))
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        self.resizable(False, False)

        self._video_path        = tk.StringVar()
        self._scene_threshold   = ctk.DoubleVar(value=0.25)
        self._similarity_thresh = ctk.DoubleVar(value=0.92)
        self._tmp_dir           = None

        self._build_ui()

    def _build_ui(self):
        ctk.CTkLabel(self, text="🎓  Lecture Slide Extractor",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(20, 2))
        ctk.CTkLabel(self,
                     text="Extract slides from screen-recorded lecture videos",
                     font=ctk.CTkFont(size=12), text_color="#888888").pack(pady=(0, 14))

        # ── file picker ───────────────────────────────────────────────────────
        ff = ctk.CTkFrame(self)
        ff.pack(fill="x", padx=24, pady=(0, 10))
        ctk.CTkLabel(ff, text="Video file",
                     font=ctk.CTkFont(weight="bold")).pack(
                         anchor="w", padx=12, pady=(10, 0))

        row = ctk.CTkFrame(ff, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(4, 12))

        # Native tk.Entry for horizontal scroll support
        entry_host = ctk.CTkFrame(row, fg_color="#343638", corner_radius=6,
                                  border_width=2, border_color="#565b5e")
        entry_host.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._path_entry = tk.Entry(
            entry_host,
            textvariable=self._video_path,
            state="readonly",
            relief="flat",
            readonlybackground="#343638",
            fg="#dcddde",
            font=("Segoe UI", 11),
        )
        self._path_entry.pack(fill="both", padx=8, pady=7)
        ctk.CTkButton(row, text="Browse", width=80,
                      command=self._browse).pack(side="right")

        # ── scene threshold ───────────────────────────────────────────────────
        self._build_slider_block(
            label        = "Scene sensitivity",
            variable     = self._scene_threshold,
            from_        = 0.05, to=0.70,
            fmt_fn       = self._fmt_scene,
            tip_left     = "← catches more changes",
            tip_right    = "only big changes →",
        )

        # ── duplicate removal ─────────────────────────────────────────────────
        self._build_slider_block(
            label        = "Duplicate removal strictness",
            variable     = self._similarity_thresh,
            from_        = 0.70, to=0.99,
            fmt_fn       = self._fmt_sim,
            tip_left     = "← removes more duplicates",
            tip_right    = "keeps more frames →",
        )

        # ── status & progress ─────────────────────────────────────────────────
        self._status = ctk.CTkLabel(self, text="", text_color="#aaaaaa",
                                    font=ctk.CTkFont(size=12))
        self._status.pack(pady=(4, 2))

        self._progress_bar = ctk.CTkProgressBar(self, mode="indeterminate")
        # Not packed yet — shown only while processing

        self._process_btn = ctk.CTkButton(
            self,
            text="▶  Extract Slides",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=48,
            command=self._process,
        )
        self._process_btn.pack(pady=(6, 10), padx=24, fill="x")

        # ── footer ────────────────────────────────────────────────────────────
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=24, pady=(0, 12))
        ctk.CTkFrame(footer, height=1, fg_color="#3a3a3a").pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(
            footer,
            text="Made with 🤍 by Dilshan-H & Claude AI",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#666666",
        ).pack()
        ctk.CTkLabel(
            footer,
            text="─── Because some lecturers teach everything and share nothing ───",
            font=ctk.CTkFont(size=12),
            text_color="#4a4a4a",
        ).pack(pady=(2, 0))

    def _build_slider_block(self, label, variable, from_, to,
                            fmt_fn, tip_left, tip_right):
        frame = ctk.CTkFrame(self)
        frame.pack(fill="x", padx=24, pady=(0, 8))

        hdr = ctk.CTkFrame(frame, fg_color="transparent")
        hdr.pack(fill="x", padx=12, pady=(10, 0))
        ctk.CTkLabel(hdr, text=label,
                     font=ctk.CTkFont(weight="bold")).pack(side="left")
        val_lbl = ctk.CTkLabel(hdr, text=fmt_fn(), text_color="#4a9eff")
        val_lbl.pack(side="right")

        ctk.CTkSlider(
            frame, from_=from_, to=to, variable=variable,
            command=lambda _: val_lbl.configure(text=fmt_fn())
        ).pack(fill="x", padx=12, pady=(4, 2))

        tips = ctk.CTkFrame(frame, fg_color="transparent")
        tips.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(tips, text=tip_left,
                     font=ctk.CTkFont(size=10), text_color="#666").pack(side="left")
        ctk.CTkLabel(tips, text=tip_right,
                     font=ctk.CTkFont(size=10), text_color="#666").pack(side="right")

    # ── formatters ────────────────────────────────────────────────────────────
    def _fmt_scene(self):
        v = self._scene_threshold.get()
        if v < 0.15: return f"{v:.2f}  (very sensitive)"
        if v < 0.30: return f"{v:.2f}  (sensitive)"
        if v < 0.45: return f"{v:.2f}  (balanced)"
        return            f"{v:.2f}  (conservative)"

    def _fmt_sim(self):
        v = self._similarity_thresh.get()
        if v < 0.80: return f"{v:.2f}  (aggressive)"
        if v < 0.88: return f"{v:.2f}  (strict)"
        if v < 0.95: return f"{v:.2f}  (balanced)"
        return            f"{v:.2f}  (lenient)"

    # ── actions ───────────────────────────────────────────────────────────────
    def _browse(self):
        path = filedialog.askopenfilename(
            title="Select lecture video",
            filetypes=[
                ("Video files", "*.mp4 *.mkv *.avi *.mov *.webm *.flv *.wmv"),
                ("All files",   "*.*"),
            ]
        )
        if path:
            self._video_path.set(path)
            self._path_entry.xview_moveto(1.0)   # scroll to show filename
            self._status.configure(text="")
            log.info(f"Video selected: {path}")

    def _set_busy(self, busy: bool):
        if busy:
            self._process_btn.configure(state="disabled", text="Processing …")
            self._progress_bar.pack(before=self._process_btn,
                                    pady=(0, 4), padx=24, fill="x")
            self._progress_bar.start()
        else:
            self._progress_bar.stop()
            self._progress_bar.pack_forget()
            self._process_btn.configure(state="normal",
                                        text="▶  Extract Slides")

    def _process(self):
        path = self._video_path.get().strip()
        if not path or not os.path.isfile(path):
            messagebox.showwarning("No file",
                                   "Please select a valid video file.")
            return

        if self._tmp_dir and os.path.isdir(self._tmp_dir):
            shutil.rmtree(self._tmp_dir, ignore_errors=True)
        self._tmp_dir = tempfile.mkdtemp(prefix="slide_extractor_")

        self._set_busy(True)

        def on_progress(msg):
            self.after(0, lambda: self._status.configure(text=msg))

        def on_done(images, error=None):
            def finish():
                self._set_busy(False)
                if error:
                    self._status.configure(text="❌ Error — see terminal for details")
                    messagebox.showerror("Extraction failed", error)
                    return
                if not images:
                    self._status.configure(
                        text="No slides detected — try lowering the thresholds.")
                    return
                self._status.configure(
                    text=f"✔  {len(images)} unique slide(s) found")
                ReviewWindow(self, images, path)
            self.after(0, finish)

        extract_slides(
            video_path           = path,
            out_dir              = self._tmp_dir,
            scene_threshold      = self._scene_threshold.get(),
            similarity_threshold = self._similarity_thresh.get(),
            progress_cb          = on_progress,
            done_cb              = on_done,
        )

    def destroy(self):
        if self._tmp_dir and os.path.isdir(self._tmp_dir):
            shutil.rmtree(self._tmp_dir, ignore_errors=True)
        super().destroy()


# ════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = App()
    app.mainloop()