from PIL import Image, ImageDraw
import os

w = h = 128
img = Image.new('RGBA', (w, h), (13,17,23,255))
d = ImageDraw.Draw(img)

# body rounded rectangle
r = 20
body_bbox = (10, 18, w-10, h-10)
d.rounded_rectangle(body_bbox, radius=r, fill=(26,32,44,255), outline=(74,85,104,255), width=4)

# antenna
d.rectangle((62,2,66,22), fill=(74,85,104,255))
d.ellipse((54, -2, 74, 18), fill=(0,255,204,255))

# ears
d.rounded_rectangle((8,52,26,98), radius=6, fill=(45,55,72,255))
d.rounded_rectangle((102,52,120,98), radius=6, fill=(45,55,72,255))

# screen
d.rounded_rectangle((28,46,100,82), radius=12, fill=(15,23,42,255), outline=(45,55,72,255), width=2)

# eyes (glow simulated)
d.ellipse((40,56,62,78), fill=(0,255,204,255))
d.ellipse((66,56,88,78), fill=(0,255,204,255))

# mouth bars
offx = 48
for i,wid in enumerate([6,6,6,6,6]):
    x = offx + i*12
    if i==1 or i==2 or i==3:
        height = 22
    else:
        height = 18
    d.rounded_rectangle((x,98,x+6,98+height), radius=2, fill=(74,85,104,255))

assets_dir = os.path.join(os.path.dirname(__file__), 'assets')
os.makedirs(assets_dir, exist_ok=True)
output_path = os.path.join(assets_dir, 'robot_logo.png')
img.save(output_path)
print('Wrote', output_path)
