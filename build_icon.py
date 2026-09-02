"""生成 WeiboArchive 应用图标 (build/icon.ico)。"""
from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 256
OUT = Path("build") / "icon.ico"
OUT.parent.mkdir(parents=True, exist_ok=True)

img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# 圆角矩形底（微博红渐变）
red_top = (230, 22, 45)
red_bot = (180, 10, 30)
for y in range(SIZE):
    t = y / SIZE
    r = int(red_top[0] + (red_bot[0] - red_top[0]) * t)
    g = int(red_top[1] + (red_bot[1] - red_top[1]) * t)
    b = int(red_top[2] + (red_bot[2] - red_top[2]) * t)
    d.line([(0, y), (SIZE, y)], fill=(r, g, b, 255))
mask = Image.new("L", (SIZE, SIZE), 0)
md = ImageDraw.Draw(mask)
md.rounded_rectangle([8, 8, SIZE - 8, SIZE - 8], radius=56, fill=255)
img.putalpha(mask)

# 白色相机主体
cx, cy = SIZE // 2, SIZE // 2 - 10
body_w, body_h = 150, 108
d.rounded_rectangle(
    [cx - body_w // 2, cy - body_h // 2, cx + body_w // 2, cy + body_h // 2],
    radius=22, fill=(255, 255, 255, 255),
)
# 顶部凸起
d.rounded_rectangle(
    [cx - 34, cy - body_h // 2 - 26, cx + 34, cy - body_h // 2 + 10],
    radius=12, fill=(255, 255, 255, 255),
)
# 镜头外圈
d.ellipse([cx - 46, cy - 46, cx + 46, cy + 46], fill=(230, 22, 45, 255))
# 镜头内圈
d.ellipse([cx - 30, cy - 30, cx + 30, cy + 30], fill=(255, 255, 255, 255))
# 镜头中心
d.ellipse([cx - 16, cy - 16, cx + 16, cy + 16], fill=(230, 22, 45, 255))
# 指示灯
d.ellipse([cx + 52, cy - 40, cx + 66, cy - 26], fill=(255, 220, 80, 255))

# 多尺寸写入 ico
sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
img.save(OUT, format="ICO", sizes=sizes)
print("icon saved:", OUT, OUT.stat().st_size, "bytes")
