"""生成安装器美化素材（水墨风）
1. installer.ico — 安装器图标 (256x256)
2. installer-sidebar.png — 侧边栏品牌图 (164x314, MUI2 规格)
3. installer-header.png — 头部图标 (150x57)
"""
from PIL import Image, ImageDraw, ImageFilter, ImageOps

ROOT = r'D:\english-multiple-choice-practice-machine'
OUT = ROOT + r'\electron\installer-assets'
import os
os.makedirs(OUT, exist_ok=True)

LOGO = Image.open(ROOT + r'\epm_app\assets\icons\brand-mark.png').convert('RGBA')
BG = Image.open(ROOT + r'\frontend\public\assets\backgrounds\ink-2-jiangnan.jpg').convert('RGB')

# 1. 安装器图标（ico：256/128/64/32/16 多尺寸）
icon = LOGO.resize((256, 256), Image.LANCZOS)
icon.save(OUT + r'\installer.ico', sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])
print('✅ installer.ico')

# 2. 侧边栏 164x314（水墨背景 + 压暗 + logo + 标语）
sidebar_bg = BG.crop((0, 0, 164, 314)).resize((164, 314), Image.LANCZOS)
# 水墨暗化 + 顶部渐变（让 logo 更突出）
overlay = Image.new('RGBA', (164, 314), (20, 30, 40, 120))
sidebar_bg = Image.alpha_composite(sidebar_bg.convert('RGBA'), overlay)
# 底部再加深（标语区域）
bottom = Image.new('RGBA', (164, 314), (10, 15, 20, 140))
sidebar_bg = Image.alpha_composite(sidebar_bg, bottom)
# 中间放 logo（180px 圆角风格，白底衬托）
logo_small = LOGO.resize((120, 120), Image.LANCZOS)
mask = logo_small.split()[3]
sidebar_bg.paste(logo_small, ((164-120)//2, 60), mask)
# 标语文字（用系统字体，居中）
d = ImageDraw.Draw(sidebar_bg)
try:
    from PIL import ImageFont
    font_title = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 22)
    font_sub = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 14)
except Exception:
    font_title = font_sub = ImageFont.load_default()
title = "AI 英语刷题机"
sub = "647 题 · 36 套 · 双网络更新"
d.text((164//2, 230), title, font=font_title, fill=(255, 255, 255, 255), anchor="mm")
d.text((164//2, 262), sub, font=font_sub, fill=(235, 240, 245, 255), anchor="mm")
sidebar_bg.convert('RGB').save(OUT + r'\installer-sidebar.bmp')
print('✅ installer-sidebar.bmp 164x314')

# 3. 头部图标 150x57（透明底 logo 缩小）
header = Image.new('RGBA', (150, 57), (0, 0, 0, 0))
logo_h = LOGO.resize((48, 48), Image.LANCZOS)
header.paste(logo_h, (6, 4), logo_h.split()[3])
header.convert('RGB').save(OUT + r'\installer-header.bmp')
print('✅ installer-header.bmp 150x57')

print('\n素材生成完成:', OUT)
