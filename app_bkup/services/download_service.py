# app/services/download_service.py
from pathlib import Path

import requests


class DownloadError(Exception):
    pass


def download_file(url: str, output_path: str) -> str:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with requests.get(url, stream=True, timeout=300) as response:
        if response.status_code >= 400:
            raise DownloadError(f"Download failed: {response.status_code} {response.text}")

        with output.open("wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

    return str(output)
