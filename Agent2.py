import os
import io
import shutil
import datetime
from PIL import Image
from pillow_heif import register_heif_opener
import imagehash

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

# 📦 CONFIG
SCOPES = ['https://www.googleapis.com/auth/drive']
PROCESSED_DIR = "downloaded_images"
USB_ROOT = "F:/"  # ✅ Change to your USB
UPLOAD_FOLDER_ID = '1Ogap-F4W2ebontg7pHDAh_Ky7QBYkOgz'  # ✅ Resized image upload target

today = datetime.date.today().isoformat()
USB_DIR = os.path.join(USB_ROOT, f"backup_{today}")
os.makedirs(USB_DIR, exist_ok=True)
HASHES = set()

register_heif_opener()

# 🔐 Authenticate
def authenticate():
    flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
    creds = flow.run_local_server(port=0)
    return build("drive", "v3", credentials=creds)

# 📁 List images
def find_images_in_folder(service, folder_id):
    query = f"'{folder_id}' in parents and mimeType contains 'image/' and trashed = false"
    results = service.files().list(q=query, pageSize=100, fields="files(id, name, size)").execute()
    return results.get('files', [])

# 📁 List large files
def find_large_files_in_folder(service, folder_id, min_size=15 * 1024 * 1024):
    query = f"'{folder_id}' in parents and mimeType != 'application/vnd.google-apps.folder' and trashed = false"
    results = service.files().list(q=query, pageSize=100, fields="files(id, name, size)").execute()
    files = results.get('files', [])
    return [f for f in files if int(f.get('size', 0)) > min_size]

# 💾 Download file
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

# 📉 Compress image
def compress_image(image, path, quality=85, max_width=1920):
    if image.width > max_width:
        ratio = max_width / float(image.width)
        new_height = int(image.height * ratio)
        image = image.resize((max_width, new_height), Image.LANCZOS)
    image.save(path, "JPEG", quality=quality, optimize=True)

# 🧹 Process images
def deduplicate_and_compress_images():
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

            shutil.copy2(src_path, os.path.join(USB_DIR, filename))

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

# ❌ Delete large files from Drive
def delete_large_files_from_drive(service, files):
    choice = input("\n❓ Do you want to delete the large files from Drive? (y/n): ").strip().lower()
    if choice != 'y':
        print("❌ Skipped deletion.")
        return

    for f in files:
        try:
            service.files().delete(fileId=f['id']).execute()
            print(f"🗑 Deleted from Drive: {f['name']}")
        except Exception as e:
            print(f"⚠️ Failed to delete {f['name']}: {e}")

# ☁️ Upload resized images back to Drive
def upload_resized_images(service, folder_id):
    choice = input("\n❓ Do you want to upload resized images back to Drive? (y/n): ").strip().lower()
    if choice != 'y':
        print("❌ Skipped upload.")
        return

    # Get existing files in the folder (to overwrite by name)
    existing_files = {}
    results = service.files().list(q=f"'{folder_id}' in parents and trashed = false",
                                   fields="files(id, name)").execute()
    for f in results.get('files', []):
        existing_files[f['name']] = f['id']

    for file in os.listdir(PROCESSED_DIR):
        file_path = os.path.join(PROCESSED_DIR, file)
        media = MediaFileUpload(file_path, resumable=True)

        if file in existing_files:
            service.files().update(fileId=existing_files[file], media_body=media).execute()
            print(f"🔄 Updated in Drive: {file}")
        else:
            service.files().create(body={'name': file, 'parents': [folder_id]}, media_body=media).execute()
            print(f"☁️ Uploaded new: {file}")

# 🚀 Main
def main():
    FOLDER_ID = '13vyykE9UmncD1SLdNDazpFDkkpy6CFsG'

    if not os.path.exists(PROCESSED_DIR):
        os.makedirs(PROCESSED_DIR)

    service = authenticate()

    print("\n🔍 Finding images...")
    images = find_images_in_folder(service, FOLDER_ID)
    print(f"📥 Found {len(images)} images.")
    for f in images:
        download_file(service, f['id'], f['name'], PROCESSED_DIR)

    deduplicate_and_compress_images()

    print("🔍 Finding large files...")
    large_files = find_large_files_in_folder(service, FOLDER_ID)
    print(f"📦 Found {len(large_files)} large files.")
    for f in large_files:
        download_file(service, f['id'], f['name'], USB_DIR)

    delete_large_files_from_drive(service, large_files)
    upload_resized_images(service, UPLOAD_FOLDER_ID)

    print(f"\n✅ Backup complete: Originals on USB → {USB_DIR}")
    print(f"🖼 Compressed images in → {PROCESSED_DIR}")

if __name__ == "__main__":
    main()
