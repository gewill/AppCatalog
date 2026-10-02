"""Behavioral tests for offline catalog validation and safe resource generation."""

import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("catalog", Path(__file__).resolve().parents[1] / "scripts/catalog.py")
catalog = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(catalog)


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "icons").mkdir()
        image = b"\x89PNG\r\n\x1a\nfixture"
        (self.root / "icons/alpha.png").write_bytes(image)
        app = {
            "id": "alpha", "appStoreID": "123", "name": "Alpha", "subtitle": "Network tools",
            "localizations": {
                "en": {"name": "Alpha", "subtitle": "Network tools"},
                "zh-Hans": {"name": "工具", "subtitle": "网络工具"},
            },
            "icon": {"path": "icons/alpha.png", "sha256": catalog.digest(image)},
            "source": {"url": "https://example.com/icon.png", "version": "1.0", "retrievedAt": "2026-10-02",
                       "originalSHA256": catalog.digest(image), "transform": "none"},
        }
        self.data = {"schemaVersion": 1, "sourceLanguage": "en", "locales": ["en", "zh-Hans"], "apps": [app]}
        self.write()
        self.output = self.root / catalog.RESOURCE_PATH

    def write(self):
        (self.root / "catalog.json").write_bytes(catalog.json_bytes(self.data))

    def app(self):
        return self.data["apps"][0]

    def generate(self, check=False):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return catalog.generate(self.root, check)

    def snapshot(self):
        if not self.output.exists():
            return None
        return {str(p.relative_to(self.output)): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.output.rglob("*") if p.is_file()}

    def test_valid_catalog_and_variable_locale_count(self):
        parsed, icons = catalog.validate(self.root)
        self.assertEqual(parsed, self.data)
        self.assertEqual(catalog.digest(icons["alpha"]), self.app()["icon"]["sha256"])

    def test_duplicate_json_keys_and_constants(self):
        for raw in ('{"schemaVersion":1,"schemaVersion":1}', '{"schemaVersion":NaN}'):
            with self.subTest(raw=raw):
                (self.root / "catalog.json").write_text(raw)
                with self.assertRaises(ValueError):
                    catalog.validate(self.root)

    def test_schema_and_metadata_failures(self):
        original = copy.deepcopy(self.data)
        edits = [lambda x: x.update(schemaVersion=True), lambda x: x.update(sourceLanguage="fr"),
                 lambda x: x.update(apps=[]), lambda x: x.update(unknown=True),
                 lambda x: x["apps"][0].update(appStoreID=123),
                 lambda x: x["apps"][0].update(id="../alpha"),
                 lambda x: x["apps"][0].update(name="x" * 121),
                 lambda x: x["apps"][0]["source"].update(retrievedAt="2026-02-30"),
                 lambda x: x["apps"][0]["source"].update(originalSHA256="bad"),
                 lambda x: x["apps"][0]["source"].update(version=""),
                 lambda x: x["apps"][0]["source"].update(url="http://example.com/icon.png"),
                 lambda x: x["apps"][0]["source"].update(url="https://user:password@example.com/icon.png"),
                 lambda x: x["apps"][0]["source"].update(url="https://bad host/icon.png")]
        for edit in edits:
            self.data = copy.deepcopy(original)
            edit(self.data)
            self.write()
            with self.subTest(data=self.data), self.assertRaises(ValueError):
                catalog.validate(self.root)

    def test_duplicate_ids_and_store_ids(self):
        for field in ("id", "appStoreID"):
            second = copy.deepcopy(self.app())
            second.update(id="beta", appStoreID="456")
            second[field] = self.app()[field]
            self.data["apps"] = [self.app(), second]
            self.write()
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "Duplicate"):
                catalog.validate(self.root)

    def test_locale_coverage_and_english_source(self):
        original = copy.deepcopy(self.data)
        for edit in [lambda: self.data["locales"].append("en"),
                     lambda: self.data["locales"].remove("en"),
                     lambda: self.data["locales"].append("../fr"),
                     lambda: self.app()["localizations"].pop("zh-Hans"),
                     lambda: self.app()["localizations"]["en"].update(name="Other"),
                     lambda: self.app()["localizations"]["zh-Hans"].update(name="bad\nname")]:
            self.data = copy.deepcopy(original)
            edit()
            self.write()
            with self.subTest(data=self.data), self.assertRaises(ValueError):
                catalog.validate(self.root)

    def test_key_conflicts_fail_but_identical_reuse_is_valid(self):
        second = copy.deepcopy(self.app())
        second.update(id="beta", appStoreID="456")
        self.data["apps"].append(second)
        self.write()
        catalog.validate(self.root)
        second["localizations"]["zh-Hans"]["name"] = "不同"
        self.write()
        with self.assertRaisesRegex(ValueError, "Conflicting localization key"):
            catalog.validate(self.root)

    def test_hash_and_signature_failures(self):
        path = self.root / "icons/alpha.png"
        path.write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            catalog.validate(self.root)
        self.app()["icon"]["sha256"] = catalog.digest(path.read_bytes())
        self.write()
        with self.assertRaisesRegex(ValueError, "signature"):
            catalog.validate(self.root)

    def test_jpeg_extension_and_signature(self):
        data = b"\xff\xd8\xffjpeg"
        (self.root / "icons/alpha.jpg").write_bytes(data)
        self.app()["icon"] = {"path": "icons/alpha.jpg", "sha256": catalog.digest(data)}
        self.write()
        catalog.validate(self.root)
        self.generate()
        self.assertEqual((self.output / "Assets.xcassets/AppCatalog-alpha.imageset/icon.jpg").read_bytes(), data)

    def test_unsafe_icon_paths(self):
        for path in ("../alpha.png", "/tmp/alpha.png", "icons/../alpha.png", "icons//alpha.png", "icons\\alpha.png"):
            self.app()["icon"]["path"] = path
            self.write()
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "Unsafe"):
                catalog.validate(self.root)

    def test_input_symlink_escape(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "alpha.png"
            target.write_bytes((self.root / "icons/alpha.png").read_bytes())
            (self.root / "icons/alpha.png").unlink()
            (self.root / "icons/alpha.png").symlink_to(target)
            with self.assertRaisesRegex(ValueError, "Symlink"):
                catalog.validate(self.root)

    def test_output_symlinks_are_rejected_without_writing(self):
        with tempfile.TemporaryDirectory() as outside:
            (self.root / "Sources").symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "Symlink"):
                self.generate()
            self.assertEqual(list(Path(outside).iterdir()), [])

    def test_generated_content_order_and_escaping(self):
        self.app()["name"] = 'A "quoted" \\ Ω 🚀'
        self.app()["localizations"]["en"]["name"] = self.app()["name"]
        self.write()
        self.generate()
        actual = (self.output / "en.lproj/AppCatalog.strings").read_text()
        self.assertIn('"A \\"quoted\\" \\\\ Ω 🚀" = "A \\"quoted\\" \\\\ Ω 🚀";', actual)
        self.assertLess(actual.index('"A '), actual.index('"Network tools"'))
        self.assertEqual(json.loads((self.output / "catalog.json").read_bytes()), self.data)
        contents = json.loads((self.output / "Assets.xcassets/AppCatalog-alpha.imageset/Contents.json").read_bytes())
        self.assertEqual(contents["images"], [{"filename": "icon.png", "idiom": "universal"}])

    def test_check_is_read_only_and_generation_is_idempotent(self):
        self.assertEqual(self.generate(check=True), 1)
        self.assertIsNone(self.snapshot())
        self.assertEqual(self.generate(), 0)
        before = self.snapshot()
        self.assertEqual(self.generate(check=True), 0)
        self.assertEqual(self.generate(), 0)
        self.assertEqual(self.snapshot(), before)
        (self.output / "en.lproj/AppCatalog.strings").write_text("drift")
        drifted = self.snapshot()
        self.assertEqual(self.generate(check=True), 1)
        self.assertEqual(self.snapshot(), drifted)

    def test_unknown_extra_files_detected_and_preserved(self):
        self.generate()
        (self.output / "notes.txt").write_text("Keep me")
        before = self.snapshot()
        self.assertEqual(self.generate(check=True), 1)
        with self.assertRaisesRegex(ValueError, "unrecognized"):
            self.generate()
        self.assertEqual(self.snapshot(), before)

    def test_owned_stale_resources_removed_and_modified_ones_preserved(self):
        self.generate()
        stale = self.output / "zh-Hans.lproj/AppCatalog.strings"
        original = stale.read_bytes()
        self.data["locales"].remove("zh-Hans")
        self.app()["localizations"].pop("zh-Hans")
        self.write()
        self.assertEqual(self.generate(check=True), 1)
        stale.write_text("User edit")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "modified generated file"):
            self.generate()
        self.assertEqual(self.snapshot(), before)
        stale.write_bytes(original)
        self.generate()
        self.assertFalse(stale.parent.exists())
        self.assertEqual(self.generate(check=True), 0)

    def test_unmarked_output_refused(self):
        self.output.mkdir(parents=True)
        (self.output / "notes.txt").write_text("User data")
        before = self.snapshot()
        self.assertEqual(self.generate(check=True), 1)
        with self.assertRaisesRegex(ValueError, "without a generated lock"):
            self.generate()
        self.assertEqual(self.snapshot(), before)

    def test_invalid_source_does_not_change_existing_output(self):
        self.generate()
        before = self.snapshot()
        self.app()["localizations"]["en"]["name"] = "Wrong"
        self.write()
        with self.assertRaises(ValueError):
            self.generate()
        self.assertEqual(self.snapshot(), before)

    def test_output_type_conflicts_fail_before_any_writes(self):
        self.generate()
        path = self.output / "en.lproj/AppCatalog.strings"
        path.unlink()
        path.mkdir()
        self.app()["localizations"]["zh-Hans"]["name"] = "新名字"
        self.write()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "Expected output file"):
            self.generate()
        self.assertEqual(self.snapshot(), before)

    def test_malicious_manifest_paths_rejected(self):
        self.generate()
        lock = self.output / catalog.LOCK
        value = json.loads(lock.read_bytes())
        value["files"]["../../outside.txt"] = "0" * 64
        lock.write_bytes(catalog.json_bytes(value))
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            self.generate()
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
