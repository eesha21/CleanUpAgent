
import sys
import os
import io
import subprocess
import shutil
from datetime import datetime, timedelta
from PIL import Image
import ffmpeg

# ===== CONFIGURATION =====
ADB_PATH = r"D:/down/platform-tools-latest-windows/platform-tools/adb.exe"
DEVICE_DB_PATH = "/sdcard/Android/media/com.whatsapp/WhatsApp/Backups/Databases"
DEVICE_MEDIA_PATH = "/sdcard/Android/media/com.whatsapp/WhatsApp/Media"

TODAY = datetime.now().strftime("%Y-%m-%d")
LOCAL_BACKUP_ROOT = f"updated_whatsapp_{TODAY}"

RESIZE_WIDTH = 720
IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
VIDEO_EXTS = {".mp4", ".3gp", ".avi"}

# ===== USER PROMPTS =====
def ask_folders_to_delete(all_folders):
    print("\n🗑 Available Media folders:")
    for folder in all_folders:
        print(f"  - {folder}")
    to_delete = input("\nEnter folders to delete (comma-separated): ").strip()
    return {x.strip() for x in to_delete.split(',') if x.strip() in all_folders}

def ask_delete_old_dbs():
    choice = input("\n❓ Do you want to delete old .crypt14 files from the phone? (y/n): ").strip().lower()
    return choice == 'y'

# ===== RESIZE FUNCTIONS =====
def resize_image(path):
    try:
        with Image.open(path) as img:
            original_width, _ = img.size
            if original_width <= RESIZE_WIDTH:
                return False  # Skipped

            img.thumbnail((RESIZE_WIDTH, RESIZE_WIDTH))
            img.save(path)
            return True  # Resized

    except Exception:
        return False  # Failed, treated as skipped

def resize_video(path):
    try:
        temp_path = path + ".tmp.mp4"
        (
            ffmpeg
            .input(path)
            .filter('scale', f'{RESIZE_WIDTH}:-2')
            .output(temp_path, vcodec='libx264', acodec='aac', strict='experimental')
            .overwrite_output()
            .run(quiet=True)
        )
        os.replace(temp_path, path)
        return True  # Resized

    except Exception:
        return False  # Skipped on failure

# ===== PROCESS MEDIA =====
def resize_media(media_root):
    images_resized, videos_resized, images_skipped, videos_skipped = 0, 0, 0, 0

    for folder in ["WhatsApp Images", "WhatsApp Video"]:
        folder_path = os.path.join(media_root, folder)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path, exist_ok=True)
            continue

        for root, _, files in os.walk(folder_path):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                full_path = os.path.join(root, file)

                if ext in IMAGE_EXTS:
                    result = resize_image(full_path)
                    if result:
                        images_resized += 1
                    else:
                        images_skipped += 1

                elif ext in VIDEO_EXTS:
                    result = resize_video(full_path)
                    if result:
                        videos_resized += 1
                    else:
                        videos_skipped += 1

    print(f"\n✅ Resized {images_resized} images, {videos_resized} videos.")
    print(f"✅ Skipped {images_skipped} images, {videos_skipped} videos.\n")

# ===== DELETE FOLDERS =====
def delete_folders(media_root, folders_to_delete):
    for folder in folders_to_delete:
        path = os.path.join(media_root, folder)
        if os.path.exists(path):
            shutil.rmtree(path, ignore_errors=True)
            print(f"🗑 Deleted folder: {folder}")

# ===== MAIN FUNCTION =====
def pull_whatsapp_backup():
    print(f"\n📁 Creating backup folder: {LOCAL_BACKUP_ROOT}")
    backups_folder = os.path.join(LOCAL_BACKUP_ROOT, "Backups", "Databases")
    media_folder = os.path.join(LOCAL_BACKUP_ROOT, "Media")

    os.makedirs(backups_folder, exist_ok=True)
    os.makedirs(media_folder, exist_ok=True)

    # === Pull Databases ===
    print(f"\n📥 Pulling Databases → {backups_folder}")
    subprocess.run([ADB_PATH, "pull", DEVICE_DB_PATH, backups_folder], stdout=subprocess.DEVNULL)

    cutoff = datetime.now() - timedelta(days=60)
    delete_old = ask_delete_old_dbs()

    for file in os.listdir(backups_folder):
        if file.endswith(".crypt14"):
            path = os.path.join(backups_folder, file)
            mod_time = datetime.fromtimestamp(os.path.getmtime(path))
            if mod_time < cutoff:
                os.remove(path)
                print(f"❌ Removed old DB: {file}")
                if delete_old:
                    subprocess.run([ADB_PATH, "shell", "rm", f"{DEVICE_DB_PATH}/{file}"])

    # === Pull Selected Media Folders ===
    print(f"\n📥 Pulling full Media → {media_folder}")

    folders_to_pull = [
        "WhatsApp Images",
        "WhatsApp Video",
        "WhatsApp Documents",
        "WhatsApp Stickers",
        "WhatsApp Audio",
        "WallPaper",
        "WhatsApp Profile Photos"
    ]

    for folder_name in folders_to_pull:
        print(f"📥 Pulling: {folder_name}")
        subprocess.run([
            ADB_PATH, "pull",
            f"{DEVICE_MEDIA_PATH}/{folder_name}",
            os.path.join(media_folder, folder_name)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # === List and Delete Folders ===
    if not os.path.exists(media_folder):
        print("❌ Media folder not found after pull.")
        return

    folders_in_media = [f for f in os.listdir(media_folder) if not f.startswith('.') and os.path.isdir(os.path.join(media_folder, f))]
    for folder in folders_in_media:
        total = sum(len(files) for _, _, files in os.walk(os.path.join(media_folder, folder)))
        print(f"🔍 Found {total} files in {folder}")

    folders_to_delete = ask_folders_to_delete(folders_in_media)

    print("\n🔧 Resizing Media...")
    resize_media(media_folder)

    print("🧹 Deleting unwanted folders...")
    delete_folders(media_folder, folders_to_delete)

    print(f"\n✅ Backup completed: {LOCAL_BACKUP_ROOT}\n")

# ===== RUN =====
if __name__ == "__main__":
    pull_whatsapp_backup()


def run_agent3():
    log_capture = io.StringIO()
    sys.stdout = log_capture
    try:
        pull_whatsapp_backup()
    except Exception as e:
        print(f"❌ Error: {e}")
    sys.stdout = sys.__stdout__
    return log_capture.getvalue()
