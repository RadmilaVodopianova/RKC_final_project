from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.test import SimpleTestCase
from PIL import Image

from .thumbnails import catalog_thumbnail


class CatalogThumbnailTests(SimpleTestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.storage = FileSystemStorage(location=self.folder.name, base_url="/media/")

    def upload(self, size=(1086, 1448), color="orange", name="product.png"):
        output = BytesIO()
        Image.new("RGB", size, color).save(output, "PNG")
        self.storage.save(name, ContentFile(output.getvalue()))
        return SimpleNamespace(name=name, storage=self.storage, url=self.storage.url(name))

    def test_responsive_sizes_preserve_original_and_reuse_cache(self):
        image = self.upload()
        original = Path(self.storage.path(image.name)).read_bytes()
        result = catalog_thumbnail(image)
        files = list(Path(self.folder.name, "catalog_thumbnails").glob("*.webp"))
        self.assertEqual(len(files), 3)
        for path in files:
            with Image.open(path) as thumb:
                self.assertIn(thumb.size, [(360, 450), (720, 900), (1080, 1350)])
        times = {path: path.stat().st_mtime_ns for path in files}
        self.assertEqual(catalog_thumbnail(image), result)
        self.assertEqual(times, {path: path.stat().st_mtime_ns for path in files})
        self.assertEqual(Path(self.storage.path(image.name)).read_bytes(), original)

    def test_replaced_upload_gets_new_urls(self):
        image = self.upload()
        before = catalog_thumbnail(image)
        self.storage.delete(image.name)
        self.upload(color="blue", name=image.name)
        self.assertNotEqual(catalog_thumbnail(image)["src"], before["src"])

    def test_small_upload_is_never_enlarged(self):
        result = catalog_thumbnail(self.upload(size=(100, 125)))
        self.assertTrue(result["srcset"].endswith(" 100w"))
        self.assertNotIn(",", result["srcset"])

    def test_missing_image_uses_original_url(self):
        image = SimpleNamespace(name="missing.png", url="/media/missing.png", storage=self.storage)
        with self.assertLogs("core.thumbnails", level="WARNING"):
            result = catalog_thumbnail(image)
        self.assertEqual(result["src"], image.url)
        self.assertEqual(result["srcset"], "")

    def test_empty_image(self):
        self.assertEqual(catalog_thumbnail(None)["src"], "")
