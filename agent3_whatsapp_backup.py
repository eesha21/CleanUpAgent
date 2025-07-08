import sys
import os
import io
import subprocess
import shutil
from datetime import datetime, timedelta
from PIL import Image
import ffmpeg

RESIZE_WIDTH = 720
IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
VIDEO_EXTS = {".mp4", ".3gp", ".avi"}

def resize_image(path):
    try:
        with Image.open(path) as img:
            original_width, _ = img.size
            if original_width <= RESIZE_WIDTH:
                return False
            img.thumbnail((RESIZE_WIDTH, RESIZE_WIDTH))
            img.save(path)
            return True
    except Exception:
        return False

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
        return True
    except Exception:
        return False

def resize_media(media_root, status_callback=None):
    images_resized = videos_resized = images_skipped = videos_skipped = 0
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
                    if resize_image(full_path):
                        images_resized += 1
                    else:
                        images_skipped += 1
                elif ext in VIDEO_EXTS:
                    if resize_video(full_path):
                        videos_resized += 1
                    else:
                        videos_skipped += 1

    print(f"\n✅ Resized {images_resized} images, {videos_resized} videos.")
    print(f"✅ Skipped {images_skipped} images, {videos_skipped} videos.\n")

def delete_folders(media_root, folders_to_delete, status_callback=None):
    for folder in folders_to_delete:
        path = os.path.join(media_root, folder)
        if os.path.exists(path):
            shutil.rmtree(path, ignore_errors=True)
            print(f"🗑 Deleted folder: {folder}")

def pull_whatsapp_backup(adb_path, db_path, media_path, status_callback=None, progress_callback=None):
    log_capture = io.StringIO()
    sys.stdout = log_capture

    try:
        today = datetime.now().strftime("%Y-%m-%d")
        local_backup_root = f"updated_whatsapp_{today}"
        backups_folder = os.path.join(local_backup_root, "Backups", "Databases")
        media_folder = os.path.join(local_backup_root, "Media")

        os.makedirs(backups_folder, exist_ok=True)
        os.makedirs(media_folder, exist_ok=True)

        if status_callback: status_callback("📥 Pulling Databases...")
        if progress_callback: progress_callback(10)
        subprocess.run([adb_path, "pull", db_path, backups_folder], stdout=subprocess.DEVNULL)

        cutoff = datetime.now() - timedelta(days=60)
        for file in os.listdir(backups_folder):
            if file.endswith(".crypt14"):
                path = os.path.join(backups_folder, file)
                mod_time = datetime.fromtimestamp(os.path.getmtime(path))
                if mod_time < cutoff:
                    os.remove(path)
                    print(f"❌ Removed old DB: {file}")

        if status_callback: status_callback("📥 Pulling Media...")
        if progress_callback: progress_callback(30)

        folders_to_pull = [
            "WhatsApp Images", "WhatsApp Video", "WhatsApp Documents",
            "WhatsApp Stickers", "WhatsApp Audio", "WallPaper", "WhatsApp Profile Photos"
        ]

        for folder_name in folders_to_pull:
            subprocess.run([
                adb_path, "pull",
                f"{media_path}/{folder_name}",
                os.path.join(media_folder, folder_name)
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        folders_in_media = [f for f in os.listdir(media_folder) if os.path.isdir(os.path.join(media_folder, f))]
        for folder in folders_in_media:
            total = sum(len(files) for _, _, files in os.walk(os.path.join(media_folder, folder)))
            print(f"🔍 Found {total} files in {folder}")

        if status_callback: status_callback("🔧 Resizing Media...")
        if progress_callback: progress_callback(60)
        resize_media(media_folder, status_callback)

        folders_to_delete = {f for f in folders_in_media if f not in {"WhatsApp Images", "WhatsApp Video"}}

        if status_callback: status_callback("🧹 Deleting Unwanted Folders...")
        delete_folders(media_folder, folders_to_delete, status_callback)
        if progress_callback: progress_callback(90)

        print(f"\n✅ Backup completed: {local_backup_root}")
        if status_callback: status_callback("✅ Backup Complete!")
        if progress_callback: progress_callback(100)

    except Exception as e:
        print(f"❌ Error: {e}")
        if status_callback: status_callback(f"❌ Error: {e}")

    sys.stdout = sys.__stdout__
    return log_capture.getvalue()

def run_agent3(adb_path, db_path, media_path, progress_callback=None, status_callback=None):
    return pull_whatsapp_backup(adb_path, db_path, media_path, status_callback, progress_callback)
