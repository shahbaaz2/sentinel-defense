"""Contract for the subset of Suricata's real EVE JSON shape this integration actually reads.
Suricata's own `eve.json` carries many more fields and event types (flow, fileinfo, stats, dns,
tls, ...) than Sentinel needs - this model validates only the `alert` event type, which is the one
Sentinel treats as sensor evidence worth normalizing (see mapper.py). An eve.json line that fails
this validation is skipped, not fabricated into something it isn't.
"""

from pydantic import BaseModel


class SuricataAlertDetail(BaseModel):
    action: str
    signature_id: int
    signature: str
    category: str
    severity: int
    """Suricata convention: 1 = highest priority (most severe), 3 = lowest."""
    rev: int = 1


class SuricataFlow(BaseModel):
    pkts_toserver: int | None = None
    pkts_toclient: int | None = None
    bytes_toserver: int | None = None
    bytes_toclient: int | None = None


class SuricataHttp(BaseModel):
    hostname: str | None = None
    url: str | None = None
    http_user_agent: str | None = None
    http_method: str | None = None
    status: int | None = None


class SuricataEveAlert(BaseModel):
    """One `event_type: "alert"` line from a real Suricata `eve.json`."""

    timestamp: str
    flow_id: int
    event_type: str
    src_ip: str
    src_port: int | None = None
    dest_ip: str
    dest_port: int | None = None
    proto: str
    alert: SuricataAlertDetail
    http: SuricataHttp | None = None
    flow: SuricataFlow | None = None
