"""Whitelisted public demo-source acquisition, separate from document parsing."""

from pathlib import Path

import httpx

BIOLOGY_SYLLABUS_URL = "https://www.cambridgeinternational.org/Images/697203-2026-2028-syllabus.pdf"


async def download_biology_syllabus(destination: Path):
    if destination.is_file():
        return destination
    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
        response = await client.get(BIOLOGY_SYLLABUS_URL)
        response.raise_for_status()
        if not response.content.startswith(b"%PDF") or len(response.content) > 10 * 1024 * 1024:
            raise ValueError("The public syllabus endpoint did not return a supported PDF")
        destination.parent.mkdir(exist_ok=True)
        temporary = destination.with_suffix(".download")
        temporary.write_bytes(response.content)
        temporary.replace(destination)
    return destination
