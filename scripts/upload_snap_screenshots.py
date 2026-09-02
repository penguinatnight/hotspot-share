import os
import json
from pathlib import Path
from snapcraft.store import StoreClientCLI, constants
from snapcraft.store._metadata import StoreMetadataHandler, _media_hash

def upload_all_screenshots():
    client = StoreClientCLI()
    account_info = client.get_account_info()
    snap_id = account_info['snaps'][constants.DEFAULT_SERIES]['hotspot-share']['snap-id']
    handler = StoreMetadataHandler(base_url=client._base_url, request_method=client.request, snap_id=snap_id, snap_name='hotspot-share')

    icons, current_screenshots = handler._current_binary_metadata()
    print(f"Current icons: {len(icons)}, current screenshots: {len(current_screenshots)}")

    screenshot_dir = Path(__file__).parent.parent / 'assets' / 'screenshots'
    screenshot_files = sorted(screenshot_dir.glob('screenshot*.png'))
    print(f"Uploading {len(screenshot_files)} screenshots from {screenshot_dir}...")

    updated_info = list(icons)  # Keep the published app icon
    files = {}
    opened_files = []

    try:
        for i, path in enumerate(screenshot_files):
            key = f"screenshot_{i}"
            f = open(path, "rb")
            opened_files.append(f)
            h = _media_hash(f)
            updated_info.append({
                "type": "screenshot",
                "hash": h,
                "key": key,
                "filename": path.name
            })
            files[key] = f

        data = {"info": json.dumps(updated_info)}
        url = client._base_url + f"/dev/api/snaps/{snap_id}/binary-metadata"
        headers = {"Accept": "application/json"}
        resp = client.request("PUT", url, data=data, files=files, headers=headers)
        if resp.ok:
            print(f"Successfully published {len(screenshot_files)} screenshots to Snap Store!")
        else:
            print(f"Failed: {resp.status_code} {resp.text}")
    finally:
        for f in opened_files:
            f.close()

if __name__ == "__main__":
    upload_all_screenshots()
