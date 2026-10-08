from PIL import Image
for f in ["picore_logo.png", "background1.png", "background2.png"]:
    Image.open(f).save(f)
