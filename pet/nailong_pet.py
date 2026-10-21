# -*- coding: utf-8 -*-
"""
奶龙桌宠 v4 —— 贴图版 + 分裂玩法（素材来自 奶龙大笑.mp4）
-------------------------------------------------------------------
· Win32 分层窗口：真·逐像素透明，永久置顶，不占任务栏
· 左键按住拖动；轻点一下 = 捧腹大笑（约 2.6 秒，只笑一次）
· 笑的过程中再点不会打断：让它把这 2.6 秒笑完（点击照样计入"长大"次数）
· 连续点击会一点点变大；点满 5 次后大奶龙「生」出一只原始大小的新奶龙
· 新奶龙各有各的笑：落地后自己从头笑一遍，和本体的笑有先有后、先后收场
· 大奶龙生完缩回原始大小、计数归零 —— 可以一直点它接着生
· 留下来的新奶龙同样可以点击、拖动、长大，也能继续生
· 右键菜单：笑一个 / 整体大小 / 自动笑 / 笑声开关 / 退出
依赖：sprite.dat + sprite.json（build_sprites.py 生成）、laugh.wav
"""
import ctypes
import json
import math
import os
import random
import sys
import threading
import time
import zlib
import winsound
from collections import OrderedDict
from ctypes import wintypes

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32
_winmm = ctypes.windll.winmm

# 字幕要画文字，这些 GDI 函数必须显式声明参数类型：
# 不声明的话 64 位下 HDC/HFONT 会被当成 32 位 int 截断，直接崩。
gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
gdi32.CreateCompatibleDC.argtypes = (ctypes.c_void_p,)
gdi32.SelectObject.restype = ctypes.c_void_p
gdi32.SelectObject.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
gdi32.DeleteObject.argtypes = (ctypes.c_void_p,)
gdi32.DeleteDC.argtypes = (ctypes.c_void_p,)
gdi32.CreateDIBSection.restype = ctypes.c_void_p
gdi32.CreateDIBSection.argtypes = (
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p,
    ctypes.c_void_p, ctypes.c_uint)
gdi32.CreateFontW.restype = ctypes.c_void_p
gdi32.CreateFontW.argtypes = (
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint,
    ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint,
    ctypes.c_wchar_p)
gdi32.CreateSolidBrush.restype = ctypes.c_void_p
gdi32.CreateSolidBrush.argtypes = (ctypes.c_uint,)
gdi32.CreatePen.restype = ctypes.c_void_p
gdi32.CreatePen.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.c_uint)
gdi32.SetBkMode.argtypes = (ctypes.c_void_p, ctypes.c_int)
gdi32.SetTextColor.argtypes = (ctypes.c_void_p, ctypes.c_uint)
gdi32.RoundRect.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                            ctypes.c_int, ctypes.c_int, ctypes.c_int,
                            ctypes.c_int)
gdi32.TextOutW.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                           ctypes.c_wchar_p, ctypes.c_int)
gdi32.GetTextExtentPoint32W.argtypes = (
    ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int, ctypes.c_void_p)
user32.ReleaseDC.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
# 这些返回句柄的函数若不声明 restype，64 位下句柄会被截断成 32 位 ——
# 截断后的非法指针传回系统就是 access violation（进程静默崩溃，无任何日志）。
# 打包成 exe 后模块基址变高，必踩。全部显式声明。
kernel32.GetModuleHandleW.restype = ctypes.c_void_p
kernel32.GetModuleHandleW.argtypes = (ctypes.c_wchar_p,)
user32.LoadCursorW.restype = ctypes.c_void_p
user32.LoadCursorW.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
user32.MonitorFromWindow.restype = ctypes.c_void_p
user32.MonitorFromWindow.argtypes = (wintypes.HWND, ctypes.c_uint)
user32.GetMonitorInfoW.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
user32.UpdateLayeredWindow.restype = ctypes.c_bool
user32.UpdateLayeredWindow.argtypes = (
    wintypes.HWND, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p,
    ctypes.c_uint32)
user32.SetTimer.restype = ctypes.c_void_p
user32.SetTimer.argtypes = (wintypes.HWND, ctypes.c_void_p, ctypes.c_uint,
                            ctypes.c_void_p)
user32.KillTimer.argtypes = (wintypes.HWND, ctypes.c_void_p)

SND_FILENAME = 0x00020000
SND_ASYNC = 0x0001
SND_NODEFAULT = 0x0002
SND_NOSTOP = 0x0010

# ---------- Win32 常量 ----------
WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000
WS_EX_LAYERED = 0x00080000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000   # 字幕窗口：点了也不抢焦点
WS_EX_TRANSPARENT = 0x00000020  # 鼠标穿透，不挡下面窗口
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_TIMER = 0x0113
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205
WM_MOUSEMOVE = 0x0200
ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0
AC_SRC_ALPHA = 1
TPM_RETURNCMD = 0x0100
TPM_RIGHTBUTTON = 0x0002
SRCCOPY = 0x00CC0020
COLORONCOLOR = 3
IDC_HAND = 32649

MONITOR_DEFAULTTONEAREST = 2

IDLE_FPS = 6.0
LAUGH_FPS = 12.0
TIMER_MS = 16
# 笑声的实际时长（秒）。笑段动画就以它为准：声音一停，动画立刻回到原始待机状态。
# 素材的笑段有 16 秒多，但音轨只有 2.6 秒 —— 不裁剪的话会「哑着再笑十几秒」。
LAUGH_SEC = 2.46
# 笑段一共多少帧（App 初始化时按 sprite.json 更新）
LAUGH_SPAN = 199

SCALE_MIN, SCALE_MAX = 0.40, 2.20
GROW_STEP = 0.18        # 每次点击长大 18%（原来的两倍）
GROW_MAX = 5            # 默认「点几次生一只」（可在右键菜单改成 1~10）

MENU_LAUGH = 1
MENU_AUTO = 3
MENU_SOUND = 4
MENU_QUIT = 5
MENU_BOING = 6
MENU_BIGGER = 11
MENU_SMALLER = 12
MENU_RESET = 13
MENU_PRESET_BASE = 20      # 20+i 对应预设百分比列表
MENU_CLICKS_BASE = 40      # 40+n 对应「点 n 次生一只」
MENU_BORN_BASE = 60        # 60+n 对应「一次生 n 只」

PRESETS = [60, 80, 100, 120, 150, 180, 200]
CLICKS_MIN, CLICKS_MAX = 1, 10
BORN_EACH_MIN, BORN_EACH_MAX = 1, 5
BORN_EACH_DEFAULT = 1
POS_SAVE_EVERY = 3.0        # 位置变化后最多这么久落盘一次（别一直写磁盘）

# 优先用 PIL 做逐字节精确缩放（不走 GDI HALFTONE，
# 部分显卡驱动下 HALFTONE 会把预乘 alpha 像素提亮成白色）
try:
    sys.path.insert(0, os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "_lib"))
    from PIL import Image as _PILImage
    from PIL import ImageChops as _PILChops
    import sprite_render as _renderer
except Exception:
    _PILImage = None

# 声音：用 Windows 原生 waveOut（纯 ctypes），不再依赖 numpy / sounddevice。
# 每只奶龙各占一个 waveOut 句柄，由系统混音器负责混合 —— 多只同笑互不打断。
import array as _array


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT),
                ("rcWork", RECT), ("dwFlags", wintypes.DWORD)]


# POINT 定义好之后才能声明签名（否则绑定不到结构体）
user32.MonitorFromPoint.restype = ctypes.c_void_p
user32.MonitorFromPoint.argtypes = (POINT, ctypes.c_uint)


# ---------- 声音：Windows 原生 waveOut（纯 ctypes，零第三方依赖） ----------
# 每只奶龙占一个 waveOut 声部，由系统混音器混合 —— 多只同笑互不打断。
# 句柄在启动时预先开好（开一次要 ~100ms），点击时只做内存拷贝 + write（0.0ms）。
class WAVEFORMATEX(ctypes.Structure):
    _fields_ = [("wFormatTag", ctypes.c_ushort),
                ("nChannels", ctypes.c_ushort),
                ("nSamplesPerSec", ctypes.c_uint32),
                ("nAvgBytesPerSec", ctypes.c_uint32),
                ("nBlockAlign", ctypes.c_ushort),
                ("wBitsPerSample", ctypes.c_ushort),
                ("cbSize", ctypes.c_ushort)]


class WAVEHDR(ctypes.Structure):
    _fields_ = [("lpData", ctypes.c_char_p),
                ("dwBufferLength", ctypes.c_uint32),
                ("dwBytesRecorded", ctypes.c_uint32),
                ("dwUser", ctypes.c_size_t),
                ("dwFlags", ctypes.c_uint32),
                ("dwLoops", ctypes.c_uint32),
                ("lpNext", ctypes.c_void_p),
                ("reserved", ctypes.c_size_t)]


WHDR_DONE = 0x00000001
WAVE_FORMAT_PCM = 1
WAVE_MAPPER = 0xFFFFFFFF
POOL_SIZE = 10          # 同时最多这么多个独立声部（10 只同笑也够）

# ---------- 待机散步 ----------
# 素材里没有走路的帧，就用待机动画 + 左右移动 + 小碎步颠簸来表现：
# 走一会儿 → 歇一会儿（继续待机动画）→ 随机换个方向接着走。
# 只在屏幕底部（任务栏上方）走；被拖到别处歇一会儿后会自己走回底部。
WALK_SPEED = 85.0        # 水平步速（像素/秒）——与迈步步幅匹配，落地脚不打滑
WALK_FALL = 200.0        # 被拖到高处后走回底部的下降速度（像素/秒）
WALK_BURST = (1.8, 4.5)  # 每次连续走多久（秒）
WALK_REST = (4.0, 9.0)   # 两次散步之间歇多久（秒）
WALK_BOB = 0.030         # 迈步颠簸幅度（占身高的比例）
WALK_BOB_HZ = 2.4        # 步频（一个迈步周期/秒 ×2π，两脚各走一步）

# ---------- 走路：两条腿左右交替迈步（纸片式局部形变，不撕裂身体） ----------
# 素材是 3/4 侧站姿，两腿间 y240~285 有天然透明缝（x127~154），
# 可以对两条腿分别做位移：以腿根为轴水平摆动（剪刀步），
# 一条腿向前迈时另一条向后蹬，相位差 π。
LEG_TOP = 222             # 腿根（渐变起点，这里位移恒 0）
LEG_L_SP = (71, 131, 298)   # 素材坐标：后腿 x0,x1 与脚底 y
LEG_R_SP = (132, 184, 311)  # 素材坐标：前腿 x0,x1 与脚底 y
LEG_SWING = 10.0          # 脚底最大水平摆幅（sprite 像素，单侧 ≈ 腿长 11%）
LEG_LIFT = 8.0            # 向前摆动时脚的最大抬起高度（向后蹬时贴地）
LEG_EASE = 1.6            # 渐变指数：腿根缓、脚底全幅

# ---------- 眼神追踪（待机时瞳孔跟着鼠标转） ----------
# 原理：先把原瞳孔抹掉（从虹膜环按同角度取色填回，保留渐变），
# 再在朝鼠标的方向画上新瞳孔 —— 瞳孔在虹膜里移动，画风不变。
# 坐标均为 sprite 像素（243×319），随窗口缩放。
EYE_R_ERASE = 6.6        # 抹除原瞳孔的半径
EYE_R_PUPIL = 4.4        # 新瞳孔半径
EYE_TRACK = 3.4          # 瞳孔最大偏移（水平；3.4+4.4 ≈ 虹膜半径 8，转到边）
EYE_TRACK_Y = 2.6        # 瞳孔最大偏移（垂直）
EYE_FOLLOW = 0.45        # 追随速度（每拍向目标靠拢的比例，越大越跟手）

# ---------- 摸肚子：肚皮弹一下 ----------
# 鼠标移到肚子上 → 只有肚皮上下弹动（头、手、脚不动），像被戳了一下。
# 实现：在肚皮那一段高度上做「按行垂直错位」，两端衰减到 0，中间最大，
# 看起来就是肚皮鼓起来又回弹（不是整只奶龙跳起来）。
BELLY_TOP = 0.36         # 弹动范围：占 sprite 高度的比例
BELLY_BOT = 0.74
WOB_DUR = 1.00           # 一次弹动的总时长（秒）
WOB_HZ = 4.6             # 弹动频率（来回几次/秒）
WOB_H = 0.160            # 最大形变（占身高的比例，约 46px；再大会把胸口拖进腹部）
WOB_DAMP = 3.0           # 衰减速度（越大停得越快；3.0 → 视觉上弹约 1 秒）
BOUNCE_COOL = 0.80       # 冷却：这么快之内不重复弹（防止来回蹭连弹）

# ---------- 摸肚子音效 ----------
# 运行时合成的一声「啵嘤」，不占打包体积；右键菜单可随时开关。
SFX_SEC = 0.22           # 音效时长（秒）
SFX_VOL = 0.34           # 音量（相对满幅，轻一点别吓人）
SFX_SR = 44100           # 采样率
SFX_CH = 1               # 单声道就够
SFX_VOICES = 3           # 音效专用声部数（连戳几声也叠得住）
SFX_PITCH = (0.94, 1.0, 1.06)   # 预合成的三个音高变体，连戳不呆板

if _winmm is not None:
    _winmm.waveOutOpen.argtypes = (
        ctypes.POINTER(ctypes.c_void_p), ctypes.c_uint,
        ctypes.POINTER(WAVEFORMATEX), ctypes.c_size_t, ctypes.c_size_t,
        ctypes.c_uint)
    _winmm.waveOutPrepareHeader.argtypes = (
        ctypes.c_void_p, ctypes.POINTER(WAVEHDR), ctypes.c_uint)
    _winmm.waveOutWrite.argtypes = (
        ctypes.c_void_p, ctypes.POINTER(WAVEHDR), ctypes.c_uint)
    _winmm.waveOutUnprepareHeader.argtypes = (
        ctypes.c_void_p, ctypes.POINTER(WAVEHDR), ctypes.c_uint)
    _winmm.waveOutClose.argtypes = (ctypes.c_void_p,)
    _winmm.waveOutReset.argtypes = (ctypes.c_void_p,)

_WAV_CACHE = {}         # path -> (raw_bytes, sr, ch, sw)
_POOL = None            # dict(sr, ch, sw, slots=[_WaveSlot...])
_POOL_LOCK = threading.Lock()


def _load_wav_bytes(path):
    """读 wav -> (PCM 字节, 采样率, 声道, 采样宽度)；失败返回 (None,0,0,0)。
    顺手掐掉开头静音 —— 否则点下去要等一百多毫秒才响，听着像"卡了一下"。"""
    hit = _WAV_CACHE.get(path)
    if hit is not None:
        return hit
    try:
        import wave
        w = wave.open(path, "rb")
        try:
            sr, ch, sw = (w.getframerate(), w.getnchannels(),
                          w.getsampwidth())
            raw = w.readframes(w.getnframes())
        finally:
            w.close()
        if sw != 2 or ch < 1 or not raw:
            return None, 0, 0, 0
        # 找第一个有声采样（16bit，阈值 2% 满幅）。每两帧看一次足够快也够准。
        a = _array.array("h")
        a.frombytes(raw)
        thr = int(0.02 * 32767)
        first = 0
        for i in range(0, len(a), ch * 2):
            v = a[i]
            if v > thr or v < -thr:
                first = i
                break
        if first > 0:
            raw = raw[max(0, first - 1) * 2:]
        out = (raw, sr, ch, sw)
        _WAV_CACHE[path] = out
        return out
    except Exception:
        return None, 0, 0, 0


class _WaveSlot(object):
    """一个 waveOut 声部：自己一条播放通道，播完自动空闲，可反复复用。"""
    __slots__ = ("h", "buf", "hdr", "busy", "cap")

    def __init__(self, fmt, cap):
        self.h = ctypes.c_void_p()
        r = _winmm.waveOutOpen(ctypes.byref(self.h), WAVE_MAPPER,
                               ctypes.byref(fmt), 0, 0, 0)
        if r != 0:
            raise OSError("waveOutOpen=%d" % r)
        self.cap = cap
        self.buf = ctypes.create_string_buffer(cap)
        self.hdr = WAVEHDR()
        self.hdr.lpData = ctypes.cast(self.buf, ctypes.c_char_p)
        self.hdr.dwBufferLength = cap
        _winmm.waveOutPrepareHeader(self.h, ctypes.byref(self.hdr),
                                    ctypes.sizeof(WAVEHDR))
        self.busy = False

    def play(self, data):
        n = min(len(data), self.cap)
        ctypes.memmove(self.buf, data, n)
        self.hdr.dwBufferLength = n
        self.hdr.dwFlags = 0
        _winmm.waveOutUnprepareHeader(self.h, ctypes.byref(self.hdr),
                                      ctypes.sizeof(WAVEHDR))
        r1 = _winmm.waveOutPrepareHeader(self.h, ctypes.byref(self.hdr),
                                         ctypes.sizeof(WAVEHDR))
        r2 = _winmm.waveOutWrite(self.h, ctypes.byref(self.hdr),
                                 ctypes.sizeof(WAVEHDR))
        ok = (r1 == 0 and r2 == 0)
        self.busy = ok
        return ok

    def done(self):
        return bool(self.hdr.dwFlags & WHDR_DONE)

    def free(self):
        if not self.busy:
            return True
        if self.done():
            self.busy = False
            return True
        return False

    def close(self):
        try:
            _winmm.waveOutReset(self.h)
            _winmm.waveOutUnprepareHeader(self.h, ctypes.byref(self.hdr),
                                          ctypes.sizeof(WAVEHDR))
            _winmm.waveOutClose(self.h)
        except Exception:
            pass


def _get_pool(path):
    """按 wav 的格式建立/复用声部池。返回 (pool, raw_bytes)。"""
    global _POOL
    raw, sr, ch, sw = _load_wav_bytes(path)
    if raw is None:
        return None, None
    with _POOL_LOCK:
        p = _POOL
        if p is not None and p["sr"] == sr and p["ch"] == ch:
            return p, raw
        if p is not None:                   # 格式变了（换音轨）：重建
            for s in p["slots"]:
                s.close()
            _POOL = None
        fmt = WAVEFORMATEX(WAVE_FORMAT_PCM, ch, sr, sr * ch * sw,
                           ch * sw, sw * 8, 0)
        slots = []
        for _ in range(POOL_SIZE):
            try:
                slots.append(_WaveSlot(fmt, len(raw) + 64))
            except Exception:
                break                        # 声部开不出来就少开几路
        if not slots:
            return None, None
        _POOL = dict(sr=sr, ch=ch, sw=sw, slots=slots)
        return _POOL, raw


def _play_wav_stream(path, from_frame=0):
    """播一路独立笑声。成功交给 waveOut 返回 True，否则交给上层走兜底。"""
    if _winmm is None:
        return False
    try:
        pool, raw = _get_pool(path)
        if pool is None or raw is None:
            return False
        # 笑段总帧数在整个 LAUGH_SEC 内播完，一帧 = LAUGH_SEC / 总帧数 秒
        per_frame = LAUGH_SEC / float(max(1, LAUGH_SPAN))
        bpf = pool["ch"] * pool["sw"]        # 每个时间点的字节数
        off = int(float(from_frame) * per_frame * pool["sr"]) * bpf
        off = max(0, off - off % bpf)
        seg = raw[off:]
        if not seg:
            return False
        for slot in pool["slots"]:
            if slot.free():
                return slot.play(seg)
        # 声部全忙（10 只以上同笑）：抢占第一个，保证总有声音
        return pool["slots"][0].play(seg)
    except Exception:
        return False


def _play_fallback(path):
    """没有软件混音时的兜底：系统单通道播放（多只会互相打断，但至少有声）"""
    try:
        if _winmm is not None:
            _winmm.PlaySoundW(
                path, None,
                SND_FILENAME | SND_ASYNC | SND_NODEFAULT | SND_NOSTOP)
    except Exception:
        pass


# ---------- 内置音效（运行时合成，零文件依赖） ----------
_SFX_CACHE = {}         # 变体名 -> (raw, sr, ch, sw)
_SFX_POOL = None        # 音效专用声部池（和笑声分开，缓冲尺寸互不干扰）
_SFX_LOCK = threading.Lock()


def _synth_boing(sr=SFX_SR, ch=SFX_CH, sw=2, pitch=1.0):
    """合成一声「啵嘤」：先「啵」一下（偏低、带颤音的回弹感），再快速收干。
    纯 array 手算（不依赖 numpy），软削波防爆音。"""
    n = max(1, int(sr * SFX_SEC))
    a = _array.array("h", bytes(n * ch * sw))
    f0 = 720.0 * pitch              # 起音：短促的「啵」
    f1 = 250.0 * pitch              # 收尾：往下沉，像肚皮回弹
    phase = 0.0
    for i in range(n):
        t = i / float(sr)
        k = i / float(n)            # 0..1 进度
        # 基频下滑 + 38Hz 颤音（颤音给一点"橡皮/塑料"的弹性味）
        f = f0 + (f1 - f0) * (k ** 0.75)
        f *= 1.0 + 0.055 * math.sin(2.0 * math.pi * 38.0 * t)
        phase += 2.0 * math.pi * f / sr
        # 快起（1-e^-150t）慢落（e^-6k）：一记软弹，尾巴带一点余韵
        env = math.exp(-6.0 * k) * (1.0 - math.exp(-150.0 * t))
        v = math.sin(phase) + 0.26 * math.sin(2.0 * phase) \
            + 0.10 * math.sin(3.0 * phase)
        v = math.tanh(v * env * SFX_VOL * 1.6)
        s = int(max(-1.0, min(1.0, v)) * 32767)
        for c in range(ch):
            a[i * ch + c] = s
    return a.tobytes()


def _get_sfx_pool(raw, sr, ch, sw):
    """音效专用声部池。独立于笑声池：缓冲按音效长度开，短小且不与长笑声抢。"""
    global _SFX_POOL
    with _SFX_LOCK:
        p = _SFX_POOL
        if p is not None and p["sr"] == sr and p["ch"] == ch \
                and p["cap"] >= len(raw):
            return p
        if p is not None:
            for s in p["slots"]:
                s.close()
            _SFX_POOL = None
        fmt = WAVEFORMATEX(WAVE_FORMAT_PCM, ch, sr, sr * ch * sw,
                           ch * sw, sw * 8, 0)
        slots = []
        for _ in range(SFX_VOICES):
            try:
                slots.append(_WaveSlot(fmt, max(len(raw) + 64, 2048)))
            except Exception:
                break
        if not slots:
            return None
        _SFX_POOL = dict(sr=sr, ch=ch, sw=sw, cap=len(raw) + 64, slots=slots)
        return _SFX_POOL


def _warm_sfx():
    """预合成几个音高变体并把声部开好 —— 第一次戳肚子才不会有 100ms 延迟。"""
    try:
        for k, pitch in enumerate(SFX_PITCH):
            name = "boing%d" % k
            if name in _SFX_CACHE:
                continue
            raw = _synth_boing(SFX_SR, SFX_CH, 2, pitch)
            _SFX_CACHE[name] = (raw, SFX_SR, SFX_CH, 2)
            _get_sfx_pool(raw, SFX_SR, SFX_CH, 2)
        return True
    except Exception:
        return False


def _play_sfx(name=None):
    """播放内置音效（默认随机挑一个音高变体）。返回 True = 已交给 waveOut。"""
    if _winmm is None:
        return False
    try:
        if name is None:
            cands = [k for k in _SFX_CACHE if k.startswith("boing")]
            name = random.choice(cands) if cands else "boing0"
        hit = _SFX_CACHE.get(name)
        if hit is None:                         # 预热没跑到，现场合成
            hit = (_synth_boing(SFX_SR, SFX_CH, 2, 1.0), SFX_SR, SFX_CH, 2)
            _SFX_CACHE[name] = hit
        raw, sr, ch, sw = hit
        pool = _get_sfx_pool(raw, sr, ch, sw)
        if pool is None:
            return False
        for slot in pool["slots"]:
            if slot.free():
                return slot.play(raw)
        return pool["slots"][0].play(raw)       # 全忙就抢占，保证有反馈
    except Exception:
        return False


def _shutdown_audio():
    """退出前把 waveOut 句柄全部关掉。
    不关的话解释器退出时音频驱动线程可能还在读已释放的缓冲 → 段错误
    （表现为程序退出瞬间崩一下、事件日志里留一条异常）。"""
    global _POOL, _SFX_POOL
    for keeper in (_POOL, _SFX_POOL):
        if not keeper:
            continue
        for s in keeper.get("slots", ()):
            try:
                s.close()
            except Exception:
                pass
    _POOL = None
    _SFX_POOL = None


class MSG(ctypes.Structure):
    _fields_ = [("hwnd", wintypes.HWND), ("message", wintypes.UINT),
                ("wParam", wintypes.WPARAM), ("lParam", wintypes.LPARAM),
                ("time", wintypes.DWORD), ("pt", POINT)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_byte), ("BlendFlags", ctypes.c_byte),
                ("SourceConstantAlpha", ctypes.c_byte),
                ("AlphaFormat", ctypes.c_byte)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32),
                ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16),
                ("biBitCount", ctypes.c_uint16),
                ("biCompression", ctypes.c_uint32),
                ("biSizeImage", ctypes.c_uint32),
                ("biXPelsPerMeter", ctypes.c_int32),
                ("biYPelsPerMeter", ctypes.c_int32),
                ("biClrUsed", ctypes.c_uint32),
                ("biClrImportant", ctypes.c_uint32)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER),
                ("bmiColors", ctypes.c_uint32 * 3)]


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", ctypes.c_uint),
                ("lpfnWndProc", ctypes.c_void_p),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON),
                ("hCursor", ctypes.c_void_p),
                ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR)]


WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, wintypes.HWND, wintypes.UINT,
                             wintypes.WPARAM, wintypes.LPARAM)

user32.DefWindowProcW.restype = ctypes.c_longlong
user32.DefWindowProcW.argtypes = (wintypes.HWND, wintypes.UINT,
                                  wintypes.WPARAM, wintypes.LPARAM)
user32.SendMessageW.restype = ctypes.c_longlong
user32.SendMessageW.argtypes = (wintypes.HWND, wintypes.UINT,
                                wintypes.WPARAM, wintypes.LPARAM)
user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = (
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID)

# 所有奶龙窗口共用一个窗口类，消息按 hwnd 分发到对应实例
PETS = {}          # hwnd -> Pet
_WNDPROC_REF = None
_CLASS_REGISTERED = False

# 缩放后的帧缓存：(宽, 高, 帧号) -> BGRA 字节；多只奶龙共用，省 CPU
_SCALE_CACHE = OrderedDict()
_SCALE_CACHE_MAX = 48
_SCALE_CACHE_BYTES = 48 * 1024 * 1024


def _dispatch(hwnd, msg, wp, lp):
    pet = PETS.get(hwnd)
    if pet is not None and pet.hwnd:
        return pet._proc(hwnd, msg, wp, lp)
    return user32.DefWindowProcW(hwnd, msg, wp, lp)


class Sprite(object):
    """一次加载、所有奶龙共享的贴图数据（省内存）"""

    def __init__(self, here):
        with open(os.path.join(here, "sprite.json"), encoding="utf-8") as f:
            meta = json.load(f)
        with open(os.path.join(here, "sprite.dat"), "rb") as f:
            blob = zlib.decompress(f.read())
        self.w = meta["w"]
        self.h = meta["h"]
        self.n = meta["n"]
        self.stride = self.w * self.h * 4
        self.frames = [blob[i * self.stride:(i + 1) * self.stride]
                       for i in range(self.n)]
        self.idle_lo, self.idle_hi = meta["idle"]
        self.laugh_lo, self.laugh_hi = meta["laugh"]
        # 待机各帧的瞳孔位置（眨眼帧记 None，画眼睛时跳过）+ 瞳孔颜色
        self.eyes = self._scan_eyes()
        self.pupil_col = self._pupil_color()
        # 待机循环只播「眼睛睁开且瞳孔在正中」的帧：眨眼帧、原素材看别处的帧
        # 全部剔除，这样不会眨眼，眼神追踪也每一帧都生效。
        self.idle_play = [self.idle_lo + i for i, c in enumerate(self.eyes)
                          if c is not None] or [self.idle_lo]
        self.idle_play += self.idle_play[-2:0:-1]

    def _scan_eyes(self):
        """逐个待机帧找瞳孔：搜索窗内「很暗」像素的质心。
        跳过两类帧（记 None，画眼睛时用素材原样）：
        · 眨眼/半闭眼帧 —— 暗像素太少，或者是眼缝不是瞳孔
        · 原素材里瞳孔移位的帧（如看向别处）—— 抹除圈会错位/污染虹膜边缘
        只有「瞳孔在虹膜正中附近、且足够大」的帧才做眼神覆盖。"""
        x0, y0, x1, y1 = 99, 15, 119, 33      # 搜索窗（sprite 坐标，眼睛附近）
        raw = []
        for i in range(self.idle_lo, self.idle_hi + 1):
            fr = self.frames[i]
            sx = sy = n = 0
            for y in range(y0, y1):
                row = y * self.w
                for x in range(x0, x1):
                    j = (row + x) * 4
                    if fr[j + 3] > 200 and fr[j] < 75 and fr[j + 1] < 75 \
                            and fr[j + 2] < 75:
                        sx += x
                        sy += y
                        n += 1
            raw.append(None if n < 45 else (sx / float(n), sy / float(n)))
        # 以第一帧有效瞳孔为基准，中心偏移超过 3px 的帧不画（瞳孔不在正中）
        ref = next((c for c in raw if c is not None), None)
        out = []
        for c in raw:
            if c is None or ref is None or abs(c[0] - ref[0]) > 3.0 \
                    or abs(c[1] - ref[1]) > 3.0:
                out.append(None)
            else:
                out.append(c)
        return out

    def _pupil_color(self):
        """瞳孔颜色：取第一帧瞳孔像素的平均色（BGR），画新瞳孔用"""
        fr = self.frames[self.idle_lo]
        rs = gs = bs = n = 0
        for y in range(15, 33):
            for x in range(99, 119):
                j = (y * self.w + x) * 4
                if fr[j + 3] > 200 and fr[j] < 75 and fr[j + 1] < 75 \
                        and fr[j + 2] < 75:
                    rs += fr[j + 2]
                    gs += fr[j + 1]
                    bs += fr[j]
                    n += 1
        return (rs // n, gs // n, bs // n) if n else (22, 22, 26)


class Pet(object):
    def __init__(self, app, x, y, grow=0, pop=False):
        self.app = app
        self.sp = app.sprite
        self.hwnd = None
        self.grow = grow
        self.mode = "idle"
        self.idx = self.sp.idle_lo
        self.mode_t0 = time.time()
        self.drag = None
        self.fade = 1.0
        self.dying = False
        self.absorb = None          # 回收动画：飞向留下那只的进度信息
        self.litters = 0            # 已经生过几次；生过的奶龙会一直留着
        self.awaiting = 0           # 还有几只生出来的娃没笑完（>0 时本体不退场）
        self.parent = None          # 谁生的我（笑完/消失时给本体减计数）
        self.next_auto = time.time() + random.uniform(10.0, 20.0)

        # 待机散步状态：走一段歇一段，只沿屏幕底部走
        self.face = 1               # 朝向：1 = 素材原方向，-1 = 水平镜像
        self.walk_dir = 0           # 正在走：-1 向左 / +1 向右 / 0 站着
        self.walk_until = 0.0       # 本次散步走到这个时刻为止
        self.next_walk = time.time() + random.uniform(2.0, 5.0)
        self.walk_t = time.time()   # 上次推进时刻（算 dt 用）
        self.walk_acc = 0.0         # 步速小数累积（55px/s 在 30ms 拍下不足 1px）
        self.bob = 0                # 走路颠簸的垂直偏移（px，渲染时加到 y）

        # 眼神追踪：瞳孔相对虹膜中心的偏移（sprite 像素）+ 已重画的标记
        self.eye_off = [0.0, 0.0]
        self.eye_mark = None
        self.idle_mix = None
        self._last_tick = time.time()

        # 摸肚子：肚皮弹动（形变幅度，渲染时按行错位用）
        self.wob = 0.0              # 当前形变（px，负=往上鼓）
        self.wob_t0 = 0.0           # 本次弹动起始时刻（0 = 没在弹）
        self.belly_in = False       # 鼠标是否已经在肚子上（只在「进入」时触发）
        self.bounce_next = 0.0      # 下次允许弹的时刻

        base = app.base_scale
        self.scale = base * (1 + GROW_STEP * grow)
        self.target = self.scale
        if pop:                      # 分裂出来时从小弹到正常大小
            self.scale = base * 0.62
            self.target = base
        self.w = max(1, int(round(self.sp.w * self.scale)))
        self.h = max(1, int(round(self.sp.h * self.scale)))
        self.x, self.y = int(x), int(y)

        self._create_window()
        self._create_canvas()
        self.render(self.idx)
        user32.SetTimer(self.hwnd, 1, TIMER_MS, None)

    # ---------- 窗口 ----------
    def _create_window(self):
        hinst = kernel32.GetModuleHandleW(None)
        self.hwnd = user32.CreateWindowExW(
            WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW,
            "NailongPetWnd", "奶龙桌宠", WS_POPUP | WS_VISIBLE,
            self.x, self.y, self.w, self.h, None, None, hinst, None)
        PETS[self.hwnd] = self

    def _make_dib(self, w, h):
        dc = gdi32.CreateCompatibleDC(self.app.hdc_screen)
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = w
        bmi.bmiHeader.biHeight = -h          # top-down
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0
        bits = ctypes.c_void_p()
        bmp = gdi32.CreateDIBSection(dc, ctypes.byref(bmi), 0,
                                     ctypes.byref(bits), None, 0)
        gdi32.SelectObject(dc, bmp)
        return dc, bmp, bits

    def _create_canvas(self):
        self.hdc_src, self.hbmp_src, self.src_bits = self._make_dib(
            self.sp.w, self.sp.h)
        # 目标画布一次性按最大可能尺寸分配，缩放动画时只改子区域，
        # 不再反复重建 DIB（反复重建会导致 GDI 句柄失效崩溃）
        self.max_w = max(1, int(round(self.sp.w * SCALE_MAX)))
        self.max_h = max(1, int(round(self.sp.h * SCALE_MAX)))
        self.hdc_dst, self.hbmp_dst, self.dst_bits = self._make_dib(
            self.max_w, self.max_h)
        # 可直接寻址的画布像素（画瞳孔覆盖层用）
        addr = self.dst_bits.value if isinstance(self.dst_bits,
                                                 ctypes.c_void_p) \
            else self.dst_bits
        self.dst_buf = (ctypes.c_ubyte
                        * (self.max_w * self.max_h * 4)).from_address(addr)

    def release_parent(self):
        """告诉本体：我这个娃已经收场了（只还一次）"""
        p = self.parent
        self.parent = None
        if p is not None and p.awaiting > 0:
            p.awaiting -= 1

    def destroy(self):
        if not self.hwnd:
            return
        hwnd = self.hwnd
        self.hwnd = None
        PETS.pop(hwnd, None)
        # 不管怎样退场，都要给本体把「娃」的计数还回去
        self.release_parent()
        user32.KillTimer(hwnd, 1)
        user32.DestroyWindow(hwnd)
        try:
            gdi32.DeleteObject(self.hbmp_dst)
            gdi32.DeleteDC(self.hdc_dst)
            gdi32.DeleteObject(self.hbmp_src)
            gdi32.DeleteDC(self.hdc_src)
        except Exception:
            pass
        self.app.on_pet_gone()

    # ---------- 渲染 ----------
    def _scale_frame(self, idx, flip=False, size=None):
        """把第 idx 帧缩放到当前尺寸（flip=True 时水平镜像，走路换向用），
        返回 w*h*4 的 BGRA 预乘字节。
        结果按 (宽, 高, 帧号, 是否镜像) 缓存 —— 奶龙越来越多时不用重复做缩放。"""
        sp = self.sp
        width, height = size or (self.w, self.h)
        key = (width, height, idx, 1 if flip else 0)
        data = _SCALE_CACHE.get(key)
        if data is not None:
            _SCALE_CACHE.move_to_end(key)
            return data
        frame = sp.frames[idx]
        if _PILImage is not None:
            # The sprite already contains premultiplied BGRA. RGBA would
            # premultiply it a second time while resampling, darkening edges.
            img = _PILImage.frombytes("RGBa", (sp.w, sp.h), frame)
            if flip:
                img = img.transpose(_PILImage.FLIP_LEFT_RIGHT)
            img = img.resize((width, height), _PILImage.Resampling.LANCZOS)
            b, g, r, a = img.split()
            # Lanczos ringing must never produce color above coverage.
            img = _PILImage.merge("RGBa", (
                _PILChops.darker(b, a), _PILChops.darker(g, a),
                _PILChops.darker(r, a), a))
            data = img.tobytes()
        else:
            # 兜底：最近邻（无 PIL 时才走到这里）
            xs = [min(sp.w - 1, int(x * sp.w / width)) * 4
                  for x in range(width)]
            if flip:
                xs = xs[::-1]          # 输出列倒序 = 水平镜像
            out = bytearray()
            for y in range(height):
                sy = min(sp.h - 1, int(y * sp.h / height)) * sp.w * 4
                out += b"".join(frame[sy + x:sy + x + 4] for x in xs)
            data = bytes(out)
        while _SCALE_CACHE and (len(_SCALE_CACHE) >= _SCALE_CACHE_MAX
                or sum(len(value) for value in _SCALE_CACHE.values())
                + len(data) > _SCALE_CACHE_BYTES):
            _SCALE_CACHE.popitem(last=False)
        _SCALE_CACHE[key] = data
        return data

    def _render_pixels(self, idx):
        """Compose eyes and continuous deformations before the final downsample."""
        # Keep a dense working image at small sizes without multiplying the
        # cost again once the sprite is already enlarged on screen.
        sampling = min(2.0, max(1.0, 1.8 * self.sp.h / self.h))
        size = (max(self.w, round(self.w * sampling)),
                max(self.h, round(self.h * sampling)))
        source = self._scale_frame(idx, self.face < 0, size)
        image = _PILImage.frombytes("RGBa", size, source)
        mix = getattr(self, "idle_mix", None)
        if self.mode == "idle" and mix and mix[1]:
            following = _PILImage.frombytes("RGBa", size,
                self._scale_frame(mix[0], self.face < 0, size))
            image = _PILImage.blend(image, following, mix[1] / 8.0)
            source = image.tobytes()
        if self.wob:
            image = _renderer.belly_warp(image, self.wob * size[1] / self.h,
                                         BELLY_TOP, BELLY_BOT)
        elif self.walk_dir:
            image = _renderer.walking_legs(
                image, (self.sp.w, self.sp.h), (LEG_L_SP, LEG_R_SP),
                LEG_TOP, LEG_SWING, LEG_LIFT, LEG_EASE,
                time.time() * WALK_BOB_HZ * 2 * math.pi, self.face < 0)
        if self.mode == "idle" and not self.dying:
            buffer = bytearray(image.tobytes())
            self._draw_eyes(source, size=size, buffer=buffer)
            image = _PILImage.frombytes("RGBa", size, bytes(buffer))
        if size != (self.w, self.h):
            image = image.resize((self.w, self.h), _PILImage.Resampling.LANCZOS)
        return _renderer.clamp_premultiplied(image).tobytes()

    def render(self, idx):
        if not self.hwnd:
            return
        if getattr(self, "_in_tick", False):
            self._pending_render = idx
            return
        sp = self.sp
        flip = self.face < 0
        composed = _PILImage is not None
        if composed:
            data = self._render_pixels(idx)
        elif not flip and (self.w, self.h) == (sp.w, sp.h):
            data = sp.frames[idx]
        else:
            data = self._scale_frame(idx, flip)

        # 逐行拷进最大画布（画布行宽与图像行宽不同，需按行搬）
        row = self.w * 4
        dst_stride = self.max_w * 4
        dst = self.dst_bits.value if isinstance(self.dst_bits, ctypes.c_void_p) \
            else self.dst_bits
        if (composed or self.wob == 0) and row == dst_stride and self.h == self.max_h:
            ctypes.memmove(dst, data, row * self.h)
        elif composed or self.wob == 0:
            for y in range(self.h):
                ctypes.memmove(dst + y * dst_stride,
                               data[y * row:(y + 1) * row], row)
        else:
            # 肚皮弹动：只把肚皮那一段高度按正弦窗错位（两端衰减到 0，
            # 中间幅度最大）→ 肚皮鼓起来又回弹，头和脚纹丝不动
            by0 = int(self.h * BELLY_TOP)
            by1 = int(self.h * BELLY_BOT)
            span = float(max(1, by1 - by0))
            for y in range(self.h):
                sy = y
                if by0 <= y <= by1:
                    sy = y + int(round(self.wob
                                       * math.sin((y - by0) / span * math.pi)))
                    if sy < 0:
                        sy = 0
                    elif sy >= self.h:
                        sy = self.h - 1
                ctypes.memmove(dst + y * dst_stride,
                               data[sy * row:(sy + 1) * row], row)

        # 走路时两条腿左右交替迈步。戳肚子形变时让位（两种错位都是按行搬，
        # 同时开会打架），戳肚子是瞬时动作、走路是常态，让常态优先级低些
        if not composed and self.walk_dir and self.wob == 0:
            self._blit_walking_legs(dst, dst_stride, data, row)

        # 眼神覆盖层：待机时把瞳孔画到 eye_off 方向（别的状态用素材原样）
        if not composed and self.mode == "idle" and not self.dying:
            self._draw_eyes(data)

        # bob：走路时的小碎步颠簸（没走路时恒为 0）
        pt_dst = POINT(self.x, self.y + self.bob)
        size = SIZE(self.w, self.h)
        pt_src = POINT(0, 0)
        alpha = max(0, min(255, int(round(255 * self.fade))))
        blend = BLENDFUNCTION(AC_SRC_OVER, 0, alpha, AC_SRC_ALPHA)
        user32.UpdateLayeredWindow(
            self.hwnd, self.app.hdc_screen, ctypes.byref(pt_dst),
            ctypes.byref(size), self.hdc_dst, ctypes.byref(pt_src),
            0, ctypes.byref(blend), ULW_ALPHA)

        # 记下本体的位置+朝向（重启后回到这里）。只记本体，不记生出来的娃，
        # 否则娃的坐标会把本体的覆盖掉。
        if self.parent is None:
            self.app.note_pos(self.x, self.y, self.face)

    def _blit_walking_legs(self, dst, dst_stride, data, row):
        """走路时两条腿左右交替迈步（纸片式剪刀步）：
        - 每条腿以腿根为轴做水平摆动：腿根位移 0、脚底全幅，与身体无缝衔接
        - 两条腿相位差 π：一条向前迈时另一条向后蹬（左右交替出脚）
        - 向前摆的半程脚微微抬起（脚底离地），向后蹬的半程贴地滑动
        - 腿让出的拖尾空隙清成透明（露出地面阴影/桌面）
        - face<0 时贴图已镜像，腿区域用镜像后的显示坐标；近侧腿最后画（压上层）
        每行一次 memmove（腿是连续横向段），无逐像素循环。"""
        sp = self.sp
        scx = self.w / float(sp.w)
        scy = self.h / float(sp.h)
        swing = LEG_SWING * scx
        lift = LEG_LIFT * scy
        if swing < 1.0 and lift < 1.0:
            return
        top = int(LEG_TOP * scy)
        if self.face < 0:
            # 镜像后近侧腿（原前腿）在左，远侧腿在右；近侧腿放最后画
            legs = ((sp.w - 1 - LEG_L_SP[1], sp.w - 1 - LEG_L_SP[0],
                     LEG_L_SP[2]),
                    (sp.w - 1 - LEG_R_SP[1], sp.w - 1 - LEG_R_SP[0],
                     LEG_R_SP[2]))
        else:
            legs = ((LEG_L_SP[0], LEG_L_SP[1], LEG_L_SP[2]),
                    (LEG_R_SP[0], LEG_R_SP[1], LEG_R_SP[2]))
        fwd = 1.0 if self.face > 0 else -1.0
        ph = time.time() * WALK_BOB_HZ * 2 * math.pi
        rects = []
        for k, (fx0, fx1, fbot) in enumerate(legs):
            s = math.sin(ph + k * math.pi)     # 前后位置（迈步相位）
            c = math.cos(ph + k * math.pi)     # >0 正在向前摆（抬脚）
            x0 = max(0, int(round(fx0 * scx)))
            x1 = min(self.w - 1, int(round(fx1 * scx)))
            bot = min(self.h - 1, int(round(fbot * scy)))
            rects.append((x0, x1, bot, max(1.0, float(bot - top)),
                          fwd * swing * s, lift * max(0.0, c)))
        blank = bytes(max(x1 - x0 + 1 for x0, x1, _, _, _, _ in rects) * 4)
        # 第一遍：把每条腿水平让出的拖尾空隙清成透明
        for x0, x1, bot, span, dxm, lft in rects:
            for y in range(top, bot + 1):
                dx = int(round(dxm * ((y - top) / span) ** LEG_EASE))
                if dx == 0:
                    continue
                if dx > 0:
                    cx0, cx1 = x0, min(x1, x0 + dx - 1)
                else:
                    cx0, cx1 = max(x0, x1 + dx + 1), x1
                seg = (cx1 - cx0 + 1) * 4
                if seg > 0:
                    ctypes.memmove(dst + y * dst_stride + cx0 * 4,
                                   blank, seg)
        # 第二遍：把腿画到摆动后的位置（循环末尾的是近侧腿，盖在上面）
        for x0, x1, bot, span, dxm, lft in rects:
            seg = (x1 - x0 + 1) * 4
            for y in range(top, bot + 1):
                e = ((y - top) / span) ** LEG_EASE
                dx = int(round(dxm * e))
                dy = int(round(lft * e))
                tx0 = x0 + dx
                if tx0 < 0:
                    tx0 = 0
                elif tx0 + (x1 - x0) >= self.w:
                    tx0 = self.w - 1 - (x1 - x0)
                sy = y + dy
                if sy >= self.h:
                    # 源行越出画面下缘（脚抬得很高时）：这行原来的脚
                    # 内容必须清成空白，否则地上会留下脚底残影
                    ctypes.memmove(dst + y * dst_stride + tx0 * 4,
                                   blank, seg)
                    continue
                ctypes.memmove(
                    dst + y * dst_stride + tx0 * 4,
                    data[sy * row + x0 * 4:sy * row + x0 * 4 + seg], seg)

    # ---------- 缩放 ----------
    def _apply_scale(self, s):
        s = max(SCALE_MIN, min(SCALE_MAX, float(s)))
        nw = max(1, int(round(self.sp.w * s)))
        nh = max(1, int(round(self.sp.h * s)))
        if (nw, nh) == (self.w, self.h):
            self.scale = s
            return
        # 以脚底中心为锚点
        self.x += (self.w - nw) // 2
        self.y += (self.h - nh)
        self.scale = s
        self.w, self.h = nw, nh
        self.render(self.idx)

    def refresh_base_scale(self, base):
        # 点得越多越大，但最大不超过约 1.8 倍（点 10 次时）
        span = max(1, self.app.clicks_need)
        ratio = GROW_STEP * self.grow * (GROW_MAX / float(span))
        self.target = base * (1 + ratio)

    # ---------- 动作 ----------
    def _dbg(self, text):
        self.app.dbg("pet %s: %s" % (self.hwnd, text))

    def play_own_laugh(self, from_frame=0):
        """每只奶龙放自己的那一遍笑声（各开一路，互不打断）；
        软件混音不可用时自动退回系统单通道播放。"""
        if not self.app.sound_on or not self.app.wav:
            return
        if _play_wav_stream(self.app.wav, from_frame):
            self._dbg("sound: mixer")
            return
        # 混音这条路不通（设备被抢/没有 sounddevice）→ 系统通道兜底
        self._dbg("sound: fallback")
        _play_fallback(self.app.wav)

    def stop_own_laugh(self):
        pass

    def start_laugh(self, sync_t0=None, play_sound=True, offset=None):
        if self.dying or not self.hwnd:
            return
        span = self.sp.laugh_hi - self.sp.laugh_lo
        self.mode = "laugh"
        self.idle_mix = None
        self.walk_dir = 0           # 笑的时候原地站好
        self.bob = 0
        self.wob = 0.0              # 肚皮弹到一半被点：先回正
        self.wob_t0 = 0.0
        if offset is not None:
            # 从这一轮笑的第 offset 帧开始（新生奶龙接的是另一段笑）。
            # offset 是「笑段帧序」，换算成时间再回推起点。
            self.mode_t0 = time.time() - offset * LAUGH_SEC / float(max(1, span))
            self.idx = min(self.sp.laugh_hi - 1, self.sp.laugh_lo + offset)
        elif sync_t0 is None:
            self.mode_t0 = time.time()
            self.idx = self.sp.laugh_lo
        else:
            # 接上别人正在进行的这一段笑（同一时刻结束）
            self.mode_t0 = sync_t0
            prog = (time.time() - sync_t0) / float(LAUGH_SEC)
            self.idx = min(self.sp.laugh_hi - 1,
                           self.sp.laugh_lo + int(max(0.0, prog) * span))
        self.render(self.idx)
        if play_sound:
            # 从当前对应的笑点开始放，声音和动作始终是一套
            self.play_own_laugh(self.idx - self.sp.laugh_lo)

    def on_click(self):
        if self.dying or not self.hwnd:
            return
        need = self.app.clicks_need
        self.grow = min(need, self.grow + 1)
        # 点得越多越大，但最大不超过约 1.8 倍（点 10 次时）
        self.target = self.app.base_scale * (
            1 + GROW_STEP * self.grow * (GROW_MAX / float(need)))
        # 正在笑的时候点击不打断：动画和笑声都让它笑完这一段
        if self.mode == "laugh":
            self._dbg("click during laugh -> keep laughing")
        else:
            self.start_laugh()
        self._dbg("click -> grow %d/%d" % (self.grow, need))
        if self.grow >= need:
            self.app.split(self)

    def start_absorb(self, keep, dur=None, curve=None):
        """回收动画：被留下那只收回去 —— 先轻轻鼓一下，再一边缩小一边飞向它。

        keep:  要飞向的那只奶龙（最后留下的本体）
        dur:   动画时长；同一批回收会传入同一个值，保证同时到达
        curve: 弧线方向；同一批也会统一，看起来才像「一起被吸走」
        """
        if self.dying or not self.hwnd:
            return
        self.dying = True
        if dur is None:
            dur = random.uniform(0.42, 0.58)
        if curve is None:
            curve = random.uniform(-0.35, 0.35)
        # 起点：以脚底中心为锚（飞起来像被吸走，而不是从头顶滑走）
        self.absorb = dict(
            keep=keep,
            t0=time.time(),
            dur=dur,
            x0=self.x, y0=self.y,
            w0=self.w, h0=self.h,
            s0=self.scale,
            curve=curve,
        )
        self._dbg("absorb -> %s" % (keep.hwnd if keep else None))

    def _tick_absorb(self, now):
        """推进回收动画；结束返回 True（并自己销毁）"""
        a = self.absorb
        keep = a["keep"]
        # 目标跟着留下那只走（它也可能在被拖动）
        if keep is not None and keep.hwnd:
            tx = keep.x + keep.w / 2.0
            ty = keep.y + keep.h / 2.0
        else:
            tx = a["x0"] + a["w0"] / 2.0
            ty = a["y0"] + a["h0"] / 2.0

        p = (now - a["t0"]) / a["dur"]
        if p >= 1.0:
            self.destroy()
            return True

        # 缓动：先轻微回弹（像被吸住），再加速被吸走
        e = p * p * (3.0 - 2.0 * p)            # smoothstep
        # 起点（脚底中心）
        sx = a["x0"] + a["w0"] / 2.0
        sy = a["y0"] + a["h0"]
        # 弧线：中途往侧向鼓出去一点，看起来是被"卷"走的
        lift = math.sin(p * math.pi) * a["curve"] * a["w0"] * 0.5
        nx = sx + (tx - sx) * e - lift
        ny = sy + (ty - sy) * e
        # 尺寸：从原样收到很小（0.28 倍），越接近目标越小
        shrink = 1.0 - 0.72 * e
        nw = max(1, int(round(a["w0"] * shrink)))
        nh = max(1, int(round(a["h0"] * shrink)))
        self.w, self.h = nw, nh
        self.scale = a["s0"] * shrink
        # 以脚底中心对齐
        self.x = int(round(nx - nw / 2.0))
        self.y = int(round(ny - nh))
        # 淡出晚一点：前段保持清晰，最后 30% 才化掉
        self.fade = 1.0 if p < 0.68 else max(0.0, (1.0 - p) / 0.32)
        self.render(self.idx)
        return False

    def _tick(self):
        self._in_tick = True
        self._pending_render = None
        try:
            self._advance_tick()
        finally:
            self._in_tick = False
        if self._pending_render is not None and self.hwnd:
            self.render(self._pending_render)

    def _advance_tick(self):
        now = time.time()
        dt = min(0.1, max(0.001, now - getattr(self, "_last_tick", now - 0.03)))
        self._last_tick = now

        # 回收动画（被留下那只吸走）
        if self.absorb is not None:
            if self._tick_absorb(now):
                return
            return

        # 消失淡出（先淡出再缩放，避免中途改尺寸影响画面）
        if self.dying:
            self.fade -= 4.0 * dt
            if self.fade <= 0.02:
                self.destroy()
                return
            self.render(self.idx)
            return

        # 尺寸渐变（一点点变大 / 分裂后弹出）
        if abs(self.target - self.scale) > 0.003:
            d = self.target - self.scale
            step = d * (1.0 - math.exp(-dt / 0.078))
            self._apply_scale(self.scale + step)

        if self.mode == "laugh":
            # 笑段只播 LAUGH_SEC 秒（= 笑声长度），按比例映射到素材的笑帧区间。
            # 原来是把 199 帧全播完（16.6 秒），声音早在第 2.6 秒就没了，
            # 后面十几秒是「哑着笑」，所以现在压缩到和声音一样长。
            span = self.sp.laugh_hi - self.sp.laugh_lo
            prog = (now - self.mode_t0) / float(LAUGH_SEC)
            if prog >= 1.0:
                # 声音结束 → 立刻回到原始待机状态
                self.mode = "idle"
                self.idx = self.sp.idle_lo
                self.mode_t0 = now
                self.idle_mix = None
                self.bob = 0
                # 笑完先站一小会儿，再继续散步
                self.next_walk = now + random.uniform(1.5, 3.5)
                self.render(self.idx)
                self.release_parent()      # 我笑完了，本体可以算账了
                self.app.on_laugh_end(self)
                if self.dying:             # 可能刚被裁决退场
                    return
            else:
                i = self.sp.laugh_lo + int(prog * span)
                if i >= self.sp.laugh_hi:
                    i = self.sp.laugh_hi - 1
                if i != self.idx:
                    self.idx = i
                    self.render(i)
        else:
            phase = (now - self.mode_t0) * IDLE_FPS
            k = int(phase)
            play = self.sp.idle_play
            i = play[k % len(play)]
            mix = (play[(k + 1) % len(play)], int((phase - k) * 8))
            if i != self.idx or mix != getattr(self, "idle_mix", None):
                self.idx = i
                self.idle_mix = mix
                self.render(i)
            self._tick_walk(now)
            self._tick_eyes(now)
            self._tick_belly(now)
            if self.app.auto_laugh and now > self.next_auto:
                self.next_auto = now + random.uniform(14.0, 22.0)
                self.start_laugh()

    # ---------- 待机散步 ----------
    def _bottom_y(self):
        """自己所在显示器的工作区底边（自动扣掉任务栏）。
        拿不到显示器信息就退回主屏高度（只会站到任务栏上，不影响运行）。"""
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        if user32.GetMonitorInfoW(
                user32.MonitorFromWindow(self.hwnd, MONITOR_DEFAULTTONEAREST),
                ctypes.byref(mi)) and mi.rcWork.bottom > 0:
            return mi.rcWork.bottom
        return user32.GetSystemMetrics(1)

    def _tick_walk(self, now):
        """待机散步：沿屏幕底部（任务栏上方）左右走，走一段歇一段。
        被拖到别处时，歇一会儿后自己走回底部再接着溜达。
        素材里没有走路的帧，用待机动画 + 小碎步颠簸来表现。"""
        dt = min(0.12, max(0.0, now - self.walk_t))
        self.walk_t = now
        if self.drag or self.dying or self.absorb is not None:
            self.walk_dir = 0
            self.bob = 0
            return
        bottom_y = self._bottom_y() - self.h
        if self.walk_dir == 0:
            self.bob = 0
            if now < self.next_walk:
                return
            if self.y < bottom_y:
                # 不在底部：先走回底部（较快的下降，像跳下去）
                self.y = min(bottom_y, self.y + int(WALK_FALL * dt) + 1)
                self.render(self.idx)
                return
            # 到底部了，出发：随机方向
            self.walk_dir = random.choice((-1, 1))
            self.face = self.walk_dir
            self.walk_until = now + random.uniform(*WALK_BURST)
            self.walk_acc = 0.0
            return
        # ---- 正在走 ----
        if now >= self.walk_until:
            self.walk_dir = 0
            self.bob = 0
            self.next_walk = now + random.uniform(*WALK_REST)
            self.render(self.idx)
            return
        self.walk_acc += WALK_SPEED * dt
        move = int(self.walk_acc)
        if move:
            self.walk_acc -= move
            self.x += move * self.walk_dir
            # 撞到屏幕边缘就掉头
            if self.x < 2:
                self.x = 2
                self.walk_dir = 1
                self.face = 1
            elif self.x + self.w > self.app.sw - 2:
                self.x = self.app.sw - 2 - self.w
                self.walk_dir = -1
                self.face = -1
        # 贴着底部走 + 迈步颠簸（两脚剪刀交叉过中线时身体最高）
        self.y = bottom_y
        self.bob = -int(round(math.cos(now * WALK_BOB_HZ * 2 * math.pi) ** 2
                              * self.h * WALK_BOB))
        self.render(self.idx)

    # ---------- 眼神追踪 ----------
    def _draw_eyes(self, source=None, size=None, buffer=None):
        """把瞳孔画到 eye_off 指的方向上：先从虹膜环取色抹掉原瞳孔
        （同角度采样，保留明暗渐变），再在偏移位置画新瞳孔（边缘抗锯齿）。
        眨眼帧（扫描不到瞳孔）直接跳过。"""
        sp = self.sp
        if not (sp.idle_lo <= self.idx <= sp.idle_hi):
            return
        info = sp.eyes[self.idx - sp.idle_lo]
        if info is None:
            return
        pcx, pcy = info
        mix = getattr(self, "idle_mix", None)
        if mix and mix[1]:
            next_eye = sp.eyes[mix[0] - sp.idle_lo]
            if next_eye is not None:
                weight = mix[1] / 8.0
                pcx += (next_eye[0] - pcx) * weight
                pcy += (next_eye[1] - pcy) * weight
        width, height = size or (self.w, self.h)
        sc = width / float(sp.w)
        scy = height / float(sp.h)
        # 镜像时 sprite x 坐标左右翻折
        fx = (pcx + 0.5) * sc - 0.5
        if self.face < 0:
            fx = width - 1 - fx
        fy = (pcy + 0.5) * scy - 0.5
        ox = self.eye_off[0] * sc
        oy = self.eye_off[1] * scy
        r_e = EYE_R_ERASE * sc                 # 抹除半径
        r_p = EYE_R_PUPIL * sc                 # 新瞳孔半径
        br, bg, bb = sp.pupil_col
        buf = self.dst_buf if buffer is None else buffer
        stride = self.max_w * 4 if buffer is None else width * 4
        if source is None:
            source = self._scale_frame(self.idx, self.face < 0, (width, height))
        source_stride = width * 4
        x_lo = max(1, int(fx - r_e - 2))
        x_hi = min(width - 2, int(fx + r_e + 3))
        y_lo = max(1, int(fy - r_e - 2))
        y_hi = min(height - 2, int(fy + r_e + 3))
        for y in range(y_lo, y_hi):
            row0 = y * stride
            dy = y - fy
            for x in range(x_lo, x_hi):
                j = row0 + x * 4
                dx = x - fx
                d = math.hypot(dx, dy)
                if d <= r_e:
                    # 抹掉原瞳孔：同角度从外侧虹膜取色填回。
                    # 采样半径 = 当前半径 + 0.9（延续径向渐变），
                    # 靠近圆心时钳到 5.5，避免采到还没抹掉的深色瞳孔。
                    sr = d + 0.9 * sc
                    if sr < 5.5 * sc:
                        sr = 5.5 * sc
                    a = math.atan2(dy, dx)
                    sx = max(0, min(width - 1,
                                    int(round(fx + math.cos(a) * sr))))
                    sy = max(0, min(height - 1,
                                    int(round(fy + math.sin(a) * sr))))
                    k = sy * source_stride + sx * 4
                    # Sample the untouched frame, never an earlier painted pixel.
                    edge = min(1.0, max(0.0, r_e - d))
                    for channel in range(3):
                        buf[j + channel] = int(round(
                            buf[j + channel] * (1 - edge)
                            + source[k + channel] * edge))
                d_p = math.hypot(x - fx - ox, y - fy - oy)
                if d_p <= r_p:
                    # 画新瞳孔：边缘 1px 渐变抗锯齿
                    t = r_p - d_p
                    if t > 1.0:
                        t = 1.0
                    buf[j] = int(buf[j] * (1 - t) + bb * t)
                    buf[j + 1] = int(buf[j + 1] * (1 - t) + bg * t)
                    buf[j + 2] = int(buf[j + 2] * (1 - t) + br * t)

    def _tick_eyes(self, now):
        """待机时眼睛跟着鼠标看：瞳孔朝鼠标方向偏移（限幅 + 平滑），
        偏移变化超过 0.25px 才重画（站着不动时几乎零开销）。"""
        if not (self.sp.idle_lo <= self.idx <= self.sp.idle_hi):
            return
        if self.sp.eyes[self.idx - self.sp.idle_lo] is None:
            return                              # 眨眼帧不用跟
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        sp = self.sp
        info = sp.eyes[self.idx - sp.idle_lo]
        sc = self.w / float(sp.w)
        exs = ((sp.w - 1 - info[0]) if self.face < 0 else info[0]) * sc
        eys = info[1] * sc
        dx = pt.x - (self.x + exs)
        dy = pt.y - (self.y + eys + self.bob)
        d = math.hypot(dx, dy)
        if d < 10.0:
            tx = ty = 0.0                       # 鼠标就在脸上：看正前方
        else:
            tx = EYE_TRACK * dx / d
            ty = EYE_TRACK_Y * dy / d
        # 平滑追随，避免瞳孔跳来跳去
        dt = min(0.1, max(0.001, now - getattr(self, "_eye_t", now - 0.03)))
        self._eye_t = now
        follow = 1.0 - (1.0 - EYE_FOLLOW) ** (dt / 0.03)
        self.eye_off[0] += (tx - self.eye_off[0]) * follow
        self.eye_off[1] += (ty - self.eye_off[1]) * follow
        mark = (int(self.eye_off[0] * 8), int(self.eye_off[1] * 8))
        if mark != self.eye_mark:
            self.eye_mark = mark
            self.render(self.idx)

    # ---------- 摸肚子 ----------
    def _sfx(self, name=None):
        """放本机音效。总声音开关、戳肚子音效开关都开着才响
        （右键菜单里两项都能随时切，关掉立即生效）。"""
        if not self.app.sound_on:
            return
        if not getattr(self.app, "boing_on", True):
            return
        if _play_sfx(name):
            self._dbg("sfx: boing")

    def _tick_belly(self, now):
        """鼠标移到肚子上时弹一下：命中判定用「贴图实际轮廓」——
        先换算回 sprite 坐标取该像素的 alpha，透明处不算（不会摸到空气）。
        只在鼠标「刚进入」肚子时触发一次，配冷却防止来回蹭连弹。"""
        if self.drag:
            self.belly_in = False
            return
        sp = self.sp
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        lx = pt.x - self.x
        ly = pt.y - (self.y + self.bob)                 # 用实际画出来的位置
        hit = False
        if 0 <= lx < self.w and 0 <= ly < self.h:
            sx = int(lx * sp.w / float(self.w))
            sy = int(ly * sp.h / float(self.h))
            if self.face < 0:                           # 镜像时 x 翻折
                sx = sp.w - 1 - sx
            if sp.h * BELLY_TOP <= sy <= sp.h * BELLY_BOT:
                hit = sp.frames[self.idx][(sy * sp.w + sx) * 4 + 3] > 40
        if hit and not self.belly_in and now >= self.bounce_next:
            self.wob_t0 = now
            self.bounce_next = now + BOUNCE_COOL
            self._sfx()             # 同时「啵」一声
        self.belly_in = hit
        # 肚皮弹动：阻尼振荡（先往上鼓，再回弹，越来越小）
        if self.wob_t0:
            t = now - self.wob_t0
            if t >= WOB_DUR:
                self.wob_t0 = 0.0
                self.wob = 0.0
            else:
                self.wob = -WOB_H * self.h * math.exp(-WOB_DAMP * t) \
                    * math.sin(2 * math.pi * WOB_HZ * t)
            self.render(self.idx)

    # ---------- 消息 ----------
    def _proc(self, hwnd, msg, wp, lp):
        if msg == WM_TIMER:
            self._tick()
            # 兜底：万一"最后一只笑完"时场上只剩它自己、错过了 on_laugh_end，
            # 这里定期补一次收敛检查（很便宜，单只时直接返回）
            now = time.time()
            if now - self.app.last_settle > 0.8:
                self.app.last_settle = now
                self.app.settle()
            return 0
        if msg == WM_LBUTTONDOWN:
            self._dbg("mouse down")
            pt = POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            self.drag = dict(mx=pt.x, my=pt.y, x=self.x, y=self.y, moved=0)
            user32.SetCapture(hwnd)
            return 0
        if msg == WM_MOUSEMOVE and self.drag:
            pt = POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            dx = pt.x - self.drag["mx"]
            dy = pt.y - self.drag["my"]
            self.drag["moved"] = max(self.drag["moved"], abs(dx) + abs(dy))
            self.x = self.drag["x"] + dx
            self.y = self.drag["y"] + dy
            self.render(self.idx)
            return 0
        if msg == WM_LBUTTONUP and self.drag:
            moved = self.drag["moved"]
            user32.ReleaseCapture()
            self.drag = None
            # 放下后先站一会儿（欣赏一下自己被摆的位置），再走回底部散步
            self.next_walk = time.time() + random.uniform(3.0, 6.0)
            if moved < 6:
                self.on_click()
            else:
                # 拖完就落盘：万一紧接着关了程序，位置也是新的
                self.app.note_pos(self.x, self.y, self.face, force=True)
            return 0
        if msg == WM_RBUTTONUP:
            self._menu()
            return 0
        if msg == WM_CLOSE:
            self.destroy()
            return 0
        return user32.DefWindowProcW(hwnd, msg, wp, lp)

    def _menu(self):
        m = user32.CreatePopupMenu()
        user32.AppendMenuW(m, 0, MENU_LAUGH, "笑一个 ヽ(≧□≦)ノ")

        sub = user32.CreatePopupMenu()
        cur = int(round(self.app.base_scale * 100))
        user32.AppendMenuW(sub, 0x1, 0, "当前：%d%%" % cur)   # MF_GRAYED
        user32.AppendMenuW(sub, 0, MENU_BIGGER, "放大一点  +10%")
        user32.AppendMenuW(sub, 0, MENU_SMALLER, "缩小一点  -10%")
        user32.AppendMenuW(sub, 0x800, 0, None)
        for i, p in enumerate(PRESETS):
            flag = 0x8 if abs(p - cur) < 3 else 0
            user32.AppendMenuW(sub, flag, MENU_PRESET_BASE + i, "%d%%" % p)
        user32.AppendMenuW(m, 0x10, sub, "整体大小")

        sub2 = user32.CreatePopupMenu()
        need = self.app.clicks_need
        user32.AppendMenuW(sub2, 0x1, 0, "当前：%d 次" % need)   # MF_GRAYED
        for n in range(CLICKS_MIN, CLICKS_MAX + 1):
            user32.AppendMenuW(sub2, 0x8 if n == need else 0,
                               MENU_CLICKS_BASE + n, "%d 次" % n)
        user32.AppendMenuW(m, 0x10, sub2, "点击次数")

        sub3 = user32.CreatePopupMenu()
        each = getattr(self.app, "born_each", BORN_EACH_DEFAULT)
        user32.AppendMenuW(sub3, 0x1, 0, "当前：%d 只" % each)   # MF_GRAYED
        for n in range(BORN_EACH_MIN, BORN_EACH_MAX + 1):
            user32.AppendMenuW(sub3, 0x8 if n == each else 0,
                               MENU_BORN_BASE + n, "%d 只" % n)
        user32.AppendMenuW(m, 0x10, sub3, "一次生几只")

        user32.AppendMenuW(m, 0x8 if self.app.auto_laugh else 0, MENU_AUTO,
                           "自己偷偷笑")
        user32.AppendMenuW(m, 0x8 if self.app.sound_on else 0, MENU_SOUND,
                           "魔性笑声")
        user32.AppendMenuW(m, 0x8 if getattr(self.app, "boing_on", True) else 0,
                           MENU_BOING, "戳肚子「啵」一声")
        user32.AppendMenuW(m, 0x800, 0, None)
        user32.AppendMenuW(m, 0, MENU_QUIT, "先躲起来（退出）")
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        user32.SetForegroundWindow(self.hwnd)
        cmd = user32.TrackPopupMenu(m, TPM_RETURNCMD | TPM_RIGHTBUTTON,
                                    pt.x, pt.y, 0, self.hwnd, None)
        user32.DestroyMenu(m)
        app = self.app
        if cmd == MENU_LAUGH:
            self.start_laugh()
        elif cmd == MENU_BIGGER:
            app.set_base_scale(app.base_scale + 0.1)
        elif cmd == MENU_SMALLER:
            app.set_base_scale(app.base_scale - 0.1)
        elif MENU_PRESET_BASE <= cmd < MENU_PRESET_BASE + len(PRESETS):
            app.set_base_scale(PRESETS[cmd - MENU_PRESET_BASE] / 100.0)
        elif MENU_CLICKS_BASE <= cmd <= MENU_CLICKS_BASE + CLICKS_MAX:
            app.set_clicks_need(cmd - MENU_CLICKS_BASE)
        elif MENU_BORN_BASE < cmd <= MENU_BORN_BASE + BORN_EACH_MAX:
            app.set_born_each(cmd - MENU_BORN_BASE)
        elif cmd == MENU_AUTO:
            app.auto_laugh = not app.auto_laugh
            app._save_cfg()
        elif cmd == MENU_SOUND:
            app.sound_on = not app.sound_on
            app._save_cfg()
        elif cmd == MENU_BOING:
            app.boing_on = not getattr(app, "boing_on", True)
            app._save_cfg()
            if app.boing_on:
                self._sfx()         # 打开时立刻试听一声，确认有效
        elif cmd == MENU_QUIT:
            user32.PostQuitMessage(0)


class App(object):
    def __init__(self):
        global LAUGH_SPAN, LAUGH_SEC
        here = os.path.dirname(os.path.abspath(__file__))
        # 打包成 exe 后：贴图/音效被解到临时目录（只读），
        # 而 settings.json 要写在 exe 旁边，否则每次重启都丢配置。
        if getattr(sys, "frozen", False):
            res_dir = getattr(sys, "_MEIPASS", os.path.dirname(
                os.path.abspath(sys.executable)))
            cfg_dir = os.path.dirname(os.path.abspath(sys.executable))
        else:
            res_dir = cfg_dir = here
        self.here = res_dir
        self.cfg_dir = cfg_dir          # 可写目录（日志/配置都放这）
        self.sprite = Sprite(res_dir)
        LAUGH_SPAN = max(1, self.sprite.laugh_hi - self.sprite.laugh_lo)
        self.wav = os.path.join(res_dir, "laugh.wav")
        # 笑声多长，笑段动画就多长（掐头静音后按实际长度算）
        try:
            _raw, _sr, _ch, _sw = _load_wav_bytes(self.wav)
            if _raw is not None and _sr:
                LAUGH_SEC = len(_raw) / float(_sr * _ch * _sw)
        except Exception:
            pass
        self.cfg_path = os.path.join(cfg_dir, "settings.json")
        self.debug = bool(os.environ.get("NAILONG_DEBUG"))

        cfg = self._load_json()
        self.base_scale = self._load_scale()
        self.clicks_need = self._load_clicks()
        self.born_each = self._load_born_each()     # 一次生几只（1~5）
        self.auto_laugh = bool(cfg.get("auto_laugh", False))
        self.sound_on = True if cfg.get("sound", True) else False
        # 戳肚子音效单独一个开关（想静音戳但留笑声时用）
        self.boing_on = True if cfg.get("boing", True) else False
        # 上次位置：渲染时顺手记下，节流落盘；退出前再补一次精确值
        self._last_pos = None
        self._pos_next = 0.0
        self.last_settle = 0.0      # 上次收敛检查的时刻（定时器兜底用）
        self.hdc_screen = user32.GetDC(0)

        self._register_class()
        self.warm_up_audio()

        # 初始一只：回到上次关闭时的位置和朝向；没有记录才放到右下角
        base_w = int(round(self.sprite.w * self.base_scale))
        base_h = int(round(self.sprite.h * self.base_scale))
        sw = user32.GetSystemMetrics(0)
        sh = user32.GetSystemMetrics(1)
        self.sw = sw
        px, py, pf = self._load_pos()
        if px is None:
            pet0 = Pet(self, sw - base_w - 70, sh - base_h - 110)
            pet0.y = pet0._bottom_y() - pet0.h
        else:
            pet0 = Pet(self, px, py)
            pet0.face = pf          # 上次朝哪边，这次还朝哪边
            self.dbg("restore pos %d,%d face=%d" % (px, py, pf))
        pet0.render(pet0.idx)
        self.pets = [pet0]

        if "--laugh" in sys.argv:
            import threading
            threading.Timer(1.2, self.pets[0].start_laugh).start()
        if "--scale" in sys.argv:
            try:
                self.set_base_scale(float(sys.argv[sys.argv.index("--scale") + 1]))
            except Exception:
                pass

    # ---------- 音频预热 ----------
    def warm_up_audio(self):
        """后台把 waveOut 声部先开好。

        开一个 waveOut 句柄要 100ms 上下，提前在后台开完，
        第一次点击就不用等 —— 否则听着就像「点了之后才响」。
        """
        if _winmm is None:
            return

        def run():
            try:
                pool, _raw = _get_pool(self.wav)
                self.dbg("audio warm-up %s (%d 声部)"
                         % ("done" if pool else "fail",
                            len(pool["slots"]) if pool else 0))
                # 顺便把「啵」合成好、声部开好：第一次戳肚子才不延迟
                self.dbg("sfx warm-up %s"
                         % ("done" if _warm_sfx() else "fail"))
            except Exception as e:
                self.dbg("audio warm-up fail: %r" % (e,))

        threading.Thread(target=run, name="audio-warmup", daemon=True).start()

    # ---------- 配置 ----------
    def _load_json(self):
        try:
            with open(self.cfg_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_cfg(self):
        d = {"scale": round(self.base_scale, 3),
             "clicks": self.clicks_need,
             "born_each": getattr(self, "born_each", BORN_EACH_DEFAULT),
             "sound": bool(self.sound_on),
             "boing": bool(getattr(self, "boing_on", True)),
             "auto_laugh": bool(getattr(self, "auto_laugh", False))}
        pos = getattr(self, "_last_pos", None)
        if pos:
            d["x"], d["y"], d["face"] = int(pos[0]), int(pos[1]), int(pos[2])
        try:
            # 先写临时文件再原子替换：写到一半断电也不会把配置写坏
            tmp = self.cfg_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(d, f)
            os.replace(tmp, self.cfg_path)
        except Exception:
            pass

    def note_pos(self, x, y, face, force=False):
        """记下本体的位置+朝向。最多每 POS_SAVE_EVERY 秒落一次盘，
        免得散步时每帧都去写文件；退出和拖放结束会强制写。"""
        self._last_pos = (int(x), int(y), int(face))
        now = time.time()
        if force or now >= self._pos_next:
            self._pos_next = now + POS_SAVE_EVERY
            self._save_cfg()

    def save_state(self):
        """退出前把本体最新位置补记一次，保证下次打开回到原处"""
        for p in list(PETS.values()):
            if p.parent is None and p.hwnd and not p.dying:
                self._last_pos = (int(p.x), int(p.y), int(p.face))
                break
        self._save_cfg()

    def _load_pos(self):
        """上次关闭时的位置与朝向；没记录、或坐标已不在任何显示器上 → None"""
        d = self._load_json()
        try:
            x, y = int(d["x"]), int(d["y"])
        except Exception:
            return None, None, 0
        try:
            face = -1 if int(d.get("face", 1)) < 0 else 1
        except Exception:
            face = 1
        # 换了显示器/改了分辨率后，旧坐标可能落到屏幕外：当作没记录
        if not user32.MonitorFromPoint(POINT(x + 20, y + 20), 0):
            return None, None, 0
        return x, y, face

    def _load_scale(self):
        s = float(self._load_json().get("scale", 1.0))
        return max(SCALE_MIN, min(SCALE_MAX, s))

    def _load_clicks(self):
        try:
            n = int(self._load_json().get("clicks", GROW_MAX))
        except Exception:
            n = GROW_MAX
        return max(CLICKS_MIN, min(CLICKS_MAX, n))

    def set_clicks_need(self, n):
        self.clicks_need = max(CLICKS_MIN, min(CLICKS_MAX, int(n)))
        # 已经点到一半的，按新目标重新对齐（超了就立刻触发不了，等下次点击）
        for pet in PETS.values():
            pet.grow = min(pet.grow, self.clicks_need)
        self._save_cfg()

    def _load_born_each(self):
        try:
            n = int(self._load_json().get("born_each", BORN_EACH_DEFAULT))
        except Exception:
            n = BORN_EACH_DEFAULT
        return max(BORN_EACH_MIN, min(BORN_EACH_MAX, n))

    def set_born_each(self, n):
        """一次生几只（1~5）：只影响下一轮生育，场上已经生出来的不动。"""
        self.born_each = max(BORN_EACH_MIN, min(BORN_EACH_MAX, int(n)))
        self._save_cfg()

    def _save_scale(self):
        self._save_cfg()

    def dbg(self, text):
        if not self.debug:
            return
        try:
            with open(os.path.join(self.cfg_dir, "debug.log"), "a",
                      encoding="utf-8") as f:
                f.write(time.strftime("[%H:%M:%S] ") + text + "\n")
        except Exception:
            pass

    # ---------- 窗口类 ----------
    def _register_class(self):
        global _WNDPROC_REF, _CLASS_REGISTERED
        if _CLASS_REGISTERED:
            return
        _WNDPROC_REF = WNDPROC(_dispatch)
        hinst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSW()
        wc.lpfnWndProc = ctypes.cast(_WNDPROC_REF, ctypes.c_void_p)
        wc.hInstance = hinst
        wc.hCursor = user32.LoadCursorW(None, ctypes.c_void_p(IDC_HAND))
        wc.lpszClassName = "NailongPetWnd"
        user32.RegisterClassW(ctypes.byref(wc))
        _CLASS_REGISTERED = True

    # ---------- 多只管理 ----------
    def pet_count(self):
        return sum(1 for p in PETS.values() if p.hwnd and not p.dying)

    def set_base_scale(self, s):
        self.base_scale = max(SCALE_MIN, min(SCALE_MAX, float(s)))
        for pet in list(PETS.values()):
            pet.refresh_base_scale(self.base_scale)
        self._save_scale()

    def split(self, pet):
        """点满后一次生出 N 只原始大小的新奶龙（N 可在右键菜单设 1~5）；
        本体缩回原始大小后可以继续生"""
        if pet.dying or not pet.hwnd:
            return
        base = self.base_scale
        nw = int(round(self.sprite.w * base))
        nh = int(round(self.sprite.h * base))
        self.dbg("spawn from %d,%d" % (pet.x, pet.y))
        # 以本体所在显示器的工作区为界（多显示器时新奶龙不会跑到隔壁屏幕）
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        user32.GetMonitorInfoW(
            user32.MonitorFromWindow(pet.hwnd, MONITOR_DEFAULTTONEAREST),
            ctypes.byref(mi))
        vx, vy = mi.rcMonitor.left, mi.rcMonitor.top
        vw = mi.rcMonitor.right - vx
        vh = mi.rcMonitor.bottom - vy

        # 本体：缩回原始大小、计数归零 —— 可以继续点它接着生
        pet.grow = 0
        pet.target = base
        pet.litters += 1

        n = max(BORN_EACH_MIN, min(BORN_EACH_MAX, getattr(
            self, "born_each", BORN_EACH_DEFAULT)))
        self.dbg("一次生 %d 只" % n)
        for i in range(n):
            # 每只都单独选位置：_pick_spawn_spot 会读 PETS 里已有的同伴，
            # 所以后出生的会避开先生出来的，整窝自然撒开
            sx, sy = self._pick_spawn_spot(pet, nw, nh, vx, vy, vw, vh)
            kid = self._spawn_kid(sx, sy)
            kid.parent = pet        # 记一下谁生的，本体要等它们全笑完才敢退场
            self.claim_litter(pet)  # 每只各记一笔，笑完各自还一次
            # 新生的是「自己笑一遍」：不接本体的进度，从起手帧开始，
            # 比本体晚笑完。声音也各放各的。
            kid.start_laugh(play_sound=True)

    def _pick_spawn_spot(self, pet, nw, nh, vx, vy, vw, vh):
        """在本体周围随机找个位置出生 —— 方位随机、距离随机，允许重叠。

        唯一硬要求：**不能把本体整个遮住**（覆盖本体的面积不超过 55%）。
        其他位置随便叠，方位尽量撒开，每次出生都不一样。
        """
        MAX_COVER = 0.55                    # 最多遮住本体 55%，必须露出大半
        cx = pet.x + pet.w / 2.0            # 本体中心
        cy = pet.y + pet.h / 2.0
        span = math.hypot(nw, nh) * 0.5     # 半对角线，当距离尺度
        near = span * 0.75                  # 最近：可以就在本体身边叠着
        far = span * 1.85                   # 最远：约两个身位
        self_area = float(nw * nh)
        pet_area = float(pet.w * pet.h)
        others = [(q.x, q.y, q.w, q.h) for q in PETS.values()
                  if q.hwnd and q is not pet and not q.dying]

        def clamp(x, y):
            x = max(vx, min(vx + vw - nw, int(round(x))))
            y = max(vy, min(vy + vh - nh, int(round(y))))
            return x, y

        def inter(x, y, qx, qy, qw, qh):
            ox = min(x + nw, qx + qw) - max(x, qx)
            oy = min(y + nh, qy + qh) - max(y, qy)
            return ox * oy if (ox > 0 and oy > 0) else 0.0

        def cover(x, y):
            """遮住本体的比例（0=完全没遮）"""
            return inter(x, y, pet.x, pet.y, pet.w, pet.h) / pet_area

        def crowd(x, y):
            """跟其他奶龙的重叠比例（软约束，仅用来在合格候选里挑）"""
            other = [(qx, qy, qw, qh) for qx, qy, qw, qh in others]
            tot = sum(inter(x, y, *q) for q in other)
            return tot / self_area

        # 撒一圈候选点：角度均匀 + 抖动，距离随机
        base_a = random.uniform(0, 2 * math.pi)
        n_cand = 28
        ok_list = []                        # 没把本体遮太多的候选
        best = None                         # 兜底：遮得最少的
        for i in range(n_cand):
            a = base_a + 2 * math.pi * (i + random.uniform(-0.45, 0.45)) / n_cand
            r = near + (far - near) * random.random()
            x, y = clamp(cx + math.cos(a) * r - nw / 2.0,
                         cy + math.sin(a) * r - nh / 2.0)
            cv = cover(x, y)
            if cv <= MAX_COVER:
                ok_list.append((crowd(x, y), x, y))
            if best is None or cv < best[0]:
                best = (cv, x, y)

        if ok_list:
            # 合格位置可能很多：在同档"不太挤"的里面随机挑，保证每次不一样
            ok_list.sort(key=lambda t: t[0])
            pool = ok_list[:max(3, len(ok_list) // 2)]
            _c, x, y = random.choice(pool)
        else:
            # 极端情况（本体贴边/被围住）：在周围矩形里找遮得最少的
            x0 = max(vx, int(cx - span * 2.0))
            x1 = min(vx + vw - nw, int(cx + span * 2.0 - nw))
            y0 = max(vy, int(cy - span * 2.0))
            y1 = min(vy + vh - nh, int(cy + span * 2.0 - nh))
            cv0, x, y = best
            if x1 > x0 and y1 > y0:
                for _ in range(200):
                    tx = random.randint(x0, x1)
                    ty = random.randint(y0, y1)
                    cv = cover(tx, ty)
                    if cv < cv0:
                        cv0, x, y = cv, tx, ty
                    if cv <= MAX_COVER:
                        break

        self.dbg("spawn (%d,%d) 遮住本体 %.0f%% 与同伴重叠 %.0f%%"
                 % (x, y, cover(x, y) * 100, crowd(x, y) * 100))
        return x, y

    def _spawn_kid(self, x, y):
        """真正建一只新奶龙（抽出来方便自测时替换）"""
        return Pet(self, x, y, grow=0, pop=True)

    def _alive(self):
        """场上还在的（回收动画中的不算，它们已经在退场了）"""
        return [p for p in PETS.values()
                if p.hwnd and not p.dying and p.absorb is None]

    def on_laugh_end(self, pet):
        """一只奶龙笑完了，来结算一次「场上该剩几只」。

        本体和娃的笑是错开的：可能娃先笑完（本体还在笑），也可能反过来。
        所以谁笑完都来结算一次，但只有「最后笑完的那只」才真正动手 ——
        此时全场都笑完，这一轮才算有结果，不会漏裁决、也不会误杀。
        """
        alive = self._alive()
        if len(alive) <= 1:
            return                          # 就它一只，笑完继续当桌宠
        self.settle(alive, trigger=pet.hwnd)

    def settle(self, alive=None, trigger="tick"):
        """把场上收成一只：只要没有在笑的、没有人还带着没笑完的娃，就动手。

        on_laugh_end 会调它，定时器也会兜底调一次 —— 因为"最后一只笑完"那一刻
        场上可能只剩它自己，on_laugh_end 会提前 return，收敛就永远等不到触发。
        """
        if alive is None:
            alive = self._alive()
        if len(alive) <= 1:
            return
        if any(q.mode == "laugh" for q in alive):
            return                          # 还有人在笑，等它笑完
        if any(q.awaiting > 0 for q in alive):
            return                          # 还有奶龙带着没笑完的娃
        # 优先留「生过娃的」那只 —— 它是下一轮的种子，留着才能继续点着生
        owners = [q for q in alive if q.litters > 0]
        keep = owners[0] if owners else alive[0]
        victims = [q for q in alive if q is not keep]
        # 同时回收：统一时长和弧线方向，所有奶龙在同一帧出发、同一帧抵达，
        # 看起来是"整群一起被吸回去"，而不是排队一只只走。
        dur = random.uniform(0.46, 0.56)
        curve = random.uniform(-0.22, 0.22)
        for q in victims:
            self.dbg("收敛(由 %s 触发): %s(litters=%d) 被 %s 回收"
                     % (trigger, q.hwnd, q.litters, keep.hwnd))
            q.release_parent()
            q.start_absorb(keep, dur=dur, curve=curve)

    def claim_litter(self, pet):
        """本体准备生一只：登记一下，娃在场上期间本体不退场"""
        pet.awaiting += 1

    def on_pet_gone(self):
        if not any(p.hwnd for p in PETS.values()):
            self._exit_log("all pets gone -> quit (%d entries left)"
                           % len(PETS))
            user32.PostQuitMessage(0)

    def _exit_log(self, text):
        """把「程序为什么退出」记下来。这类问题事后完全无迹可寻，必须当场留痕。"""
        try:
            with open(os.path.join(self.cfg_dir, "exit.log"), "a",
                      encoding="utf-8") as f:
                f.write(time.strftime("[%H:%M:%S] ") + text + "\n")
        except Exception:
            pass

    # ---------- 主循环 ----------
    def run(self):
        msg = MSG()
        # GetMessageW 返回 -1 表示出错（继续取消息即可），0 才是 WM_QUIT。
        # 原来的 `> 0` 写法在遇到 -1 时会静默退出整个程序 —— 打包后偶发。
        while True:
            r = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if r == 0:                      # WM_QUIT：正常退出
                self.save_state()           # 退出前把位置和设置落盘
                break
            if r == -1:                     # 出错：记录并继续
                self._exit_log("GetMessage error %d, msg=%d"
                               % (ctypes.GetLastError(), msg.message))
                continue
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        _shutdown_audio()


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass
    # C 层崩溃（段错误）不会走 except，也不会留 error.log。
    # faulthandler 能在崩溃瞬间把 Python 调用栈写下来，是排查的唯一线索。
    try:
        import faulthandler
        if getattr(sys, "frozen", False):
            log_dir = os.path.dirname(os.path.abspath(sys.executable))
        else:
            log_dir = os.path.dirname(os.path.abspath(__file__))
        crash = open(os.path.join(log_dir, "crash.log"), "w")
        faulthandler.enable(crash)
    except Exception:
        pass
    App().run()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        if getattr(sys, "frozen", False):
            here = os.path.dirname(os.path.abspath(sys.executable))
        else:
            here = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(here, "error.log"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S\n"))
            f.write(traceback.format_exc())
            f.write("\n")
        raise
