import os
from pathlib import Path
from PIL import Image, ImageDraw

ROOT_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT_DIR / "assets"
ASSETS_DIR.mkdir(exist_ok=True)

def create_discord_green_icon():
    size = 512
    # Create image with RGBA
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Discord Green color
    green = (35, 165, 90, 255) # Discord #23A55A (or #57F287)
    white = (255, 255, 255, 255)

    # Draw rounded rectangle / circle background
    margin = 16
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=110,
        fill=green
    )

    # Draw Discord Clyde Logo in white
    # Clyde logo proportions centered in 512x512
    # Clyde head coordinates scaled to 512x512
    # Base center: (256, 260)
    # Head outline polygon points
    clyde_points = [
        (135, 185), # top left horn
        (175, 220), # top left dent
        (256, 205), # top center
        (337, 220), # top right dent
        (377, 185), # top right horn
        (405, 305), # right cheek upper
        (375, 360), # right cheek lower
        (335, 350), # right chin outer
        (310, 375), # right chin inner
        (280, 355), # center bottom right
        (256, 355), # center bottom
        (232, 355), # center bottom left
        (202, 375), # left chin inner
        (177, 350), # left chin outer
        (137, 360), # left cheek lower
        (107, 305), # left cheek upper
    ]
    draw.polygon(clyde_points, fill=white)

    # Eyes: Ellipses with green color
    left_eye = [190, 275, 230, 315]
    right_eye = [282, 275, 322, 315]
    draw.ellipse(left_eye, fill=green)
    draw.ellipse(right_eye, fill=green)

    # Save PNG
    png_path = ASSETS_DIR / "discord_green.png"
    img.save(png_path, "PNG")
    print(f"[+] Saved PNG icon to: {png_path}")

    # Save ICO with multiple mipmap sizes
    ico_path = ASSETS_DIR / "bot_icon.ico"
    img.save(
        ico_path,
        format="ICO",
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    )
    print(f"[+] Saved ICO icon to: {ico_path} (Size: {os.path.getsize(ico_path)} bytes)")

if __name__ == "__main__":
    create_discord_green_icon()
