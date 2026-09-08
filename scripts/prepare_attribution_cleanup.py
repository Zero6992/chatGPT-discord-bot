#!/usr/bin/env python3
"""Prepare, verify and report a message-only cleanup in a NEW local mirror.

Never updates source refs, working trees or remote servers. Requires a destination
outside the source repository. The source bundle remains a recoverable backup.
"""

import argparse
import json
import subprocess
from pathlib import Path

TARGET_LINES = {
    "🤖 Generated with [Claude Code](https://claude.ai/code)".encode(),
    b"Co-Authored-By: Claude <noreply@anthropic.com>",
}


def git(repo: Path, *args: str, data: bytes | None = None) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        input=data,
        capture_output=True,
        check=True,
    ).stdout


def clean_message(message: bytes) -> bytes:
    return b"".join(
        line
        for line in message.splitlines(keepends=True)
        if line.rstrip(b"\r\n") not in TARGET_LINES
    )


def split_object(raw: bytes) -> tuple[list[bytes], bytes]:
    header, message = raw.split(b"\n\n", 1)
    fields: list[bytes] = []
    for line in header.split(b"\n"):
        if line.startswith(b" "):
            fields[-1] += b"\n" + line
        else:
            fields.append(line)
    return fields, message


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def refs(repo: Path) -> dict[str, str]:
    return dict(
        line.split(" ", 1)
        for line in git(repo, "for-each-ref", "--format=%(refname) %(objectname)")
        .decode()
        .splitlines()
    )


def prepare(source: Path, output: Path) -> dict:
    source, output = source.resolve(), output.resolve()
    if git(source, "rev-parse", "--is-bare-repository").strip() != b"true":
        source = Path(git(source, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    if output.is_relative_to(source) or output.exists():
        raise ValueError("Destination must be a new directory outside the source repository")
    before = refs(source)
    output.mkdir(parents=True, mode=0o700)
    bundle = output / "original.bundle"
    git(source, "bundle", "create", str(bundle), "--all")
    bundle.chmod(0o600)
    git(source, "bundle", "verify", str(bundle))
    mirror = output / "prepared.git"
    git(output, "clone", "--mirror", str(bundle), str(mirror))
    if refs(mirror) != before:
        raise ValueError("Mirror refs differ from backup source")
    mapping: dict[str, str] = {}
    targets = []
    dropped_signatures = []
    commits = git(mirror, "rev-list", "--all", "--reverse", "--topo-order").decode().splitlines()
    for oid in commits:
        raw = git(mirror, "cat-file", "commit", oid)
        fields, message = split_object(raw)
        new_message = clean_message(message)
        new_fields = [
            b"parent " + mapping[field[7:].decode()].encode()
            if field.startswith(b"parent ")
            else field
            for field in fields
        ]
        if new_message != message:
            targets.append(
                {
                    "commit": oid,
                    "removed_lines": [
                        line.decode() for line in message.splitlines() if line in TARGET_LINES
                    ],
                }
            )
        changed = new_message != message or new_fields != fields
        if changed:
            if any(field.startswith(b"mergetag ") for field in fields):
                raise ValueError(
                    "Changed commit contains a merge tag; manual signature review required"
                )
            if any(field.startswith((b"gpgsig ", b"gpgsig-sha256 ")) for field in fields):
                dropped_signatures.append(oid)
            new_fields = [
                field
                for field in new_fields
                if not field.startswith((b"gpgsig ", b"gpgsig-sha256 "))
            ]
        rewritten = b"\n".join(new_fields) + b"\n\n" + new_message
        mapping[oid] = (
            git(mirror, "hash-object", "-t", "commit", "-w", "--stdin", data=rewritten)
            .decode()
            .strip()
            if changed
            else oid
        )
        # Verify raw code tree, all human metadata and exact parent topology.
        actual_fields, actual_message = split_object(
            git(mirror, "cat-file", "commit", mapping[oid])
        )
        require(
            actual_fields == new_fields and actual_message == new_message,
            "Commit message/header verification failed",
        )
        require(
            [f for f in fields if f.startswith((b"tree ", b"author ", b"committer ", b"encoding "))]
            == [
                f
                for f in actual_fields
                if f.startswith((b"tree ", b"author ", b"committer ", b"encoding "))
            ],
            "Code tree or human metadata changed",
        )

    tags = {}
    dropped_tag_signatures = []

    def rewrite_object(oid: str) -> str:
        if oid in mapping:
            return mapping[oid]
        kind = git(mirror, "cat-file", "-t", oid).strip()
        if kind != b"tag":
            return oid
        fields, message = split_object(git(mirror, "cat-file", "tag", oid))
        target = next(f[7:].decode() for f in fields if f.startswith(b"object "))
        replacement = rewrite_object(target)
        if replacement == target:
            return oid
        new_fields = [
            b"object " + replacement.encode() if field.startswith(b"object ") else field
            for field in fields
        ]
        for marker in (
            b"-----BEGIN PGP SIGNATURE-----",
            b"-----BEGIN SSH SIGNATURE-----",
            b"-----BEGIN SIGNED MESSAGE-----",
        ):
            if marker in message:
                message = message.split(marker, 1)[0]
                dropped_tag_signatures.append(oid)
        new_oid = (
            git(
                mirror,
                "hash-object",
                "-t",
                "tag",
                "-w",
                "--stdin",
                data=b"\n".join(new_fields) + b"\n\n" + message,
            )
            .decode()
            .strip()
        )
        tags[oid] = new_oid
        return new_oid

    after = {ref: rewrite_object(oid) for ref, oid in before.items()}
    updates = b"".join(f"update {ref} {after[ref]} {oid}\n".encode() for ref, oid in before.items())
    git(mirror, "update-ref", "--stdin", data=updates)
    git(mirror, "fsck", "--full")
    require(refs(source) == before, "Source refs changed unexpectedly")
    require(refs(mirror) == after, "Prepared refs differ from expected mapping")
    require(
        len(git(mirror, "rev-list", "--all").splitlines()) == len(commits),
        "Commit topology/count changed",
    )
    for new_oid in set(mapping.values()):
        message = split_object(git(mirror, "cat-file", "commit", new_oid))[1]
        require(clean_message(message) == message, "Targeted attribution remains")
    report = {
        "source": str(source),
        "backup": str(bundle),
        "prepared_mirror": str(mirror),
        "published": False,
        "verified_commits": len(commits),
        "targeted_commits": targets,
        "changed_commits": sum(old != new for old, new in mapping.items()),
        "affected_refs": {
            ref: {"old": before[ref], "new": after[ref]}
            for ref in before
            if before[ref] != after[ref]
        },
        "removed_commit_signatures": dropped_signatures,
        "removed_tag_signatures": dropped_tag_signatures,
        "changed_tag_objects": tags,
        "verification": [
            "Source refs unchanged",
            "All code trees and raw human metadata preserved",
            "Exact parent topology preserved",
            "Only exact attribution lines removed from commit messages",
            "git fsck --full passed",
            "Backup bundle verified",
        ],
    }
    (output / "commit-map.json").write_text(json.dumps(mapping, indent=2) + "\n")
    (output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.source, args.output)
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "backup",
                    "prepared_mirror",
                    "verified_commits",
                    "changed_commits",
                    "affected_refs",
                    "published",
                )
            },
            indent=2,
        )
    )
