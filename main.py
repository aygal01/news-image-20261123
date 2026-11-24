#!/usr/bin/env python3
"""Entrypoint for the news-image-20261123 make.fun entry.

The repository ships the finished front page as ``entry.png`` next to this
file. This program copies it into the output directory the grader names
and verifies the copy, so the run is deterministic: no network, no clock,
no randomness — two runs produce byte-identical output.

Output location, first match wins:
  1. ``--output <path>`` on the command line (a file path, or a
     directory, in which case ``entry.png`` is written inside it),
  2. ``MAKEFUN_OUTPUT_DIR`` (the grader's convention),
  3. ``ENTRY_OUTPUT`` (a file path, or a directory),
  4. ``/output/entry.png``.
"""

import argparse
import hashlib
import os
import sys
import tempfile
from pathlib import Path

SOURCE_NAME = "entry.png"
MAX_BYTES = 1_048_576  # 1 MiB cap for the delivered image
JPEG_MAGIC = b"\xff\xd8"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}


def source_path() -> Path:
    return Path(__file__).resolve().parent / SOURCE_NAME


def looks_like_image(data: bytes) -> bool:
    return data.startswith(JPEG_MAGIC) or data.startswith(PNG_MAGIC)


def as_output_file(p: Path) -> Path:
    """Interpret a user-supplied path as a file or a directory.

    A path is a file only when it names an image file (known suffix);
    anything else — an existing directory, a path ending in a separator,
    or a not-yet-existing plain name — is a directory that receives
    ``entry.png``. This matters because the output directory often does
    not exist yet when the grader invokes us.
    """
    if p.suffix.lower() in IMAGE_SUFFIXES:
        return p
    return p / SOURCE_NAME


def resolve_output(explicit: str | None) -> Path:
    """Work out the destination file from CLI, env, then the default."""
    if explicit:
        return as_output_file(Path(explicit))
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR")
    if out_dir:
        return Path(out_dir) / SOURCE_NAME
    single = os.environ.get("ENTRY_OUTPUT")
    if single:
        return as_output_file(Path(single))
    return Path("/output") / SOURCE_NAME


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def deliver(dest: Path, data: bytes) -> None:
    """Write ``data`` to ``dest`` atomically, then verify the copy.

    The bytes go to a temporary file in the destination directory first
    and are moved into place with ``os.replace``, so a failed run can
    never leave a half-written image behind. The copy is then read back
    and checked byte-for-byte against the source.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".entry-", dir=dest.parent)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, dest)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise
    written = dest.read_bytes()
    if sha256_hex(written) != sha256_hex(data):
        raise IOError("written file hash does not match source")
    if len(written) > MAX_BYTES or not looks_like_image(written):
        raise IOError("written file failed verification")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Deliver the finished news image to the output directory.")
    parser.add_argument("--output", metavar="PATH",
                        help="destination file or directory")
    parser.add_argument("--check", action="store_true",
                        help="only validate the source image, write nothing")
    args = parser.parse_args(argv)

    src = source_path()
    if not src.is_file():
        print(f"error: source image missing: {src}", file=sys.stderr)
        return 1
    data = src.read_bytes()
    if len(data) > MAX_BYTES:
        print(f"error: source is {len(data)} bytes, over the 1 MiB cap",
              file=sys.stderr)
        return 1
    if not looks_like_image(data):
        print("error: source is neither JPEG nor PNG", file=sys.stderr)
        return 1
    if args.check:
        print(f"ok: {src} ({len(data)} bytes, "
              f"sha256 {sha256_hex(data)})")
        return 0

    dest = resolve_output(args.output)
    try:
        deliver(dest, data)
    except OSError as exc:
        print(f"error: could not deliver image to {dest}: {exc}",
              file=sys.stderr)
        return 1
    print(f"wrote {dest} ({len(data)} bytes, sha256 {sha256_hex(data)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
