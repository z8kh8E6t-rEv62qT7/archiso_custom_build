#!/usr/bin/env python3
"""Validate a complete local AUR repository before using or publishing it."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import uuid

ROOT = Path(__file__).resolve().parent.parent
PACKAGES = {"rime-ice-pinyin-git": "https://github.com/iDvel/rime-ice"}
DATABASE = "custom-aur.db.tar.gz"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def package_info(path):
    result = subprocess.run(["bsdtar", "-xOf", str(path), ".PKGINFO"],
                            check=True, capture_output=True, text=True)
    return dict(line.split(" = ", 1) for line in result.stdout.splitlines()
                if " = " in line)


def validate(repo):
    repo = repo.resolve(strict=True)
    manifest = json.loads((repo / "manifest.json").read_text())
    records = manifest.get("packages", {})
    if set(records) != set(PACKAGES):
        raise ValueError("本地仓库必须包含雾凇拼音")
    package_metadata = {}
    for name, record in records.items():
        filename = record["filename"]
        if Path(filename).name != filename or not filename.startswith(name + "-"):
            raise ValueError("非法本地包文件名")
        package = repo / filename
        if package.is_symlink() or digest(package) != record["sha256"]:
            raise ValueError(f"AUR 包校验和不匹配：{name}")
        info = package_info(package)
        if info.get("pkgname") != name or info.get("arch") not in {"any", "x86_64"}:
            raise ValueError(f"AUR 包名或架构不匹配：{name}")
        if info.get("pkgver") != record["version"]:
            raise ValueError(f"AUR 包版本与记录不符：{name}")
        package_metadata[name] = info
    if digest(repo / DATABASE) != manifest["database_sha256"]:
        raise ValueError("AUR 仓库数据库校验和不匹配")
    if (repo / "custom-aur.db").resolve(strict=True) != repo / DATABASE:
        raise ValueError("AUR 仓库数据库链接不正确")
    with tarfile.open(repo / DATABASE) as archive:
        entries = [m for m in archive.getmembers() if m.name.endswith("/desc")]
        if len(entries) != len(PACKAGES):
            raise ValueError("本地仓库应只包含指定的 AUR 包")
        seen = set()
        for entry in entries:
            with archive.extractfile(entry) as stream:
                fields = stream.read().decode().split("\n\n")
            desc = {part.splitlines()[0]: part.splitlines()[1:] for part in fields if part.strip()}
            names = desc.get("%NAME%", [])
            if len(names) != 1 or names[0] not in records or names[0] in seen:
                raise ValueError("仓库记录与软件包不一致：%NAME%")
            name = names[0]
            seen.add(name)
            record = records[name]
            for key, value in {"%NAME%": name, "%VERSION%": record["version"],
                               "%FILENAME%": record["filename"], "%SHA256SUM%": record["sha256"],
                               "%ARCH%": package_metadata[name]["arch"]}.items():
                if desc.get(key) != [value]:
                    raise ValueError(f"仓库记录与软件包不一致：{name} {key}")
    return repo


def publish(repo, packages):
    repo = repo.resolve(strict=True)
    if not repo.is_relative_to(ROOT / "localrepo"):
        raise ValueError("仓库必须位于工程 localrepo 内")
    manifest = {"packages": {}, "database_sha256": digest(repo / DATABASE)}
    for filename, aur_commit, upstream_commit in packages:
        if Path(filename).name != filename:
            raise ValueError("非法本地包文件名")
        info = package_info(repo / filename)
        name = info["pkgname"]
        if name not in PACKAGES or name in manifest["packages"]:
            raise ValueError("AUR 包名不匹配或重复")
        manifest["packages"][name] = {
            "filename": filename, "version": info["pkgver"], "sha256": digest(repo / filename),
            "aur_url": f"https://aur.archlinux.org/{name}.git", "aur_commit": aur_commit,
            "upstream_url": PACKAGES[name], "upstream_commit": upstream_commit or None}
    (repo / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    validate(repo)
    # Publish only after validation; an ongoing ISO build retains its resolved generation.
    temporary = ROOT / "localrepo" / (".current-" + uuid.uuid4().hex)
    temporary.symlink_to(repo.relative_to(ROOT / "localrepo"))
    try:
        os.replace(temporary, ROOT / "localrepo/current")
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--print-path", action="store_true")
    pub = sub.add_parser("publish")
    pub.add_argument("repo")
    pub.add_argument("--package", nargs=3, action="append", required=True,
                     metavar=("FILENAME", "AUR_COMMIT", "UPSTREAM_COMMIT"))
    args = parser.parse_args()
    try:
        if args.command == "publish":
            publish(Path(args.repo), args.package)
        else:
            repo = validate(ROOT / "localrepo/current")
            print(repo if args.print_path else "本地 AUR 包和仓库校验通过。")
    except (OSError, ValueError, KeyError, IndexError, tarfile.TarError, subprocess.CalledProcessError) as exc:
        print(f"本地 AUR 仓库不可用：{exc}。请先以普通用户运行 ./build-aur.sh。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
