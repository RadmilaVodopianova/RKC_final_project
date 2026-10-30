"""Приватні резервні копії SQLite, налаштувань і оригіналів фото."""

import argparse
from contextlib import closing, contextmanager
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import tarfile
from tempfile import TemporaryDirectory
from uuid import uuid4


ARCHIVE_PATTERN = re.compile(r"rkc-backup-\d{8}T\d{6}Z-[0-9a-f]{8}\.tar\.gz")


def file_hash(stream):
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


@contextmanager
def backup_lock(directory):
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(directory / ".backup.lock", flags, 0o600)
    try:
        if os.name == "posix":
            import fcntl

            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(descriptor)


def verify_archive(path):
    """Перевіряє вміст без розпакування архіву в робочий проєкт."""
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        if len(names) != len(set(names)) or any(not member.isfile() for member in members):
            raise ValueError("Архів містить повтори або неприпустимі типи файлів.")
        with archive.extractfile("backup-info.json") as stream:
            manifest = json.load(stream)
        if manifest.get("version") != 1 or not isinstance(manifest.get("files"), dict):
            raise ValueError("Невідомий формат резервної копії.")
        files = manifest["files"]
        if not {"db.sqlite3", ".env"}.issubset(files):
            raise ValueError("В архіві відсутня база або налаштування.")
        if set(names) != set(files) | {"backup-info.json"}:
            raise ValueError("Список файлів архіву не збігається з описом.")
        for name, expected_hash in files.items():
            if name not in {"db.sqlite3", ".env"} and not name.startswith("media/products/"):
                raise ValueError("Неприпустимий шлях в архіві.")
            if ".." in name.split("/"):
                raise ValueError("Неприпустимий шлях в архіві.")
            with archive.extractfile(name) as stream:
                if file_hash(stream) != expected_hash:
                    raise ValueError(f"Пошкоджено файл в архіві: {name}")


def create_backup(project, directory, keep=7):
    project = Path(project).resolve(strict=True)
    directory = Path(directory).expanduser().resolve()
    if keep < 1:
        raise ValueError("Потрібно зберігати щонайменше один архів.")
    if directory == project or project in directory.parents:
        raise ValueError("Папка резервних копій має бути поза проєктом.")

    database = project / "db.sqlite3"
    environment = project / ".env"
    photos = project / "media/products"
    for path in (database, environment):
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Відсутній звичайний файл: {path.name}")
    if photos.is_symlink() or not photos.is_dir() or not photos.resolve().is_relative_to(project):
        raise ValueError("Не знайдено папку оригіналів фото media/products.")
    photo_files = []
    for path in sorted(photos.rglob("*")):
        if path.is_symlink():
            raise ValueError("Символічні посилання в папці фото не підтримуються.")
        if path.is_file():
            photo_files.append(path)

    previous_umask = os.umask(0o077)
    partial = None
    try:
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        directory.chmod(0o700)
        with backup_lock(directory):
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            name = f"rkc-backup-{stamp}-{uuid4().hex[:8]}.tar.gz"
            result = directory / name
            partial = directory / f".{name}.partial"
            with TemporaryDirectory(prefix=".rkc-snapshot-", dir=directory) as temporary:
                snapshot = Path(temporary) / "db.sqlite3"
                with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as source:
                    with closing(sqlite3.connect(snapshot)) as destination:
                        source.backup(destination, pages=128, sleep=0.1)
                        if destination.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                            raise ValueError("Копія бази не пройшла перевірку цілісності.")
                saved_environment = Path(temporary) / ".env"
                saved_environment.write_bytes(environment.read_bytes())
                files = {"db.sqlite3": snapshot, ".env": saved_environment}
                files.update({path.relative_to(project).as_posix(): path for path in photo_files})
                hashes = {}
                for archive_name, path in files.items():
                    with path.open("rb") as stream:
                        hashes[archive_name] = file_hash(stream)
                manifest = json.dumps(
                    {"version": 1, "created_at": stamp, "files": hashes},
                    ensure_ascii=False,
                    indent=2,
                ).encode("utf-8")
                with partial.open("xb") as raw:
                    with tarfile.open(fileobj=raw, mode="w:gz", compresslevel=3) as archive:
                        info = tarfile.TarInfo("backup-info.json")
                        info.size = len(manifest)
                        info.mode = 0o600
                        archive.addfile(info, io.BytesIO(manifest))
                        for archive_name, path in files.items():
                            archive.add(path, arcname=archive_name, recursive=False)
                    raw.flush()
                    os.fsync(raw.fileno())
                verify_archive(partial)
                partial.rename(result)

            archives = sorted(
                (
                    path for path in directory.iterdir()
                    if ARCHIVE_PATTERN.fullmatch(path.name) and path.is_file() and not path.is_symlink()
                ),
                key=lambda path: (path.stat().st_mtime_ns, path.name),
            )
            for old_archive in archives[:-keep]:
                old_archive.unlink()
            return result
    finally:
        if partial is not None:
            partial.unlink(missing_ok=True)
        os.umask(previous_umask)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--backup-dir", type=Path, default=Path.home() / "backups")
    parser.add_argument("--keep", type=int, default=7)
    arguments = parser.parse_args()
    try:
        result = create_backup(arguments.project_dir, arguments.backup_dir, arguments.keep)
    except (OSError, ValueError, sqlite3.Error, tarfile.TarError, KeyError) as error:
        parser.exit(1, f"Помилка резервного копіювання: {error}\n")
    print(f"Резервну копію створено та перевірено: {result}")


if __name__ == "__main__":
    main()
