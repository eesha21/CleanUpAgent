import os
import io
import sys
import datetime
import shutil
from PIL import Image
from pillow_heif import register_heif_opener
import imagehash

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

# 📦 CONFIG
SCOPES = ['https://www.googleapis.com/auth/drive']
PROCESSED_DIR = "downloaded_images"
UPLOAD_FOLDER_ID = '1Ogap-F4W2ebontg7pHDAh_Ky7QBYkOgz'
HASHES = set()

register_heif_opener()

def authenticate():
    flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
    creds = flow.run_local_server(port=0, open_browser=True)
    return build("drive", "v3", credentials=creds)

def find_images_in_drive(service):
    query = "mimeType contains 'image/' and trashed = false"
    results = service.files().list(q=query, pageSize=1000, fields="files(id, name, size)").execute()
    return results.get('files', [])

def find_large_files_in_drive(service, min_size=15 * 1024 * 1024):
    query = "mimeType != 'application/vnd.google-apps.folder' and trashed = false"
    results = service.files().list(q=query, pageSize=1000, fields="files(id, name, size)").execute()
    files = results.get('files', [])
    return [f for f in files if int(f.get('size', 0)) > min_size]

def download_file(service, file_id, filename, target_folder):
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    fh.seek(0)
    with open(os.path.join(target_folder, filename), 'wb') as f:
        f.write(fh.read())

def compress_image(image, path, quality=85, max_width=1920):
    if image.width > max_width:
        ratio = max_width / float(image.width)
        new_height = int(image.height * ratio)
        image = image.resize((max_width, new_height), Image.LANCZOS)
    image.save(path, "JPEG", quality=quality, optimize=True)

def deduplicate_and_compress_images(usb_dir):
    images_resized, images_skipped = 0, 0
    for filename in os.listdir(PROCESSED_DIR):
        src_path = os.path.join(PROCESSED_DIR, filename)
        try:
            img = Image.open(src_path)

            if filename.lower().endswith(".heic"):
                filename = os.path.splitext(filename)[0] + ".jpg"
                new_path = os.path.join(PROCESSED_DIR, filename)
                img.save(new_path, "JPEG")
                os.remove(src_path)
                src_path = new_path
                img = Image.open(src_path)

            shutil.copy2(src_path, os.path.join(usb_dir, filename))

            h = imagehash.average_hash(img)
            if h in HASHES:
                os.remove(src_path)
                continue
            HASHES.add(h)

            compress_image(img, src_path)
            images_resized += 1

        except:
            images_skipped += 1

    print(f"\n✅ Resized {images_resized} images.")
    print(f"✅ Skipped {images_skipped} images.\n")

def delete_large_files_from_drive(service, files):
    deleted, failed = 0, 0
    for f in files:
        try:
            service.files().delete(fileId=f['id']).execute()
            print(f"🗑 Deleted from Drive: {f['name']}")
            deleted += 1
        except Exception as e:
            print(f"⚠ Failed to delete {f['name']}: {e}")
            failed += 1
    return deleted, failed

def upload_resized_images(service, folder_id):
    existing_files = {}
    results = service.files().list(q=f"'{folder_id}' in parents and trashed = false",
                                   fields="files(id, name)").execute()
    for f in results.get('files', []):
        existing_files[f['name']] = f['id']

    uploaded, updated = 0, 0
    for file in os.listdir(PROCESSED_DIR):
        file_path = os.path.join(PROCESSED_DIR, file)
        media = MediaFileUpload(file_path, resumable=True)

        if file in existing_files:
            service.files().update(fileId=existing_files[file], media_body=media).execute()
            print(f"🔄 Updated in Drive: {file}")
            updated += 1
        else:
            service.files().create(body={'name': file, 'parents': [folder_id]}, media_body=media).execute()
            print(f"☁ Uploaded new: {file}")
            uploaded += 1
    return uploaded, updated

def run_agent2(usb_root, progress_callback=None, status_callback=None):
    log_capture = io.StringIO()
    sys.stdout = log_capture

    try:
        if not os.path.exists(usb_root):
            raise FileNotFoundError(f"The path '{usb_root}' does not exist.")

        today = datetime.date.today().isoformat()
        usb_dir = os.path.join(usb_root, f"backup_{today}")
        os.makedirs(usb_dir, exist_ok=True)

        if not os.path.exists(PROCESSED_DIR):
            os.makedirs(PROCESSED_DIR)

        if status_callback: status_callback("🔐 Signing into Google Drive…")
        if progress_callback: progress_callback(5)

        service = authenticate()

        if status_callback: status_callback("🔍 Scanning Drive for images…")
        images = find_images_in_drive(service)
        print(f"📸 Found {len(images)} images.")
        if progress_callback: progress_callback(15)

        for idx, f in enumerate(images):
            if status_callback: status_callback(f"⬇ Downloading: {f['name']}")
            download_file(service, f['id'], f['name'], PROCESSED_DIR)
            if progress_callback: progress_callback(15 + int(10 * (idx + 1) / max(1, len(images))))

        if status_callback: status_callback("🛠 Compressing and de-duplicating images…")
        deduplicate_and_compress_images(usb_dir)
        if progress_callback: progress_callback(40)

        if status_callback: status_callback("🔍 Scanning Drive for large files…")
        large_files = find_large_files_in_drive(service)
        print(f"📦 Found {len(large_files)} large files.")
        if progress_callback: progress_callback(55)

        for idx, f in enumerate(large_files):
            if status_callback: status_callback(f"⬇ Downloading: {f['name']}")
            download_file(service, f['id'], f['name'], usb_dir)
            if progress_callback: progress_callback(55 + int(10 * (idx + 1) / max(1, len(large_files))))

        if status_callback: status_callback("🗑 Deleting large files from Drive…")
        deleted, failed = delete_large_files_from_drive(service, large_files)
        print(f"🗑 Deleted {deleted}, Failed: {failed}")
        if progress_callback: progress_callback(75)

        if status_callback: status_callback("☁ Uploading compressed images back to Drive…")
        uploaded, updated = upload_resized_images(service, UPLOAD_FOLDER_ID)
        print(f"☁ Uploaded: {uploaded}, Updated: {updated}")
        if progress_callback: progress_callback(95)

        if status_callback: status_callback("✅ Backup Complete!")
        if progress_callback: progress_callback(100)

        print(f"\n✅ Backup done.\nFiles saved to: {usb_dir}\nImages: {PROCESSED_DIR}")

    except Exception as e:
        print(f"❌ Error: {e}")
        if status_callback: status_callback(f"❌ Error: {e}")

    sys.stdout = sys.__stdout__
    return log_capture.getvalue()
