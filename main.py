import socket
import subprocess
import time
from collections import deque

import psutil
from PIL import Image, ImageDraw, ImageFont

from luma.core.interface.serial import spi
from luma.lcd.device import ili9486

# =========================
# Display
# =========================
serial = spi(port=0, device=0)
device = ili9486(serial, width=320, height=480, rotate=1)

W = device.width   # ?????? 480
H = device.height  # ?????? 320

# =========================
# Fonts
# =========================
try:
    FONT_BIG = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
    FONT_MED = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
    FONT_SM = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
    FONT_SM_BOLD = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 11)
    FONT_XS = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
    FONT_XS_BOLD = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 10)
except OSError:
    FONT_BIG = ImageFont.load_default()
    FONT_MED = ImageFont.load_default()
    FONT_SM = ImageFont.load_default()
    FONT_SM_BOLD = ImageFont.load_default()
    FONT_XS = ImageFont.load_default()
    FONT_XS_BOLD = ImageFont.load_default()

# =========================
# Colors
# =========================
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

# ????????? ??? ??????? ?????. ???? ?? ????? ??????? ??? ??? ??? ??????????,
# ??????? ??????? GREEN_BG ? RED_BG.
GREEN_BG = (255, 179, 179)  # light green
YELLOW_BG = (255, 245, 157)  # light yellow
RED_BG = (144, 238, 144)      # light red

# =========================
# History
# =========================
HIST_LEN = 180
cpu_hist = deque([0] * HIST_LEN, maxlen=HIST_LEN)
ram_hist = deque([0] * HIST_LEN, maxlen=HIST_LEN)
disk_hist = deque([0] * HIST_LEN, maxlen=HIST_LEN)
net_hist = deque([0] * HIST_LEN, maxlen=HIST_LEN)

prev_net = psutil.net_io_counters()
prev_time = time.time()

# =========================
# Helpers
# =========================
def get_cpu_temp():
    try:
        temps = psutil.sensors_temperatures()
        if "cpu_thermal" in temps and temps["cpu_thermal"]:
            return temps["cpu_thermal"][0].current
        for entries in temps.values():
            if entries:
                return entries[0].current
    except Exception:
        pass
    return None


def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "n/a"


def get_fqdn():
    try:
        return socket.getfqdn() or "n/a"
    except Exception:
        return "n/a"


def get_dns():
    servers = []
    try:
        with open("/etc/resolv.conf", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("nameserver"):
                    parts = line.split()
                    if len(parts) >= 2:
                        servers.append(parts[1])
        return ", ".join(servers[:2]) if servers else "n/a"
    except Exception:
        return "n/a"


def get_gateway():
    try:
        result = subprocess.run(
            ["ip", "route", "show", "default"],
            capture_output=True,
            text=True,
            check=False,
        )
        lines = result.stdout.strip().splitlines()
        if not lines:
            return "n/a"
        parts = lines[0].split()
        if "via" in parts:
            idx = parts.index("via")
            if idx + 1 < len(parts):
                return parts[idx + 1]
    except Exception:
        pass
    return "n/a"


def trim_text(draw, text, font, max_width):
    if draw.textlength(text, font=font) <= max_width:
        return text
    ell = "..."
    while text and draw.textlength(text + ell, font=font) > max_width:
        text = text[:-1]
    return text + ell if text else ell


def usage_color(value):
    v = float(value)
    if v < 50:
        return GREEN_BG
    elif v < 80:
        return YELLOW_BG
    else:
        return RED_BG


def rounded_rect(draw, box, radius=7, outline=WHITE, fill=None, width=1):
    draw.rounded_rectangle(box, radius=radius, outline=outline, fill=fill, width=width)


def format_gib(value_bytes):
    return f"{value_bytes / (1024 ** 3):.1f}G"


def format_rate(value_bps):
    if value_bps >= 1024 * 1024:
        return f"{value_bps / (1024 * 1024):.1f}M"
    if value_bps >= 1024:
        return f"{value_bps / 1024:.0f}K"
    return f"{value_bps:.0f}B"


def metric_card(draw, x, y, w, h, title, value_num, value_text):
    color = usage_color(value_num)
    rounded_rect(draw, (x, y, x + w, y + h), radius=6, fill=color, outline=color)
    draw.text((x + 6, y + 4), title, fill=BLACK, font=FONT_XS_BOLD)
    draw.text((x + 6, y + 18), value_text, fill=BLACK, font=FONT_BIG)


def sparkline(draw, x, y, w, h, data, title, value_num, value_text="", max_value=100.0):
    color = usage_color(value_num)

    rounded_rect(draw, (x, y, x + w, y + h), radius=6, outline=WHITE)
    draw.text((x + 6, y + 4), title, fill=WHITE, font=FONT_XS_BOLD)

    if value_text:
        tw = draw.textlength(value_text, font=FONT_XS)
        draw.text((x + w - tw - 6, y + 4), value_text, fill=WHITE, font=FONT_XS)

    gx = x + 6
    gy = y + 18
    gw = w - 12
    gh = h - 24

    left = gx + 1
    top = gy + 1
    right = gx + gw - 1
    bottom = gy + gh - 1

    draw.rectangle((left, top, right, bottom), outline=WHITE)

    if len(data) < 2:
        return

    inner_w = right - left
    inner_h = bottom - top
    if inner_w < 2 or inner_h < 2:
        return

    vals = list(data)[-(inner_w + 1):]
    n = len(vals)
    if n < 2:
        return

    points = []
    for i, v in enumerate(vals):
        px = left + round(i * inner_w / (n - 1))
        clamped = max(0.0, min(float(v), max_value))
        py = bottom - round(clamped * inner_h / max_value)
        points.append((px, py))

    fill_points = [(points[0][0], bottom)] + points + [(points[-1][0], bottom)]
    draw.polygon(fill_points, fill=color)
    draw.line(points, fill=WHITE, width=1)


# Prime CPU reading
psutil.cpu_percent(interval=None)

while True:
    now = time.time()

    cpu = float(psutil.cpu_percent(interval=None))
    vm = psutil.virtual_memory()
    disk_usage = psutil.disk_usage("/")
    ram = float(vm.percent)
    disk = float(disk_usage.percent)
    temp = get_cpu_temp()

    net = psutil.net_io_counters()
    dt = max(now - prev_time, 0.001)
    rx_bps = (net.bytes_recv - prev_net.bytes_recv) / dt
    tx_bps = (net.bytes_sent - prev_net.bytes_sent) / dt
    net_load = min(((rx_bps + tx_bps) / (8 * 1024 * 1024)) * 100, 100)

    cpu_hist.append(cpu)
    ram_hist.append(ram)
    disk_hist.append(disk)
    net_hist.append(net_load)

    prev_net = net
    prev_time = now

    fqdn = get_fqdn()
    ip = get_ip()
    dns = get_dns()
    gw = get_gateway()

    # =========================
    # Layout
    # =========================
    M = 8
    G = 8

    header_h = 22
    cards_h = 40
    info_h = 12
    bottom_h = 68

    free_h = H - (M + header_h + G + cards_h + G + info_h + G + bottom_h + G + M)
    graph_h = max(70, (free_h - G) // 2)

    card_w = (W - 2 * M - 2 * G) // 3
    graph_w = (W - 2 * M - G) // 2

    # =========================
    # Draw
    # =========================
    img = Image.new("RGB", (W, H), BLACK)
    draw = ImageDraw.Draw(img)

    # Header
    y = M
    draw.text((M, y), "System Monitor", fill=WHITE, font=FONT_MED)
    clock_text = time.strftime("%H:%M:%S")
    tw = draw.textlength(clock_text, font=FONT_MED)
    draw.text((W - M - tw, y), clock_text, fill=WHITE, font=FONT_MED)
    y += header_h
    draw.line((M, y, W - M, y), fill=WHITE, width=1)
    y += G

    # Top cards
    metric_card(draw, M, y, card_w, cards_h, "CPU", cpu, f"{cpu:3.0f}%")
    metric_card(draw, M + card_w + G, y, card_w, cards_h, "RAM", ram, f"{ram:3.0f}%")
    metric_card(draw, M + 2 * (card_w + G), y, card_w, cards_h, "DISK", disk, f"{disk:3.0f}%")
    y += cards_h + G

    # Small info line
    temp_text = f"TEMP {temp:4.1f}C" if temp is not None else "TEMP n/a"
    draw.text((M, y), temp_text, fill=WHITE, font=FONT_SM_BOLD)
    y += info_h + G

    # Graphs row 1
    sparkline(draw, M, y, graph_w, graph_h, cpu_hist, "CPU history", cpu, f"{cpu:3.0f}%")
    sparkline(
        draw,
        M + graph_w + G,
        y,
        graph_w,
        graph_h,
        ram_hist,
        "RAM history",
        ram,
        f"{ram:3.0f}% {format_gib(vm.used)}/{format_gib(vm.available)}",
    )
    y += graph_h + G

    # Graphs row 2
    sparkline(
        draw,
        M,
        y,
        graph_w,
        graph_h,
        disk_hist,
        "DISK history",
        disk,
        f"{disk:3.0f}% {format_gib(disk_usage.used)}/{format_gib(disk_usage.free)}",
    )
    sparkline(
        draw,
        M + graph_w + G,
        y,
        graph_w,
        graph_h,
        net_hist,
        "NET load",
        net_load,
        f"{format_rate(rx_bps)}/{format_rate(tx_bps)}",
    )
    y += graph_h + G

    # Bottom compact box
    rounded_rect(draw, (M, y, W - M, H - M), radius=6, outline=WHITE)
    text_x = M + 8
    text_w = W - 2 * M - 16

    line1 = f"IP  {trim_text(draw, ip, FONT_SM, 170)}   GW  {trim_text(draw, gw, FONT_SM, 180)}"
    line2 = f"DNS {trim_text(draw, dns, FONT_SM, text_w - 28)}  FQDN {trim_text(draw, fqdn, FONT_SM, text_w - 36)}"

    draw.text((text_x, y + 8), line1, fill=WHITE, font=FONT_SM)
    draw.text((text_x, y + 24), line2, fill=WHITE, font=FONT_SM)

    device.display(img)
    time.sleep(1)
