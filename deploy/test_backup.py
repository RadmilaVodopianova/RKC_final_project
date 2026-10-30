from contextlib import closing
import io
import os
from pathlib import Path
import sqlite3
import stat
import tarfile
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from backup import create_backup, verify_archive


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.photos = self.project / "media/products"
        self.photos.mkdir(parents=True)
        (self.photos / "Ковбаса.jpg").write_bytes(b"original photo")
        (self.project / ".env").write_bytes(b"SECRET_KEY=test-only-secret\n")
        cache = self.project / "media/catalog_thumbnails"
        cache.mkdir()
        (cache / "preview.webp").write_bytes(b"generated preview")
        with closing(sqlite3.connect(self.project / "db.sqlite3")) as database:
            database.execute("CREATE TABLE orders (number INTEGER, name TEXT)")
            database.execute("INSERT INTO orders VALUES (?, ?)", (9, "Заявка"))
            database.commit()
        self.backups = self.root / "backups"

    def test_archive_restores_database_settings_and_original_photo(self):
        original = (self.project / "db.sqlite3").read_bytes()
        result = create_backup(self.project, self.backups)
        verify_archive(result)
        with tarfile.open(result, "r:gz") as archive:
            self.assertEqual(
                set(archive.getnames()),
                {"backup-info.json", "db.sqlite3", ".env", "media/products/Ковбаса.jpg"},
            )
            restored = self.root / "restored.sqlite3"
            restored.write_bytes(archive.extractfile("db.sqlite3").read())
            self.assertEqual(archive.extractfile(".env").read(), b"SECRET_KEY=test-only-secret\n")
            self.assertEqual(archive.extractfile("media/products/Ковбаса.jpg").read(), b"original photo")
        with closing(sqlite3.connect(restored)) as database:
            self.assertEqual(database.execute("SELECT * FROM orders").fetchall(), [(9, "Заявка")])
            self.assertEqual(database.execute("PRAGMA integrity_check").fetchone(), ("ok",))
        self.assertEqual((self.project / "db.sqlite3").read_bytes(), original)

    def test_committed_wal_data_is_included_while_database_is_open(self):
        with closing(sqlite3.connect(self.project / "db.sqlite3")) as database:
            database.execute("PRAGMA journal_mode=WAL")
            database.execute("INSERT INTO orders VALUES (?, ?)", (10, "Нова заявка"))
            database.commit()
            self.assertTrue((self.project / "db.sqlite3-wal").exists())
            result = create_backup(self.project, self.backups)
            with tarfile.open(result, "r:gz") as archive:
                restored = self.root / "wal-restored.sqlite3"
                restored.write_bytes(archive.extractfile("db.sqlite3").read())
            with closing(sqlite3.connect(restored)) as snapshot:
                self.assertEqual(snapshot.execute("SELECT COUNT(*) FROM orders").fetchone(), (2,))

    def test_retention_keeps_latest_archives_and_preserves_other_files(self):
        first = create_backup(self.project, self.backups, keep=2)
        foreign = self.backups / "rkc-backup-important.tar.gz"
        foreign.write_bytes(b"do not delete")
        second = create_backup(self.project, self.backups, keep=2)
        third = create_backup(self.project, self.backups, keep=2)
        self.assertFalse(first.exists())
        self.assertTrue(second.exists())
        self.assertTrue(third.exists())
        self.assertEqual(foreign.read_bytes(), b"do not delete")

    def test_failed_verification_preserves_previous_backup_and_removes_partial(self):
        previous = create_backup(self.project, self.backups, keep=1)
        with patch("backup.verify_archive", side_effect=ValueError("failed verification")):
            with self.assertRaises(ValueError):
                create_backup(self.project, self.backups, keep=1)
        self.assertTrue(previous.exists())
        self.assertEqual(list(self.backups.glob("*.tar.gz")), [previous])
        self.assertFalse(list(self.backups.glob("*.partial")))

    def test_missing_environment_prevents_incomplete_backup(self):
        (self.project / ".env").unlink()
        with self.assertRaises(ValueError):
            create_backup(self.project, self.backups)
        self.assertFalse(self.backups.exists())

    def test_backup_directory_inside_project_is_rejected(self):
        with self.assertRaises(ValueError):
            create_backup(self.project, self.project / "backups")
        self.assertFalse((self.project / "backups").exists())

    def test_modified_photo_payload_is_rejected(self):
        valid = create_backup(self.project, self.backups)
        changed = self.root / "changed.tar.gz"
        with tarfile.open(valid, "r:gz") as source, tarfile.open(changed, "w:gz") as target:
            for member in source.getmembers():
                data = source.extractfile(member).read()
                if member.name.endswith(".jpg"):
                    data = b"changed photo"
                member.size = len(data)
                target.addfile(member, io.BytesIO(data))
        with self.assertRaisesRegex(ValueError, "Пошкоджено файл"):
            verify_archive(changed)

    @unittest.skipUnless(os.name == "posix", "POSIX permissions")
    def test_backup_permissions_are_private(self):
        result = create_backup(self.project, self.backups)
        self.assertEqual(stat.S_IMODE(self.backups.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(result.stat().st_mode), 0o600)

    @unittest.skipUnless(os.name == "posix", "POSIX symbolic links")
    def test_symbolic_link_to_external_photo_is_rejected(self):
        external = self.root / "external.jpg"
        external.write_bytes(b"private external file")
        (self.photos / "link.jpg").symlink_to(external)
        with self.assertRaises(ValueError):
            create_backup(self.project, self.backups)


if __name__ == "__main__":
    unittest.main()
