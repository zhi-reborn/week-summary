from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKSUM_FILE = "SHA256SUMS"
CHECKSUM_LINE = re.compile(r"^([0-9a-fA-F]{64})  ([^/\\]+)$")
WINDOWS_VERSION = re.compile(r'^\s*#define MyAppVersion "([^"]+)"$', re.MULTILINE)


class ReleaseCheckError(RuntimeError):
    """The release inputs do not satisfy the publication gate."""


@dataclass(frozen=True)
class ReleaseResult:
    version: str
    artifact_count: int
    checksum_count: int


def read_declared_versions(root: Path) -> dict[str, str]:
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    with (root / "pyproject.toml").open("rb") as stream:
        backend = str(tomllib.load(stream)["project"]["version"])
    frontend = str(
        json.loads((root / "frontend" / "package.json").read_text(encoding="utf-8"))["version"]
    )
    iss = (root / "packaging" / "windows" / "weekly-report-assistant.iss").read_text(
        encoding="utf-8-sig"
    )
    windows_match = WINDOWS_VERSION.search(iss)
    if windows_match is None:
        raise ReleaseCheckError("Windows 安装器未声明 MyAppVersion")
    return {
        "VERSION": version,
        "backend": backend,
        "frontend": frontend,
        "windows_installer": windows_match.group(1),
    }


def expected_artifact_names(version: str) -> tuple[str, str, str]:
    return (
        f"WeeklyReportAssistant-{version}-windows-x64.exe",
        f"weekly-report-assistant_{version}_amd64.deb",
        f"weekly-report-assistant-{version}-linux-x64.tar.gz",
    )


def _validated_version(root: Path) -> str:
    versions = read_declared_versions(root)
    if not versions["VERSION"]:
        raise ReleaseCheckError("VERSION 不能为空")
    if len(set(versions.values())) != 1:
        details = ", ".join(f"{name}={value}" for name, value in versions.items())
        raise ReleaseCheckError(f"版本声明不一致：{details}")
    return versions["VERSION"]


def _package_files(installer_dir: Path) -> set[str]:
    if not installer_dir.is_dir():
        raise ReleaseCheckError(f"安装包目录不存在：{installer_dir}")
    return {
        item.name
        for item in installer_dir.iterdir()
        if item.is_file()
        and (item.name.endswith(".exe") or item.name.endswith(".deb") or item.name.endswith(".tar.gz"))
    }


def _validate_artifact_set(installer_dir: Path, version: str) -> tuple[str, str, str]:
    expected = expected_artifact_names(version)
    actual = _package_files(installer_dir)
    if actual != set(expected):
        missing = sorted(set(expected) - actual)
        unexpected = sorted(actual - set(expected))
        raise ReleaseCheckError(f"安装包集合不匹配：missing={missing}, unexpected={unexpected}")
    return expected


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_checksums(installer_dir: Path, version: str) -> Path:
    artifacts = _validate_artifact_set(installer_dir, version)
    manifest = installer_dir / CHECKSUM_FILE
    content = "".join(f"{_sha256(installer_dir / name)}  {name}\n" for name in artifacts)
    manifest.write_text(content, encoding="utf-8", newline="\n")
    return manifest


def _read_checksums(manifest: Path) -> dict[str, str]:
    if not manifest.is_file():
        raise ReleaseCheckError(f"缺少校验清单：{manifest}")
    checksums: dict[str, str] = {}
    for line_number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), start=1):
        match = CHECKSUM_LINE.fullmatch(line)
        if match is None or match.group(2) in checksums:
            raise ReleaseCheckError(f"SHA256SUMS 第 {line_number} 行格式无效")
        checksums[match.group(2)] = match.group(1).lower()
    return checksums


def validate_release(root: Path, installer_dir: Path) -> ReleaseResult:
    version = _validated_version(root)
    artifacts = _validate_artifact_set(installer_dir, version)
    checksums = _read_checksums(installer_dir / CHECKSUM_FILE)
    if set(checksums) != set(artifacts):
        raise ReleaseCheckError("SHA256SUMS 条目与安装包集合不一致")
    for name in artifacts:
        actual = _sha256(installer_dir / name)
        if not hmac.compare_digest(actual, checksums[name]):
            raise ReleaseCheckError(f"SHA-256 校验失败：{name}")
    return ReleaseResult(version, len(artifacts), len(checksums))


def main() -> None:
    parser = argparse.ArgumentParser(description="校验发布版本、安装包集合与 SHA-256")
    parser.add_argument("installer_dir", type=Path)
    parser.add_argument(
        "--write-checksums",
        action="store_true",
        help="为已收集的三个安装包生成 SHA256SUMS，然后继续校验",
    )
    arguments = parser.parse_args()
    try:
        version = _validated_version(ROOT)
        if arguments.write_checksums:
            write_checksums(arguments.installer_dir, version)
        result = validate_release(ROOT, arguments.installer_dir)
    except (KeyError, OSError, ReleaseCheckError, tomllib.TOMLDecodeError) as error:
        print(f"RELEASE_FAILED {error}", file=sys.stderr)
        raise SystemExit(1) from error
    print(
        f"RELEASE_OK version={result.version} artifacts={result.artifact_count} "
        "checksums=valid"
    )


if __name__ == "__main__":
    main()
