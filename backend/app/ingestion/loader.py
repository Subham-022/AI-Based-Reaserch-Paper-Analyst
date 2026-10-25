from __future__ import annotations

import ipaddress
import socket
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx


MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024

_ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/octet-stream",
}


class LoaderError(ValueError):
    """Raised when a paper cannot be safely loaded."""


def load_file(
    path: Path,
    max_bytes: int = MAX_DOWNLOAD_BYTES,
) -> bytes:
    if not path.exists():
        raise LoaderError("File does not exist.")

    if not path.is_file():
        raise LoaderError("The provided path is not a file.")

    if path.suffix.lower() != ".pdf":
        raise LoaderError("Only PDF files are supported.")

    if path.stat().st_size > max_bytes:
        raise LoaderError(
            "The PDF exceeds the maximum allowed size of 50 MB."
        )

    data = path.read_bytes()

    if not data.startswith(b"%PDF-"):
        raise LoaderError("The file is not a valid PDF.")

    return data


def _resolve_host(host: str) -> list[str]:
    try:
        results = socket.getaddrinfo(
            host,
            None,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise LoaderError(
            "Could not resolve the URL host."
        ) from exc

    return list(
        {
            result[4][0]
            for result in results
        }
    )


def _is_public_host(host: str) -> bool:
    if not host:
        return False

    try:
        addresses = _resolve_host(host)
    except LoaderError:
        raise

    for address in addresses:
        ip = ipaddress.ip_address(address)

        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False

    return True


def _validate_url(url: str) -> None:
    parsed = urlparse(url)

    if parsed.scheme != "https":
        raise LoaderError(
            "Only HTTPS URLs are allowed."
        )

    if not parsed.hostname:
        raise LoaderError(
            "The URL does not contain a valid hostname."
        )

    if parsed.username or parsed.password:
        raise LoaderError(
            "URLs containing credentials are not allowed."
        )

    if not _is_public_host(parsed.hostname):
        raise LoaderError(
            "The URL points to a private or restricted host."
        )


def load_url(
    url: str,
    max_bytes: int = MAX_DOWNLOAD_BYTES,
    timeout: float = 20.0,
) -> bytes:
    current_url = url

    with httpx.Client(
        timeout=timeout,
        follow_redirects=False,
    ) as client:
        for _ in range(4):
            _validate_url(current_url)

            response = client.get(current_url)

            if response.status_code in {
                301,
                302,
                303,
                307,
                308,
            }:
                location = response.headers.get(
                    "location"
                )

                if not location:
                    raise LoaderError(
                        "The redirect does not contain a destination."
                    )

                current_url = urljoin(
                    current_url,
                    location,
                )
                continue

            response.raise_for_status()

            content_type = response.headers.get(
                "content-type",
                "",
            )

            content_type = content_type.split(
                ";",
                maxsplit=1,
            )[0].strip().lower()

            data = response.content

            if len(data) > max_bytes:
                raise LoaderError(
                    "The downloaded PDF exceeds the "
                    "maximum allowed size of 50 MB."
                )

            if (
                content_type not in _ALLOWED_CONTENT_TYPES
                and not data.startswith(b"%PDF-")
            ):
                raise LoaderError(
                    "The URL did not return a PDF."
                )

            if not data.startswith(b"%PDF-"):
                raise LoaderError(
                    "The downloaded content is not a valid PDF."
                )

            return data

    raise LoaderError(
        "Too many redirects while loading the PDF."
    )