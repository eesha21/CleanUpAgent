from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import io
import os
import sys

SCOPES = ['https://www.googleapis.com/auth/drive']

def authenticate():
    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
    creds = flow.run_local_server(port=0, open_browser=True)  # 👈 opens browser silently
    service = build('drive', 'v3', credentials=creds)
    return service

def list_image_files(service, folder_id):
    query = f"'{folder_id}' in parents and mimeType contains 'image/' and trashed = false"
    results = service.files().list(
        q=query,
        fields="files(id, name, mimeType, size, md5Checksum)"
    ).execute()
    return results.get('files', [])

def find_duplicates(files):
    seen_hashes = {}
    duplicates = []

    for file in files:
        hash_val = file.get('md5Checksum')
        if not hash_val:
            continue
        if hash_val in seen_hashes:
            duplicates.append(file)
        else:
            seen_hashes[hash_val] = file
    return duplicates

def delete_files(service, duplicates):
    deleted = 0
    failed = 0
    for file in duplicates:
        try:
            service.files().delete(fileId=file['id']).execute()
            print(f"🗑 Deleted duplicate: {file['name']}")
            deleted += 1
        except Exception as e:
            print(f"⚠️ Failed to delete {file['name']}: {e}")
            failed += 1
    return deleted, failed

def main():
    print("🔐 Signing into Google Drive...")
    service = authenticate()

    folder_id = '13vyykE9UmncD1SLdNDazpFDkkpy6CFsG'
    print("🔍 Scanning for images...")

    files = list_image_files(service, folder_id)
    total = len(files)
    print(f"📸 Total images found: {total}")

    duplicates = find_duplicates(files)
    dup_count = len(duplicates)
    print(f"♻️ Duplicate images found: {dup_count}")

    if dup_count > 0:
        print("🚀 Removing duplicates...")
        deleted, failed = delete_files(service, duplicates)
        print(f"✅ Cleanup complete. {deleted} files deleted. {failed} failed.")
    else:
        print("✅ No duplicates found. Drive is clean!")

def run_agent1():
    log_capture = io.StringIO()
    sys.stdout = log_capture
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}")
    sys.stdout = sys.__stdout__
    return log_capture.getvalue()

if __name__ == '__main__':
    main()
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

def run_agent2(usb_root):
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

        print("🔐 Signing into Google Drive...")
        service = authenticate()

        print("\n🔍 Searching your entire Drive for images...")
        images = find_images_in_drive(service)
        print(f"📸 Found {len(images)} images.")

        for f in images:
            download_file(service, f['id'], f['name'], PROCESSED_DIR)

        deduplicate_and_compress_images(usb_dir)

        print("🔍 Searching your entire Drive for large files...")
        large_files = find_large_files_in_drive(service)
        print(f"📦 Found {len(large_files)} large files (>15MB).")

        for f in large_files:
            download_file(service, f['id'], f['name'], usb_dir)

        deleted, failed = delete_large_files_from_drive(service, large_files)
        print(f"🗑 Deleted {deleted} large files. ⚠ {failed} failed to delete.")

        uploaded, updated = upload_resized_images(service, UPLOAD_FOLDER_ID)
        print(f"☁ Uploaded {uploaded} new images. 🔄 Updated {updated} images.")

        print(f"\n✅ Backup Complete!\n🗂 Originals saved to → {usb_dir}\n🖼 Compressed images in → {PROCESSED_DIR}")

    except Exception as e:
        print(f"\n❌ Error: {e}")

    sys.stdout = sys.__stdout__
    return log_capture.getvalue()
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

def run_agent2(usb_root):
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

        print("🔐 Signing into Google Drive...")
        service = authenticate()

        print("\n🔍 Searching your entire Drive for images...")
        images = find_images_in_drive(service)
        print(f"📸 Found {len(images)} images.")

        for f in images:
            download_file(service, f['id'], f['name'], PROCESSED_DIR)

        deduplicate_and_compress_images(usb_dir)

        print("🔍 Searching your entire Drive for large files...")
        large_files = find_large_files_in_drive(service)
        print(f"📦 Found {len(large_files)} large files (>15MB).")

        for f in large_files:
            download_file(service, f['id'], f['name'], usb_dir)

        deleted, failed = delete_large_files_from_drive(service, large_files)
        print(f"🗑 Deleted {deleted} large files. ⚠ {failed} failed to delete.")

        uploaded, updated = upload_resized_images(service, UPLOAD_FOLDER_ID)
        print(f"☁ Uploaded {uploaded} new images. 🔄 Updated {updated} images.")

        print(f"\n✅ Backup Complete!\n🗂 Originals saved to → {usb_dir}\n🖼 Compressed images in → {PROCESSED_DIR}")

    except Exception as e:
        print(f"\n❌ Error: {e}")

    sys.stdout = sys.__stdout__
    return log_capture.getvalue()
