from __future__ import annotations

import json
import socket
import ssl
import urllib.parse
import urllib.request
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import List
from urllib.error import HTTPError, URLError

from PIL import Image, UnidentifiedImageError

from app import config


ARASAAC_API_BASE = "https://api.arasaac.org/api/pictograms"
ARASAAC_IMAGES_BASE = "https://static.arasaac.org/pictograms"
DEFAULT_RESULT_LIMIT = 12


@dataclass
class ArasaacResult:
    pictogram_id: int
    label: str
    image_url: str
    keywords: list[str]
    schematic: bool = False
    aac: bool = False


class ArasaacServiceError(Exception):
    def __init__(self, kind: str, message: str, cause: Exception | None = None):
        super().__init__(message)
        self.kind = kind
        self.cause = cause


class ArasaacService:
    def __init__(self, timeout: float = 12.0):
        self.timeout = timeout
        self.cache_dir = Path(config.DATA_DIR) / 'arasaac_cache'
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._ssl_context = ssl.create_default_context()

    def search_pictograms(self, query: str, language: str = 'es', limit: int = DEFAULT_RESULT_LIMIT) -> List[ArasaacResult]:
        query = (query or '').strip()
        if not query:
            return []
        language = self._normalize_language(language)
        url = f"{ARASAAC_API_BASE}/{language}/search/{urllib.parse.quote(query)}"
        try:
            with urllib.request.urlopen(url, timeout=self.timeout, context=self._ssl_context) as response:
                raw_payload = response.read().decode('utf-8')
            payload = json.loads(raw_payload)
        except HTTPError as e:
            if getattr(e, 'code', None) == 404:
                return []
            raise ArasaacServiceError('http', f'HTTP {e.code}: {e.reason}', e) from e
        except (URLError, TimeoutError, socket.timeout, ssl.SSLError) as e:
            raise ArasaacServiceError('network', str(e), e) from e
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ArasaacServiceError('payload', str(e), e) from e
        except Exception as e:
            raise ArasaacServiceError('unknown', str(e), e) from e

        if not isinstance(payload, list):
            raise ArasaacServiceError('payload', 'Unexpected ARASAAC payload type.')

        results: list[ArasaacResult] = []
        for item in payload[:max(1, int(limit))]:
            if not isinstance(item, dict):
                continue
            raw_id = item.get('_id')
            try:
                pictogram_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            keywords = [str(k.get('keyword', '')).strip() for k in item.get('keywords', []) if isinstance(k, dict) and str(k.get('keyword', '')).strip()]
            label = keywords[0] if keywords else str(pictogram_id)
            image_url = f"{ARASAAC_IMAGES_BASE}/{pictogram_id}/{pictogram_id}_300.png"
            results.append(
                ArasaacResult(
                    pictogram_id=pictogram_id,
                    label=label,
                    image_url=image_url,
                    keywords=keywords,
                    schematic=bool(item.get('schematic', False)),
                    aac=bool(item.get('aac', False)),
                )
            )
        return results

    def fetch_thumbnail_image(self, result: ArasaacResult, size: tuple[int, int] = (90, 90)) -> Image.Image:
        local_path = self._local_file_path(result.pictogram_id)
        image = self._load_cached_or_download(local_path, result.image_url)
        thumb = image.copy()
        thumb.thumbnail(size, Image.LANCZOS)
        return thumb

    def download_pictogram(self, result: ArasaacResult) -> str:
        local_path = self._local_file_path(result.pictogram_id)
        if local_path.exists():
            try:
                with Image.open(local_path) as cached:
                    cached.load()
                return str(local_path)
            except (FileNotFoundError, UnidentifiedImageError, OSError):
                local_path.unlink(missing_ok=True)
        image = self._download_image(result.image_url)
        try:
            image.save(local_path, format='PNG')
        except Exception as e:
            raise ArasaacServiceError('cache_write', str(e), e) from e
        return str(local_path)

    def _load_cached_or_download(self, local_path: Path, url: str) -> Image.Image:
        if local_path.exists():
            try:
                with Image.open(local_path) as cached:
                    cached.load()
                    return cached.convert('RGBA')
            except (FileNotFoundError, UnidentifiedImageError, OSError):
                local_path.unlink(missing_ok=True)
        return self._download_image(url)

    def _download_image(self, url: str) -> Image.Image:
        try:
            with urllib.request.urlopen(url, timeout=self.timeout, context=self._ssl_context) as response:
                content = response.read()
        except HTTPError as e:
            raise ArasaacServiceError('http', f'HTTP {e.code}: {e.reason}', e) from e
        except (URLError, TimeoutError, socket.timeout, ssl.SSLError) as e:
            raise ArasaacServiceError('network', str(e), e) from e
        except Exception as e:
            raise ArasaacServiceError('unknown', str(e), e) from e

        try:
            with Image.open(BytesIO(content)) as image:
                image.load()
                return image.convert('RGBA')
        except (UnidentifiedImageError, OSError, ValueError) as e:
            raise ArasaacServiceError('image', str(e), e) from e

    def _local_file_path(self, pictogram_id: int) -> Path:
        return self.cache_dir / f'arasaac_{int(pictogram_id)}.png'

    @staticmethod
    def _normalize_language(language: str) -> str:
        language = (language or 'es').strip().lower()
        if '-' in language:
            language = language.split('-', 1)[0]
        if '_' in language:
            language = language.split('_', 1)[0]
        return language if language in {'es', 'en', 'fr', 'pt', 'ca', 'eu', 'gl', 'de', 'it'} else 'es'
