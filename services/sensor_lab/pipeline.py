"""Real, safe, synthetic network-sensor lab pipeline - see services/sensor_lab/__init__.py.

Every container is ephemeral (`docker run --rm` or explicitly removed at the end of the run), the
network is a private Docker bridge with no route to anything outside this machine, and the only
traffic generated is one HTTP request with a deliberately suspicious-looking marker query string
and one DNS query for a synthetic DGA-shaped test hostname - both fully described here, nothing
hidden. Suricata and Zeek both run once, in batch mode, against the resulting pcap file; neither is
a live-capturing daemon.
"""

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

NETWORK_NAME = "sentinel-sensor-lab"
SUBNET = "172.28.0.0/24"
SERVER_IP = "172.28.0.10"
DNS_IP = "172.28.0.11"
CLIENT_IP = "172.28.0.3"

SERVER_CONTAINER = "sentinel-lab-server"
DNS_CONTAINER = "sentinel-lab-dns"
CLIENT_CONTAINER = "sentinel-lab-client"

SURICATA_IMAGE = "jasonish/suricata:latest"
ZEEK_IMAGE = "zeek/zeek:latest"
NGINX_IMAGE = "nginx:alpine"
DNS_IMAGE = "alpine:latest"
CLIENT_IMAGE = "nicolaka/netshoot:latest"

DEFAULT_TIMEOUT_SECONDS = 45
DGA_TEST_HOSTNAME = "a8f3k2m9x7q1z5.sentinel-lab-dga-test.example"
BENIGN_TEST_HOSTNAME = "www.normal-lab-site.example"

_LOCAL_SURICATA_RULES = """\
alert http any any -> any any (msg:"SENTINEL LAB Suspicious Command-Injection-style URI"; \
flow:established,to_server; http.uri; content:"cmd="; nocase; \
classtype:web-application-attack; sid:1000001; rev:1; priority:1; \
metadata: attack_target Web_Server;)
alert http any any -> any any (msg:"SENTINEL LAB Marker Header Present"; \
flow:established,to_server; http.header_names; content:"X-Sentinel-Lab-Marker"; \
classtype:policy-violation; sid:1000002; rev:1; priority:2;)
"""


class SensorLabError(RuntimeError):
    """A step of the sensor-lab pipeline failed - always cleaned up before this is raised, so a
    failed run never leaves containers or a stale network behind."""


@dataclass
class SensorLabResult:
    pcap_path: str
    suricata_alert_count: int
    zeek_conn_count: int
    zeek_dns_count: int
    zeek_http_count: int


async def _run(*args: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> str:
    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError as exc:
        proc.kill()
        await proc.wait()
        raise SensorLabError(f"command timed out after {timeout}s: {' '.join(args)}") from exc
    if proc.returncode != 0:
        stderr_text = stderr.decode(errors="replace")
        raise SensorLabError(f"command failed ({proc.returncode}): {' '.join(args)}\n{stderr_text}")
    return stdout.decode(errors="replace")


async def _run_ignore_errors(*args: str, timeout: float = 20) -> None:
    try:
        await _run(*args, timeout=timeout)
    except SensorLabError:
        pass


async def _cleanup() -> None:
    for container in (CLIENT_CONTAINER, DNS_CONTAINER, SERVER_CONTAINER):
        await _run_ignore_errors("docker", "rm", "-f", container)
    await _run_ignore_errors("docker", "network", "rm", NETWORK_NAME)


async def _generate_lab_traffic(base_dir: Path) -> Path:
    www_dir = base_dir / "www"
    www_dir.mkdir(parents=True, exist_ok=True)
    (www_dir / "index.html").write_text("<html>sentinel lab test page</html>\n")

    pcap_dir = base_dir / "pcap"
    pcap_dir.mkdir(parents=True, exist_ok=True)
    pcap_path = pcap_dir / "lab.pcap"
    pcap_path.unlink(missing_ok=True)

    await _cleanup()
    await _run(
        "docker", "network", "create", "--subnet", SUBNET, NETWORK_NAME, timeout=20
    )
    try:
        await _run(
            "docker", "run", "-d", "--name", SERVER_CONTAINER,
            "--network", NETWORK_NAME, "--ip", SERVER_IP,
            "-v", f"{www_dir}:/usr/share/nginx/html:ro",
            NGINX_IMAGE,
        )
        await _run(
            "docker", "run", "-d", "--name", DNS_CONTAINER,
            "--network", NETWORK_NAME, "--ip", DNS_IP, "--cap-add", "NET_ADMIN",
            DNS_IMAGE, "sh", "-c",
            f"apk add --no-cache dnsmasq >/dev/null 2>&1 && "
            f"dnsmasq -k --no-daemon --address=/#/{SERVER_IP}",
        )
        await _run(
            "docker", "run", "-d", "--name", CLIENT_CONTAINER,
            "--network", NETWORK_NAME, "--ip", CLIENT_IP,
            "--cap-add", "NET_RAW", "--cap-add", "NET_ADMIN",
            "-v", f"{pcap_dir}:/pcap",
            CLIENT_IMAGE, "sleep", "infinity",
        )
        await asyncio.sleep(2)  # let dnsmasq finish installing before the client queries it

        await _run(
            "docker", "exec", "-d", CLIENT_CONTAINER,
            "tcpdump", "-i", "eth0", "-w", "/pcap/lab.pcap", "-U",
        )
        await asyncio.sleep(1)

        traffic_script = (
            f"curl -s -o /dev/null -A 'SentinelLabClient/1.0' "
            f"-H 'X-Sentinel-Lab-Marker: suspicious-scan-attempt' "
            f"http://{SERVER_IP}/index.html; "
            f"curl -s -o /dev/null -A 'SentinelLabClient/1.0' "
            f"'http://{SERVER_IP}/index.html?cmd=cat%20/etc/passwd'; "
            f"dig @{DNS_IP} {DGA_TEST_HOSTNAME} +time=2 +tries=1 >/dev/null; "
            f"dig @{DNS_IP} {BENIGN_TEST_HOSTNAME} +time=2 +tries=1 >/dev/null"
        )
        await _run("docker", "exec", CLIENT_CONTAINER, "sh", "-c", traffic_script)
        await asyncio.sleep(1)
        await _run_ignore_errors("docker", "exec", CLIENT_CONTAINER, "pkill", "tcpdump")
        await asyncio.sleep(1)
    finally:
        await _cleanup()

    if not pcap_path.exists() or pcap_path.stat().st_size == 0:
        raise SensorLabError("no pcap was captured - lab traffic generation failed")
    return pcap_path


async def _run_suricata(base_dir: Path, pcap_path: Path) -> Path:
    rules_dir = base_dir / "suricata-rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    rules_path = rules_dir / "local.rules"
    rules_path.write_text(_LOCAL_SURICATA_RULES)

    out_dir = base_dir / "suricata-out"
    out_dir.mkdir(parents=True, exist_ok=True)
    eve_path = out_dir / "eve.json"
    eve_path.unlink(missing_ok=True)

    await _run(
        "docker", "run", "--rm",
        "-v", f"{pcap_path}:/pcap/lab.pcap:ro",
        "-v", f"{rules_dir}:/rules:ro",
        "-v", f"{out_dir}:/var/log/suricata",
        SURICATA_IMAGE,
        "-r", "/pcap/lab.pcap", "-S", "/rules/local.rules",
        "-k", "none", "-l", "/var/log/suricata", "--runmode=single",
        timeout=60,
    )
    return eve_path


async def _run_zeek(base_dir: Path, pcap_path: Path) -> Path:
    out_dir = base_dir / "zeek-out"
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in ("conn.log", "dns.log", "http.log"):
        (out_dir / name).unlink(missing_ok=True)

    await _run(
        "docker", "run", "--rm", "-w", "/zeek-out",
        "-v", f"{pcap_path}:/pcap/lab.pcap:ro",
        "-v", f"{out_dir}:/zeek-out",
        ZEEK_IMAGE, "zeek", "-C", "-r", "/pcap/lab.pcap", "LogAscii::use_json=T",
        timeout=60,
    )
    return out_dir


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open() as f:
        return sum(1 for line in f if line.strip())


def _count_suricata_alerts(eve_path: Path) -> int:
    if not eve_path.exists():
        return 0
    count = 0
    with eve_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                if json.loads(line).get("event_type") == "alert":
                    count += 1
            except json.JSONDecodeError:
                continue
    return count


async def run_network_sensor_lab(base_dir: str = "var/sensor-lab") -> SensorLabResult:
    base_path = Path(base_dir).resolve()
    pcap_path = await _generate_lab_traffic(base_path)
    eve_path = await _run_suricata(base_path, pcap_path)
    zeek_out_dir = await _run_zeek(base_path, pcap_path)

    return SensorLabResult(
        pcap_path=str(pcap_path),
        suricata_alert_count=_count_suricata_alerts(eve_path),
        zeek_conn_count=_count_lines(zeek_out_dir / "conn.log"),
        zeek_dns_count=_count_lines(zeek_out_dir / "dns.log"),
        zeek_http_count=_count_lines(zeek_out_dir / "http.log"),
    )
