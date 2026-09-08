import hashlib
import json
from dataclasses import replace

import pytest

from src.cli import DESKTOP_ISOLATION_PROBE, DockerRunner, ProcessResult
from src.config import Backend, load_settings, verified_seccomp_profile
from src.domain import BotError


@pytest.fixture
def desktop_model(model, tmp_path):
    profile = tmp_path / "seccomp.json"
    profile.write_text(
        json.dumps(
            {
                "defaultAction": "SCMP_ACT_ERRNO",
                "syscalls": [{"names": ["exit", "exit_group"], "action": "SCMP_ACT_ALLOW"}],
            }
        )
    )
    backend = Backend(
        "desktop",
        "codex-cli",
        auth="account",
        owner_id=4,
        auth_profile=str(tmp_path / "account"),
        image="sha256:" + "1" * 64,
        cli_version="fixture-version",
        network="fixture-internal",
        proxy_url="http://egress:3128",
        docker_socket="/var/run/docker.sock",
        docker_mode="desktop",
        seccomp_profile=str(profile),
        seccomp_sha256=hashlib.sha256(profile.read_bytes()).hexdigest(),
    )
    return replace(model, backend=backend, parameters={})


def desktop_config(model):
    backend = model.backend
    fields = "\n".join(
        f"{key} = {json.dumps(value)}" for key, value in backend.__dict__.items() if key != "name"
    )
    return (
        '[bot]\ndefault_model = "cli"\nallowed_user_ids = [4]\n'
        "[backends.desktop]\n" + fields + "\n"
        '[models.cli]\nbackend = "desktop"\nmodel = "fixture-model"\ncapabilities = ["chat"]\n'
    )


def test_desktop_configuration_is_explicit_and_resolves_profile(desktop_model, tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(
        desktop_config(desktop_model).replace(desktop_model.backend.seccomp_profile, "seccomp.json")
    )
    configured = load_settings(path).models["cli"].backend
    assert configured.docker_mode == "desktop"
    assert configured.seccomp_profile == desktop_model.backend.seccomp_profile
    assert verified_seccomp_profile(configured) == configured.seccomp_profile


@pytest.mark.parametrize(
    "mutation", ["mode", "socket", "hash", "default_allow", "missing", "shared"]
)
def test_unsafe_desktop_configuration_rejected(desktop_model, tmp_path, mutation):
    model = desktop_model
    if mutation == "mode":
        model = replace(model, backend=replace(model.backend, docker_mode="host"))
    elif mutation == "socket":
        model = replace(model, backend=replace(model.backend, docker_socket="tcp://localhost:2375"))
    elif mutation == "hash":
        model = replace(model, backend=replace(model.backend, seccomp_sha256="0" * 64))
    elif mutation == "default_allow":
        profile = tmp_path / "seccomp.json"
        profile.write_text('{"defaultAction":"SCMP_ACT_ALLOW","syscalls":[]}')
        model = replace(
            model,
            backend=replace(
                model.backend, seccomp_sha256=hashlib.sha256(profile.read_bytes()).hexdigest()
            ),
        )
    elif mutation == "missing":
        (tmp_path / "seccomp.json").unlink()
    text = desktop_config(model)
    if mutation == "shared":
        text = text.replace("allowed_user_ids = [4]", "allowed_user_ids = [4, 9]")
    path = tmp_path / "config.toml"
    path.write_text(text)
    with pytest.raises(BotError):
        load_settings(path)


async def run_preflight(model, *, runtime_changes=None, isolation=None):
    runtime = {
        "OperatingSystem": "Docker Desktop",
        "SecurityOptions": ["name=seccomp,profile=unconfined"],
        "CgroupDriver": "cgroupfs",
        "CgroupVersion": "2",
        "MemoryLimit": True,
        "CpuCfsQuota": True,
        "PidsLimit": True,
        **(runtime_changes or {}),
    }
    calls = []
    runner = DockerRunner(model, 10)

    async def docker(argv, **kwargs):
        calls.append(argv)
        if argv[1] == "info":
            return ProcessResult(0, json.dumps(runtime).encode(), b"")
        if argv[1] == "network":
            return ProcessResult(0, b'[{"Internal":true}]', b"")
        if argv[1] == "image":
            return ProcessResult(
                0,
                b'[{"Config":{"Labels":{"io.chatgptbot.cli":"codex-cli","io.chatgptbot.account-auth":"1"}}}]',
                b"",
            )
        if DESKTOP_ISOLATION_PROBE in argv:
            return ProcessResult(
                0,
                json.dumps(isolation if isolation is not None else {"passed": True}).encode(),
                b"",
            )
        if argv[1] == "run":
            return ProcessResult(
                0,
                b"fixture-version exec --json --ignore-user-config --ignore-rules --skip-git-repo-check SESSION_ID --model --device-auth",
                b"",
            )
        return ProcessResult(0, b"", b"")

    runner.docker = docker
    return runner, calls


async def test_desktop_probes_controls_and_applies_pinned_seccomp_to_every_container(desktop_model):
    runner, calls = await run_preflight(desktop_model)
    await runner.verify()
    assert runner.verified and runner.isolation == {"passed": True}
    runs = [argv for argv in calls if argv[1] == "run"]
    assert any(DESKTOP_ISOLATION_PROBE in argv for argv in runs)
    for argv in runs:
        assert "--security-opt=seccomp=" + desktop_model.backend.seccomp_profile in argv
        assert "--read-only" in argv and "65532:65532" in argv
        assert "--cap-drop=ALL" in argv and "--security-opt=no-new-privileges" in argv
        assert "--memory-swap=1g" in argv and "--log-driver=none" in argv
        assert "--mount" not in argv
    assert sum(argv[1] == "rm" for argv in calls) == len(runs)


@pytest.mark.parametrize(
    "changed",
    [
        {"OperatingSystem": "Ubuntu"},
        {"CgroupVersion": "1"},
        {"CgroupDriver": "none"},
        {"MemoryLimit": False},
        {"CpuCfsQuota": False},
        {"PidsLimit": False},
    ],
)
async def test_desktop_rejects_wrong_daemon_or_unenforced_limits(desktop_model, changed):
    runner, calls = await run_preflight(desktop_model, runtime_changes=changed)
    with pytest.raises(BotError):
        await runner.verify()
    assert not runner.verified
    assert all(argv[1] != "run" for argv in calls)


@pytest.mark.parametrize("report", [{"passed": False}, {"passed": 1}, {}, []])
async def test_desktop_probe_fails_closed_before_native_cli_and_cleans_up(desktop_model, report):
    runner, calls = await run_preflight(desktop_model, isolation=report)
    with pytest.raises(BotError, match="isolation probe"):
        await runner.verify()
    assert not runner.verified
    assert len([argv for argv in calls if argv[1] == "run"]) == 1
    assert calls[-1][1:3] == ["rm", "-f"]


async def test_profile_change_is_rejected_even_after_preflight(desktop_model, tmp_path):
    runner, _ = await run_preflight(desktop_model)
    await runner.verify()
    (tmp_path / "seccomp.json").write_text('{"defaultAction":"SCMP_ACT_ALLOW"}')
    with pytest.raises(BotError, match="seccomp"):
        runner.base("next-container")
