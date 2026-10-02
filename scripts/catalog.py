#!/usr/bin/env python3
"""Validate the offline catalog and generate deterministic Swift Package resources."""

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata
from urllib.parse import urlsplit

MARKER = "gewill/AppCatalog:1"
LOCK = ".appcatalog-manifest.json"
RESOURCE_PATH = "Sources/AppCatalog/Resources"
HEX = r"[0-9a-f]{64}"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key!r}")
        result[key] = value
    return result


def read_json(path):
    def reject(value):
        raise ValueError(f"Invalid JSON constant: {value}")
    return json.loads(path.read_bytes(), object_pairs_hook=unique_object, parse_constant=reject)


def fields(value, expected, label):
    require(isinstance(value, dict) and set(value) == set(expected.split()), f"Invalid {label} fields")


def string(value, maximum, label):
    require(isinstance(value, str) and 0 < len(value) <= maximum
            and value.strip() == value
            and all(unicodedata.category(c) not in {"Cc", "Cs"} for c in value),
            f"Invalid {label}")


def relative(root, value):
    require(isinstance(value, str) and value and not value.startswith("/")
            and "\\" not in value and "\x00" not in value
            and all(part not in {"", ".", "..", ".git"} for part in value.split("/")),
            f"Unsafe relative path: {value!r}")
    result = root
    for part in value.split("/"):
        result = result / part
        require(not result.is_symlink(), f"Symlink is not allowed: {result}")
    require(result.resolve().is_relative_to(root.resolve()), f"Path escapes root: {value}")
    return result


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate(root):
    catalog = read_json(relative(root, "catalog.json"))
    fields(catalog, "schemaVersion sourceLanguage locales apps", "catalog")
    require(type(catalog["schemaVersion"]) is int and catalog["schemaVersion"] == 1,
            "Unsupported catalog schemaVersion")
    require(catalog["sourceLanguage"] == "en", "sourceLanguage must be en")
    locales = catalog["locales"]
    require(isinstance(locales, list) and 0 < len(locales) <= 100
            and all(isinstance(x, str) and re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", x)
                    for x in locales), "Invalid locales")
    require(len(set(locales)) == len(locales) and "en" in locales, "Duplicate locales or missing en")
    require(isinstance(catalog["apps"], list) and 0 < len(catalog["apps"]) <= 1000, "Invalid apps")
    ids, store_ids, keys, icons = set(), set(), {}, {}
    for app in catalog["apps"]:
        fields(app, "id appStoreID name subtitle localizations icon source", "app")
        require(isinstance(app["id"], str) and len(app["id"]) <= 64
                and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", app["id"]), "Invalid app id")
        require(app["id"] not in ids, f"Duplicate app id: {app['id']}")
        ids.add(app["id"])
        require(isinstance(app["appStoreID"], str)
                and re.fullmatch(r"[1-9][0-9]{0,19}", app["appStoreID"]), "Invalid appStoreID")
        require(app["appStoreID"] not in store_ids, f"Duplicate appStoreID: {app['appStoreID']}")
        store_ids.add(app["appStoreID"])
        translations = app["localizations"]
        require(isinstance(translations, dict) and set(translations) == set(locales),
                f"Locale coverage differs: {app['id']}")
        for locale, text in translations.items():
            fields(text, "name subtitle", f"{app['id']}/{locale}")
            for field in ("name", "subtitle"):
                string(text[field], 120 if field == "name" else 240, f"{app['id']}/{locale}/{field}")
        for field in ("name", "subtitle"):
            string(app[field], 120 if field == "name" else 240, f"{app['id']}/{field}")
            require(translations["en"][field] == app[field], f"English source differs: {app['id']}/{field}")
            values = {locale: translations[locale][field] for locale in locales}
            require(app[field] not in keys or keys[app[field]] == values,
                    f"Conflicting localization key: {app[field]!r}")
            keys[app[field]] = values
        icon = app["icon"]
        fields(icon, "path sha256", "icon")
        path = relative(root, icon["path"])
        require(icon["path"].startswith("icons/"), "Icon must be under icons/")
        require(isinstance(icon["sha256"], str) and re.fullmatch(HEX, icon["sha256"]), "Invalid icon sha256")
        require(path.is_file() and path.stat().st_size <= 20_000_000, f"Invalid icon file: {path}")
        data = path.read_bytes()
        require(digest(data) == icon["sha256"], f"Icon hash mismatch: {icon['path']}")
        valid_png = path.suffix == ".png" and data.startswith(b"\x89PNG\r\n\x1a\n")
        valid_jpeg = path.suffix in {".jpg", ".jpeg"} and data.startswith(b"\xff\xd8\xff")
        require(valid_png or valid_jpeg, f"Invalid PNG/JPEG signature or extension: {icon['path']}")
        icons[app["id"]] = data
        source = app["source"]
        fields(source, "url version retrievedAt originalSHA256 transform", "source")
        string(source["url"], 4096, "source URL")
        url = urlsplit(source["url"])
        require(url.scheme == "https" and url.hostname and not url.username and not url.password
                and not any(c.isspace() or c == "\\" for c in source["url"]),
                "Source URL must use https without credentials")
        string(source["version"], 64, "source version")
        string(source["transform"], 1024, "source transform")
        require(isinstance(source["retrievedAt"], str)
                and re.fullmatch(r"\d{4}-\d{2}-\d{2}", source["retrievedAt"]), "Invalid retrievedAt")
        date.fromisoformat(source["retrievedAt"])
        require(isinstance(source["originalSHA256"], str)
                and re.fullmatch(HEX, source["originalSHA256"]), "Invalid originalSHA256")
    return catalog, icons


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def strings_literal(value):
    """JSON escaping is compatible with .strings for validated, control-free metadata."""
    return json.dumps(value, ensure_ascii=False)


def prepare(root, catalog, icons):
    files = {"catalog.json": json_bytes(catalog)}
    strings = {locale: {} for locale in catalog["locales"]}
    for app in catalog["apps"]:
        image_path = f"Assets.xcassets/AppCatalog-{app['id']}.imageset/"
        filename = "icon" + Path(app["icon"]["path"]).suffix
        files[image_path + filename] = icons[app["id"]]
        files[image_path + "Contents.json"] = json_bytes({"images": [{"filename": filename, "idiom": "universal"}],
                                                         "info": {"author": "xcode", "version": 1}})
        for locale in catalog["locales"]:
            for field in ("name", "subtitle"):
                strings[locale][app[field]] = app["localizations"][locale][field]
    files["Assets.xcassets/Contents.json"] = json_bytes({"info": {"author": "xcode", "version": 1}})
    for locale, values in strings.items():
        lines = ["/* Generated by AppCatalog. Do not edit. */"]
        lines += [f"{strings_literal(key)} = {strings_literal(values[key])};" for key in sorted(values)]
        files[f"{locale}.lproj/AppCatalog.strings"] = ("\n".join(lines) + "\n").encode()
    files[LOCK] = json_bytes({"schemaVersion": 1, "generator": MARKER,
                              "files": {name: digest(data) for name, data in files.items()}})
    return files


def inventory(output):
    files, directories = {}, []
    if output.exists():
        require(output.is_dir(), f"Output is not a directory: {output}")
        def visit(folder):
            for path in sorted(folder.iterdir()):
                require(not path.is_symlink(), f"Symlink in output: {path}")
                if path.is_dir():
                    directories.append(path)
                    visit(path)
                else:
                    require(path.is_file(), f"Non-regular output file: {path}")
                    files[path.relative_to(output).as_posix()] = path.read_bytes()
        visit(output)
    return files, directories


def generate(root, check=False):
    catalog, icons = validate(root)
    expected = prepare(root, catalog, icons)
    output = relative(root, RESOURCE_PATH)
    current, directories = inventory(output)
    changed = sorted(name for name in expected.keys() | current.keys() if expected.get(name) != current.get(name))
    wanted_dirs = {p.as_posix() for name in expected for p in Path(name).parents if p != Path(".")}
    stale_dirs = [p for p in directories if p.relative_to(output).as_posix() not in wanted_dirs]
    if check:
        if changed or stale_dirs:
            print("Generated output differs: " + ", ".join(changed + [p.relative_to(output).as_posix() + "/" for p in stale_dirs]), file=sys.stderr)
            return 1
        print(f"Up to date: {output}")
        return 0
    if current:
        require(LOCK in current, "Refusing to overwrite output without a generated lock")
        old = read_json(output / LOCK)
        require(isinstance(old, dict) and old.get("generator") == MARKER
                and type(old.get("schemaVersion")) is int and old["schemaVersion"] == 1
                and isinstance(old.get("files"), dict), "Invalid generated lock marker")
        for name, sha in old["files"].items():
            relative(output, name)
            require(isinstance(sha, str) and re.fullmatch(HEX, sha), "Invalid generated lock hash")
        owned = set(old["files"]) | {LOCK}
    else:
        owned = set()
    require(not (set(current) - owned), "Refusing to remove unrecognized output files")
    for name in expected:
        path = relative(output, name)
        require(not path.exists() or path.is_file(), f"Expected output file: {path}")
        for parent in path.parents:
            if parent == output.parent:
                break
            require(not parent.exists() or parent.is_dir(), f"Expected output directory: {parent}")
    for name in set(current) - set(expected):
        require(digest(current[name]) == old["files"][name], f"Refusing to delete modified generated file: {name}")
    # Remove only paths named in the prior generated manifest; never recursively delete a directory.
    for name in sorted(set(current) - set(expected)):
        (output / name).unlink()
    for path in sorted(stale_dirs, key=lambda p: len(p.parts), reverse=True):
        if not any(path.iterdir()):
            path.rmdir()
    for name, data in expected.items():
        path = relative(output, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        if current.get(name) != data:
            path.write_bytes(data)
    print(f"Generated {len(catalog['apps'])} apps in {output}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    gen = sub.add_parser("generate")
    gen.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    try:
        if args.command == "validate":
            catalog, _ = validate(root)
            print(f"Valid: {len(catalog['apps'])} apps, {len(catalog['locales'])} locales")
            return 0
        return generate(root, args.check)
    except (ValueError, OSError) as error:
        print(f"catalog: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
