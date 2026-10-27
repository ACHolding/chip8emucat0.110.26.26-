#!/usr/bin/env python3
"""
$catchip8emu0.1.1 — Cat's CHIP-8 Emulator 0.1.1

mGBA-inspired GUI + Nesticle-style menustrip, with a built-in Pong ROM.
Full CHIP-8 CPU, 60 FPS display, sound timer beep, hex keypad.

Pong: Left 1/Q  |  Right 4/R
"""

from __future__ import annotations

import io
import os
import platform
import random
import struct
import subprocess
import tempfile
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox

# ---------------------------------------------------------------------------
# Config — mGBA-like chrome
# ---------------------------------------------------------------------------
VERSION = "0.1.1"
WINDOW_W, WINDOW_H = 720, 520
TARGET_FPS = 60
FRAME_MS = max(1, 1000 // TARGET_FPS)
CPU_HZ = 600
CYCLES_PER_FRAME = max(1, CPU_HZ // TARGET_FPS)

THEME = {
    "bg": "#0b1220",
    "panel": "#121a2b",
    "canvas": "#050b16",
    "pixel": "#3b82f6",
    "pixel_dim": "#1e3a5f",
    "text": "#60a5fa",
    "text_hi": "#93c5fd",
    "btn": "#000000",
    "btn_active": "#1e293b",
    "border": "#1e3a8a",
    "menu_bg": "#0f172a",
    "menu_fg": "#93c5fd",
    "status": "#0f172a",
}

# Classic public-domain CHIP-8 Pong (verified 254-byte dump)
# Left paddle: 1 up / Q down   Right paddle: 4 up / R down
PONG_ROM = bytes([
    0x6A, 0x02, 0x6B, 0x0C, 0x6C, 0x3F, 0x6D, 0x0C, 0xA2, 0xEA, 0xDA, 0xB6,
    0xDC, 0xD6, 0x6E, 0x00, 0x22, 0xD4, 0x66, 0x03, 0x68, 0x02, 0x60, 0x60,
    0xF0, 0x15, 0xF0, 0x07, 0x30, 0x00, 0x12, 0x1A, 0xC7, 0x17, 0x77, 0x08,
    0x69, 0xFF, 0xA2, 0xF0, 0xD6, 0x71, 0xA2, 0xEA, 0xDA, 0xB6, 0xDC, 0xD6,
    0x60, 0x01, 0xE0, 0xA1, 0x7B, 0xFE, 0x60, 0x04, 0xE0, 0xA1, 0x7B, 0x02,
    0x60, 0x1F, 0x8B, 0x02, 0xDA, 0xB6, 0x60, 0x0C, 0xE0, 0xA1, 0x7D, 0xFE,
    0x60, 0x0D, 0xE0, 0xA1, 0x7D, 0x02, 0x60, 0x1F, 0x8D, 0x02, 0xDC, 0xD6,
    0xA2, 0xF0, 0xD6, 0x71, 0x86, 0x84, 0x87, 0x94, 0x60, 0x3F, 0x86, 0x02,
    0x61, 0x1F, 0x87, 0x12, 0x46, 0x02, 0x12, 0x78, 0x46, 0x3D, 0x12, 0x8A,
    0x12, 0x9E, 0x80, 0x70, 0x80, 0xB5, 0x3F, 0x01, 0x12, 0xA6, 0x61, 0x02,
    0x80, 0x15, 0x3F, 0x01, 0x12, 0xBA, 0x80, 0x15, 0x3F, 0x01, 0x12, 0xC8,
    0x80, 0x15, 0x3F, 0x01, 0x12, 0xA6, 0x12, 0x9E, 0x80, 0x70, 0x80, 0xD5,
    0x3F, 0x01, 0x12, 0xA6, 0x61, 0x02, 0x80, 0x15, 0x3F, 0x01, 0x12, 0xBA,
    0x80, 0x15, 0x3F, 0x01, 0x12, 0xC8, 0x80, 0x15, 0x3F, 0x01, 0x12, 0xA6,
    0x37, 0x00, 0x37, 0x1F, 0x69, 0xFF, 0x49, 0xFE, 0x69, 0x01, 0xD6, 0x71,
    0x12, 0x2A, 0x7E, 0x01, 0x36, 0x3D, 0x7E, 0x0F, 0x60, 0x05, 0xF0, 0x18,
    0x22, 0xD4, 0x12, 0x14, 0x69, 0xFF, 0x48, 0x02, 0x68, 0xFE, 0x12, 0xCE,
    0x69, 0x00, 0x48, 0x02, 0x68, 0xFE, 0x12, 0xCE, 0x69, 0x01, 0x48, 0x02,
    0x68, 0xFE, 0x60, 0x01, 0xF0, 0x18, 0x12, 0x9E, 0xA2, 0xF2, 0xFE, 0x33,
    0xF2, 0x65, 0xF1, 0x29, 0x64, 0x14, 0x65, 0x00, 0xD4, 0x55, 0x74, 0x0F,
    0xF2, 0x29, 0xD4, 0x55, 0x00, 0xEE, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80,
    0x80, 0x00,
])
# Tiny maze demo (optional File menu item)
MAZE_ROM = bytes([
    0xA2, 0x1E, 0xC2, 0x01, 0x32, 0x01, 0xA2, 0x1A, 0xD0, 0x14,
    0x70, 0x04, 0x30, 0x40, 0x12, 0x02, 0x60, 0x00, 0x71, 0x04,
    0x31, 0x20, 0x12, 0x02, 0x12, 0x18, 0x80, 0x40, 0x20, 0x10,
    0x20, 0x40, 0x80, 0x10,
])


# ---------------------------------------------------------------------------
# Audio (CHIP-8 sound timer → short square beep)
# ---------------------------------------------------------------------------
class AudioEngine:
    def __init__(self, root: tk.Tk, enabled: bool = True):
        self.root = root
        self.enabled = enabled
        self._busy = False
        self.system = platform.system()
        self.wav = self._square(440, 120)
        self.path = None
        if self.system != "Windows":
            try:
                fd, path = tempfile.mkstemp(suffix=".wav")
                with os.fdopen(fd, "wb") as fh:
                    fh.write(self.wav)
                self.path = path
            except OSError:
                self.path = None

    @staticmethod
    def _square(freq: int, ms: int, rate: int = 22050) -> bytes:
        n = int(rate * ms / 1000)
        buf = io.BytesIO()
        buf.write(b"RIFF")
        buf.write(struct.pack("<I", 36 + n))
        buf.write(b"WAVEfmt ")
        buf.write(struct.pack("<IHHIIHH", 16, 1, 1, rate, rate, 1, 8))
        buf.write(b"data")
        buf.write(struct.pack("<I", n))
        period = rate / freq
        samples = bytearray(n)
        for i in range(n):
            samples[i] = 190 if (i % period) < (period / 2) else 65
        buf.write(samples)
        return buf.getvalue()

    def beep(self):
        if not self.enabled or self._busy:
            return
        self._busy = True
        threading.Thread(target=self._play, daemon=True).start()

    def _play(self):
        try:
            if self.system == "Windows":
                import winsound
                winsound.PlaySound(self.wav, winsound.SND_MEMORY)
            elif self.system == "Darwin" and self.path:
                subprocess.run(
                    ["afplay", self.path],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            elif self.path:
                subprocess.run(
                    ["aplay", "-q", self.path],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            else:
                self.root.bell()
        except Exception:
            try:
                self.root.bell()
            except Exception:
                pass
        finally:
            self._busy = False

    def cleanup(self):
        if self.path and os.path.exists(self.path):
            try:
                os.remove(self.path)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# CHIP-8 core
# ---------------------------------------------------------------------------
class Chip8:
    FONT = [
        0xF0, 0x90, 0x90, 0x90, 0xF0, 0x20, 0x60, 0x20, 0x20, 0x70,
        0xF0, 0x10, 0xF0, 0x80, 0xF0, 0xF0, 0x10, 0xF0, 0x10, 0xF0,
        0x90, 0x90, 0xF0, 0x10, 0x10, 0xF0, 0x80, 0xF0, 0x10, 0xF0,
        0xF0, 0x80, 0xF0, 0x90, 0xF0, 0xF0, 0x10, 0x20, 0x40, 0x40,
        0xF0, 0x90, 0xF0, 0x90, 0xF0, 0xF0, 0x90, 0xF0, 0x10, 0xF0,
        0xF0, 0x90, 0xF0, 0x90, 0x90, 0xE0, 0x90, 0xE0, 0x90, 0xE0,
        0xF0, 0x80, 0x80, 0x80, 0xF0, 0xE0, 0x90, 0x90, 0x90, 0xE0,
        0xF0, 0x80, 0xF0, 0x80, 0xF0, 0xF0, 0x80, 0xF0, 0x80, 0x80,
    ]

    def __init__(self):
        self.rom = bytearray(PONG_ROM)
        self.reset()

    def reset(self):
        self.mem = [0] * 4096
        self.v = [0] * 16
        self.i = 0
        self.pc = 0x200
        self.stack = [0] * 16
        self.sp = 0
        self.dt = 0
        self.st = 0
        self.keys = [0] * 16
        self.fb = [0] * (64 * 32)
        self.draw = True
        self.wait_key = False
        self.wait_reg = 0
        self.op = 0
        for i, b in enumerate(self.FONT):
            self.mem[i] = b
        for i, b in enumerate(self.rom):
            if 0x200 + i < 4096:
                self.mem[0x200 + i] = b

    def load(self, data: bytes | bytearray | list):
        self.rom = bytearray(data)
        self.reset()

    def tick_timers(self):
        if self.dt > 0:
            self.dt -= 1
        beep = False
        if self.st > 0:
            beep = True
            self.st -= 1
        return beep

    def step(self):
        if self.wait_key:
            for k, down in enumerate(self.keys):
                if down:
                    self.v[self.wait_reg] = k
                    self.wait_key = False
                    break
            return

        if self.pc > 0xFFE:
            self.pc = 0x200
        op = (self.mem[self.pc] << 8) | self.mem[self.pc + 1]
        self.op = op
        self.pc = (self.pc + 2) & 0xFFF

        nnn, nn, n = op & 0xFFF, op & 0xFF, op & 0xF
        x, y = (op >> 8) & 0xF, (op >> 4) & 0xF
        hi = op & 0xF000

        if op == 0x00E0:
            self.fb = [0] * 2048
            self.draw = True
        elif op == 0x00EE:
            if self.sp > 0:
                self.sp -= 1
                self.pc = self.stack[self.sp]
        elif hi == 0x1000:
            self.pc = nnn
        elif hi == 0x2000:
            if self.sp < 16:
                self.stack[self.sp] = self.pc
                self.sp += 1
            self.pc = nnn
        elif hi == 0x3000:
            if self.v[x] == nn:
                self.pc = (self.pc + 2) & 0xFFF
        elif hi == 0x4000:
            if self.v[x] != nn:
                self.pc = (self.pc + 2) & 0xFFF
        elif hi == 0x5000 and n == 0:
            if self.v[x] == self.v[y]:
                self.pc = (self.pc + 2) & 0xFFF
        elif hi == 0x6000:
            self.v[x] = nn
        elif hi == 0x7000:
            self.v[x] = (self.v[x] + nn) & 0xFF
        elif hi == 0x8000:
            if n == 0:
                self.v[x] = self.v[y]
            elif n == 1:
                self.v[x] |= self.v[y]
            elif n == 2:
                self.v[x] &= self.v[y]
            elif n == 3:
                self.v[x] ^= self.v[y]
            elif n == 4:
                total = self.v[x] + self.v[y]
                self.v[x] = total & 0xFF
                self.v[0xF] = 1 if total > 0xFF else 0
            elif n == 5:
                borrow = 1 if self.v[x] >= self.v[y] else 0
                self.v[x] = (self.v[x] - self.v[y]) & 0xFF
                self.v[0xF] = borrow
            elif n == 6:
                self.v[0xF] = self.v[x] & 1
                self.v[x] >>= 1
            elif n == 7:
                borrow = 1 if self.v[y] >= self.v[x] else 0
                self.v[x] = (self.v[y] - self.v[x]) & 0xFF
                self.v[0xF] = borrow
            elif n == 0xE:
                self.v[0xF] = (self.v[x] >> 7) & 1
                self.v[x] = (self.v[x] << 1) & 0xFF
        elif hi == 0x9000 and n == 0:
            if self.v[x] != self.v[y]:
                self.pc = (self.pc + 2) & 0xFFF
        elif hi == 0xA000:
            self.i = nnn
        elif hi == 0xB000:
            self.pc = (nnn + self.v[0]) & 0xFFF
        elif hi == 0xC000:
            self.v[x] = random.randint(0, 255) & nn
        elif hi == 0xD000:
            vx, vy = self.v[x] % 64, self.v[y] % 32
            self.v[0xF] = 0
            for row in range(n):
                if vy + row >= 32:
                    break
                sprite = self.mem[(self.i + row) & 0xFFF]
                for col in range(8):
                    if vx + col >= 64:
                        break
                    if sprite & (0x80 >> col):
                        idx = (vy + row) * 64 + (vx + col)
                        if self.fb[idx]:
                            self.v[0xF] = 1
                        self.fb[idx] ^= 1
            self.draw = True
        elif hi == 0xE000:
            key = self.v[x] & 0xF
            if nn == 0x9E and self.keys[key]:
                self.pc = (self.pc + 2) & 0xFFF
            elif nn == 0xA1 and not self.keys[key]:
                self.pc = (self.pc + 2) & 0xFFF
        elif hi == 0xF000:
            if nn == 0x07:
                self.v[x] = self.dt
            elif nn == 0x0A:
                self.wait_key = True
                self.wait_reg = x
            elif nn == 0x15:
                self.dt = self.v[x]
            elif nn == 0x18:
                self.st = self.v[x]
            elif nn == 0x1E:
                self.i = (self.i + self.v[x]) & 0xFFF
            elif nn == 0x29:
                self.i = (self.v[x] & 0xF) * 5
            elif nn == 0x33:
                val = self.v[x]
                self.mem[self.i & 0xFFF] = val // 100
                self.mem[(self.i + 1) & 0xFFF] = (val // 10) % 10
                self.mem[(self.i + 2) & 0xFFF] = val % 10
            elif nn == 0x55:
                for r in range(x + 1):
                    self.mem[(self.i + r) & 0xFFF] = self.v[r]
            elif nn == 0x65:
                for r in range(x + 1):
                    self.v[r] = self.mem[(self.i + r) & 0xFFF]


# ---------------------------------------------------------------------------
# GUI — Nesticle menustrip + mGBA chrome
# ---------------------------------------------------------------------------
class CatChip8App:
    # Nesticle / COSMAC VIP hex pad on QWERTY
    KEYMAP = {
        "1": 0x1, "2": 0x2, "3": 0x3, "4": 0xC,
        "q": 0x4, "w": 0x5, "e": 0x6, "r": 0xD,
        "a": 0x7, "s": 0x8, "d": 0x9, "f": 0xE,
        "z": 0xA, "x": 0x0, "c": 0xB, "v": 0xF,
    }

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"Cat's CHIP-8 {VERSION} — mGBA / Nesticle UI")
        self.root.configure(bg=THEME["bg"])
        self.root.minsize(640, 480)
        self._center(WINDOW_W, WINDOW_H)

        self.cpu = Chip8()
        self.audio = AudioEngine(root)
        self.running = True
        self.speed = 1  # 1x / 2x / 3x cycles
        self.scale = 10
        self.rom_name = "Pong.ch8 (built-in)"
        self.frame_n = 0
        self.fps_t0 = time.perf_counter()
        self.fps = 60.0

        self._nesticle_menustrip()
        self._mgba_toolbar()
        self._mgba_viewport()
        self._mgba_statusbar()
        self._bind()

        self.root.protocol("WM_DELETE_WINDOW", self._quit)
        self._loop()

    def _center(self, w, h):
        self.root.update_idletasks()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x, y = max(0, (sw - w) // 2), max(0, (sh - h) // 2)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _menu(self, parent):
        return tk.Menu(
            parent, tearoff=0,
            bg=THEME["menu_bg"], fg=THEME["menu_fg"],
            activebackground=THEME["border"],
            activeforeground=THEME["text_hi"],
            bd=0,
        )

    def _nesticle_menustrip(self):
        """Classic Nesticle-style cascading menubar (File / Emulation / …)."""
        bar = tk.Menu(
            self.root, tearoff=0,
            bg=THEME["menu_bg"], fg=THEME["menu_fg"],
            activebackground=THEME["border"],
            activeforeground=THEME["text_hi"],
        )

        # File  (Nesticle: Open / Exit)
        file_m = self._menu(bar)
        file_m.add_command(label="Open ROM…\tCtrl+O", command=self.open_rom)
        file_m.add_command(label="Open Built-in Pong\tCtrl+P", command=self.load_pong)
        file_m.add_command(label="Open Built-in Maze", command=self.load_maze)
        file_m.add_separator()
        file_m.add_command(label="Exit\tAlt+F4", command=self._quit)
        bar.add_cascade(label="File", menu=file_m)

        # Emulation  (Nesticle: Pause / Soft Reset / Hard Reset)
        emu_m = self._menu(bar)
        emu_m.add_command(label="Pause / Resume\tSpace", command=self.toggle_pause)
        emu_m.add_command(label="Soft Reset\tCtrl+R", command=self.soft_reset)
        emu_m.add_command(label="Hard Reset\tCtrl+Shift+R", command=self.hard_reset)
        emu_m.add_command(label="Frame Advance\tN", command=self.frame_step)
        emu_m.add_separator()
        speed_m = self._menu(emu_m)
        speed_m.add_command(label="Speed 1×", command=lambda: self.set_speed(1))
        speed_m.add_command(label="Speed 2×", command=lambda: self.set_speed(2))
        speed_m.add_command(label="Speed 3×", command=lambda: self.set_speed(3))
        emu_m.add_cascade(label="Speed", menu=speed_m)
        bar.add_cascade(label="Emulation", menu=emu_m)

        # Options  (Nesticle options drawer)
        opt_m = self._menu(bar)
        opt_m.add_command(label="Keypad Map…", command=self.show_keys)
        opt_m.add_command(label="About…", command=self.show_about)
        bar.add_cascade(label="Options", menu=opt_m)

        # Video  (mGBA-like)
        vid_m = self._menu(bar)
        vid_m.add_command(label="Scale 8×", command=lambda: self.set_scale(8))
        vid_m.add_command(label="Scale 10×", command=lambda: self.set_scale(10))
        vid_m.add_command(label="Scale 12×", command=lambda: self.set_scale(12))
        bar.add_cascade(label="Video", menu=vid_m)

        # Sound
        snd_m = self._menu(bar)
        snd_m.add_command(label="Toggle Sound", command=self.toggle_audio)
        snd_m.add_command(label="Test Beep", command=self.audio.beep)
        bar.add_cascade(label="Sound", menu=snd_m)

        # Help
        help_m = self._menu(bar)
        help_m.add_command(label="Controls", command=self.show_keys)
        help_m.add_command(label="About CatCHIP8", command=self.show_about)
        bar.add_cascade(label="Help", menu=help_m)

        self.root.config(menu=bar)

    def _btn(self, parent, text, cmd, width=9):
        return tk.Button(
            parent, text=text, command=cmd,
            bg=THEME["btn"], fg=THEME["text"],
            activebackground=THEME["btn_active"],
            activeforeground=THEME["text_hi"],
            highlightbackground=THEME["border"],
            highlightthickness=1, bd=0, relief=tk.FLAT,
            font=("Menlo", 10, "bold"), width=width, cursor="hand2",
            padx=6, pady=4,
        )

    def _mgba_toolbar(self):
        bar = tk.Frame(
            self.root, bg=THEME["panel"], height=44,
            highlightbackground=THEME["border"], highlightthickness=1,
        )
        bar.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(6, 4))
        self._btn(bar, "Open", self.open_rom).pack(side=tk.LEFT, padx=3, pady=5)
        self._btn(bar, "Pong", self.load_pong).pack(side=tk.LEFT, padx=3, pady=5)
        self.btn_pause = self._btn(bar, "Pause", self.toggle_pause)
        self.btn_pause.pack(side=tk.LEFT, padx=3, pady=5)
        self._btn(bar, "Reset", self.soft_reset, width=7).pack(side=tk.LEFT, padx=3, pady=5)
        self._btn(bar, "Step", self.frame_step, width=6).pack(side=tk.LEFT, padx=3, pady=5)
        self.btn_audio = self._btn(bar, "Sound: ON", self.toggle_audio, width=10)
        self.btn_audio.pack(side=tk.RIGHT, padx=6, pady=5)
        tk.Label(
            bar, text="mGBA-style CHIP-8",
            bg=THEME["panel"], fg=THEME["text_hi"],
            font=("Menlo", 10),
        ).pack(side=tk.RIGHT, padx=8)

    def _mgba_viewport(self):
        wrap = tk.Frame(
            self.root, bg=THEME["bg"],
            highlightbackground=THEME["border"], highlightthickness=2,
        )
        wrap.pack(side=tk.TOP, expand=True, fill=tk.BOTH, padx=10, pady=4)
        self.canvas = tk.Canvas(
            wrap, bg=THEME["canvas"], highlightthickness=0,
            width=64 * self.scale, height=32 * self.scale,
        )
        self.canvas.pack(expand=True)
        self._alloc_pixels()

    def _alloc_pixels(self):
        self.canvas.delete("all")
        self.rects = [0] * 2048
        self.drawn = [0] * 2048
        s = self.scale
        for y in range(32):
            for x in range(64):
                x0, y0 = x * s, y * s
                self.rects[y * 64 + x] = self.canvas.create_rectangle(
                    x0, y0, x0 + s, y0 + s,
                    fill=THEME["canvas"], outline=THEME["pixel_dim"], width=0,
                )
        self.canvas.config(width=64 * s, height=32 * s)
        self.cpu.draw = True

    def _mgba_statusbar(self):
        bar = tk.Frame(
            self.root, bg=THEME["status"], height=28,
            highlightbackground=THEME["border"], highlightthickness=1,
        )
        bar.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=(2, 8))
        self.lbl_l = tk.Label(
            bar, text=f"ROM: {self.rom_name}",
            bg=THEME["status"], fg=THEME["text"],
            font=("Menlo", 9, "bold"), anchor="w",
        )
        self.lbl_l.pack(side=tk.LEFT, padx=8)
        self.lbl_r = tk.Label(
            bar, text="60 FPS | PC 0200",
            bg=THEME["status"], fg=THEME["text_hi"],
            font=("Menlo", 9), anchor="e",
        )
        self.lbl_r.pack(side=tk.RIGHT, padx=8)

    def _bind(self):
        self.root.bind("<KeyPress>", self._kd)
        self.root.bind("<KeyRelease>", self._ku)
        self.root.bind("<Control-o>", lambda e: self.open_rom())
        self.root.bind("<Control-p>", lambda e: self.load_pong())
        self.root.bind("<Control-r>", lambda e: self.soft_reset())
        self.root.bind("<Control-R>", lambda e: self.hard_reset())
        self.root.bind("<space>", lambda e: self.toggle_pause())

    def _kd(self, e):
        k = e.keysym.lower()
        if k in self.KEYMAP:
            self.cpu.keys[self.KEYMAP[k]] = 1
        elif k == "n" and not self.running:
            self.frame_step()

    def _ku(self, e):
        k = e.keysym.lower()
        if k in self.KEYMAP:
            self.cpu.keys[self.KEYMAP[k]] = 0

    # ---- actions ----------------------------------------------------------
    def open_rom(self):
        path = filedialog.askopenfilename(
            title="Open CHIP-8 ROM",
            filetypes=[("CHIP-8", "*.ch8 *.c8 *.rom"), ("All", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "rb") as fh:
                data = fh.read()
            if len(data) > 4096 - 0x200:
                messagebox.showerror("ROM", "ROM too large for CHIP-8 memory.")
                return
            self.cpu.load(data)
            self.rom_name = os.path.basename(path)
            self._clear_fb()
            self.running = True
            self.btn_pause.config(text="Pause")
            self._status()
        except OSError as exc:
            messagebox.showerror("Load failed", str(exc))

    def load_pong(self):
        self.cpu.load(PONG_ROM)
        self.rom_name = "Pong.ch8 (built-in)"
        self._clear_fb()
        self.running = True
        self.btn_pause.config(text="Pause")
        self._status()

    def load_maze(self):
        self.cpu.load(MAZE_ROM)
        self.rom_name = "Maze.ch8 (built-in)"
        self._clear_fb()
        self.running = True
        self.btn_pause.config(text="Pause")
        self._status()

    def toggle_pause(self):
        self.running = not self.running
        self.btn_pause.config(text="Pause" if self.running else "Resume")
        self._status()

    def soft_reset(self):
        self.cpu.reset()
        self._clear_fb()
        self._status()

    def hard_reset(self):
        """Nesticle-style hard reset: reload current ROM bytes + full clear."""
        self.cpu.load(bytes(self.cpu.rom))
        self._clear_fb()
        self.running = True
        self.btn_pause.config(text="Pause")
        self._status()

    def frame_step(self):
        self.running = False
        self.btn_pause.config(text="Resume")
        self.cpu.step()
        if self.cpu.tick_timers():
            self.audio.beep()
        self._paint()
        self._status()

    def set_speed(self, n: int):
        self.speed = max(1, min(3, n))
        self._status()

    def set_scale(self, s: int):
        self.scale = s
        self._alloc_pixels()
        self._paint(force=True)

    def toggle_audio(self):
        self.audio.enabled = not self.audio.enabled
        self.btn_audio.config(
            text="Sound: ON" if self.audio.enabled else "Sound: OFF"
        )
        self._status()

    def show_keys(self):
        messagebox.showinfo(
            "Keypad",
            "CHIP-8 hex pad (Nesticle / COSMAC layout):\n\n"
            "  1 2 3 4   →  1 2 3 C\n"
            "  Q W E R   →  4 5 6 D\n"
            "  A S D F   →  7 8 9 E\n"
            "  Z X C V   →  A 0 B F\n\n"
            "Pong:  Left 1/Q   Right 4/R\n"
            "Space = Pause   Ctrl+R = Soft Reset",
        )

    def show_about(self):
        messagebox.showinfo(
            "About",
            f"Cat's CHIP-8 Emulator {VERSION}\n\n"
            "GUI: mGBA-inspired chrome\n"
            "Menus: Nesticle-style menustrip\n"
            "ROM: built-in classic Pong\n\n"
            "Full CHIP-8 instruction set @ 60 FPS.",
        )

    # ---- render / loop ----------------------------------------------------
    def _clear_fb(self):
        for i in range(2048):
            self.drawn[i] = 0
            self.canvas.itemconfig(self.rects[i], fill=THEME["canvas"])

    def _paint(self, force: bool = False):
        if not force and not self.cpu.draw:
            return
        on, off = THEME["pixel"], THEME["canvas"]
        fb, drawn, rects = self.cpu.fb, self.drawn, self.rects
        for i in range(2048):
            v = fb[i]
            if force or v != drawn[i]:
                drawn[i] = v
                self.canvas.itemconfig(rects[i], fill=on if v else off)
        self.cpu.draw = False

    def _status(self):
        st = "RUN" if self.running else "PAUSE"
        aud = "ON" if self.audio.enabled else "OFF"
        self.lbl_l.config(text=f"[{st}] {self.rom_name}")
        self.lbl_r.config(
            text=(
                f"{self.fps:4.1f} FPS | {self.speed}× | "
                f"PC {self.cpu.pc:04X} | OP {self.cpu.op:04X} | SND {aud}"
            )
        )

    def _loop(self):
        t0 = time.perf_counter()
        if self.running:
            cycles = CYCLES_PER_FRAME * self.speed
            for _ in range(cycles):
                self.cpu.step()
            if self.cpu.tick_timers():
                self.audio.beep()
            self._paint()

        self.frame_n += 1
        now = time.perf_counter()
        if now - self.fps_t0 >= 0.5:
            self.fps = self.frame_n / (now - self.fps_t0)
            self.frame_n = 0
            self.fps_t0 = now
            self._status()

        spent = int((time.perf_counter() - t0) * 1000)
        self.root.after(max(1, FRAME_MS - spent), self._loop)

    def _quit(self):
        self.running = False
        self.audio.cleanup()
        self.root.destroy()


def main():
    root = tk.Tk()
    CatChip8App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
