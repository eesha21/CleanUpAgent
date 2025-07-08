from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import os

# --- Step 1: Authenticate Google Drive ---
SCOPES = ['https://www.googleapis.com/auth/drive']

def authenticate():
    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
    creds = flow.run_local_server(port=0)
    service = build('drive', 'v3', credentials=creds)
    return service

# --- Step 2: List all image files from Google Drive ---
def list_image_files(service, folder_id):
    query = f"'{folder_id}' in parents and mimeType contains 'image/' and trashed = false"
    results = service.files().list(
        q=query,
        fields="nextPageToken, files(id, name, mimeType, size, md5Checksum)"
    ).execute()
    return results.get('files', [])

# --- Step 3: Identify duplicates using md5Checksum ---
def find_duplicates(files):
    seen_hashes = {}
    duplicates = []

    for file in files:
        hash_val = file.get('md5Checksum')
        if not hash_val:
            continue  # Some files (like Google Docs) don’t have checksums
        if hash_val in seen_hashes:
            duplicates.append(file)
        else:
            seen_hashes[hash_val] = file
    return duplicates

# --- Step 4: Delete duplicate files ---
def delete_files(service, duplicates):
    for file in duplicates:
        try:
            service.files().delete(fileId=file['id']).execute()
            print(f"Deleted duplicate: {file['name']}")
        except Exception as e:
            print(f"Failed to delete {file['name']}: {e}")

# --- Step 5: Main flow ---
def main():
    service = authenticate()
    folder_id = '13vyykE9UmncD1SLdNDazpFDkkpy6CFsG' 

    files = list_image_files(service, folder_id)
    print(f"Total images found in 'photos': {len(files)}")

    duplicates = find_duplicates(files)
    print(f"Duplicate images found: {len(duplicates)}")

    if duplicates:
        delete_files(service, duplicates)
    else:
        print("No duplicates found.")

if __name__ == '__main__':
    main()