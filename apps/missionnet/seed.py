"""Deterministic MissionNet seed dataset (blueprint §7.6).

Run as `python -m apps.missionnet.seed --reset` to wipe and recreate the pristine baseline: ~10
assets, 8 users, 4 service tokens, 15 mission records, a dependency graph, and a normal event
baseline. This is what `make reset-lab` calls so a live demo can be repeated without manual cleanup.
"""

import argparse
import asyncio
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete

from apps.missionnet.db import Base, SessionLocal, engine
from apps.missionnet.models import (
    Asset,
    AuditEvent,
    IdentityUser,
    MissionRecord,
    ServiceToken,
    TelemetrySample,
)

ASSETS = [
    # asset_id, name, asset_type, mission_role, criticality, dependencies, outage_s, cost, rollback
    ("identity-service-01", "Identity Service", "service", "identity", 5, [], 120, "high", True),
    (
        "api-gateway-01",
        "API Gateway",
        "service",
        "gateway",
        5,
        ["identity-service-01"],
        60,
        "high",
        True,
    ),
    (
        "mission-data-api-01",
        "Mission Data API",
        "service",
        "data",
        5,
        ["identity-service-01", "api-gateway-01"],
        180,
        "high",
        True,
    ),
    (
        "telemetry-gateway-01",
        "Telemetry Gateway Alpha",
        "service",
        "edge",
        4,
        ["api-gateway-01"],
        300,
        "medium",
        True,
    ),
    (
        "telemetry-gateway-02",
        "Telemetry Gateway Bravo",
        "service",
        "edge",
        4,
        ["api-gateway-01"],
        300,
        "medium",
        True,
    ),
    (
        "comms-service-01",
        "Communications Service",
        "service",
        "comms",
        3,
        ["identity-service-01"],
        600,
        "low",
        True,
    ),
    (
        "ops-console-01",
        "Operations Console",
        "frontend",
        "operator-console",
        3,
        ["api-gateway-01"],
        600,
        "low",
        True,
    ),
    ("asset-registry-01", "Asset Registry", "service", "data", 4, [], 300, "medium", True),
    (
        "sim-uav-017",
        "SIM-UAV-017",
        "edge-device",
        "edge",
        2,
        ["telemetry-gateway-01"],
        900,
        "low",
        True,
    ),
    (
        "sim-uav-042",
        "SIM-UAV-042",
        "edge-device",
        "edge",
        2,
        ["telemetry-gateway-02"],
        900,
        "low",
        True,
    ),
]

USERS = [
    ("u-operator-01", "j.rivera", "J. Rivera", "operator", "human"),
    ("u-operator-02", "a.tanaka", "A. Tanaka", "operator", "human"),
    ("u-analyst-01", "m.osei", "M. Osei", "analyst", "human"),
    ("u-analyst-02", "s.dubois", "S. Dubois", "analyst", "human"),
    ("u-admin-01", "r.khan", "R. Khan", "administrator", "human"),
    ("u-admin-02", "l.novak", "L. Novak", "administrator", "human"),
    (
        "svc-telemetry-01",
        "svc-telemetry-01",
        "Telemetry Ingest Service Account",
        "service_account",
        "service_account",
    ),
    (
        "svc-mission-data-01",
        "svc-mission-data-01",
        "Mission Data Service Account",
        "service_account",
        "service_account",
    ),
]

MISSION_RECORD_TITLES = [
    "Sector 7 patrol readiness summary",
    "Synthetic supply manifest - convoy 12",
    "Fictional asset maintenance log",
    "Simulated weather advisory - grid 4",
    "Training exercise after-action note",
    "Synthetic comms relay status",
    "Fictional personnel rotation schedule",
    "Simulated fuel reserve report",
    "Training scenario debrief - SCN-004",
    "Synthetic equipment inventory delta",
    "Fictional route deconfliction note",
    "Simulated sensor calibration record",
    "Training exercise safety brief",
    "Synthetic logistics request - batch 9",
    "Fictional readiness board update",
]


def _now() -> datetime:
    return datetime.now(UTC)


async def reset_and_seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    delete_order = (TelemetrySample, AuditEvent, ServiceToken, MissionRecord, Asset, IdentityUser)
    async with SessionLocal() as session:
        for model in delete_order:
            await session.execute(delete(model))
        await session.commit()

        users = [
            IdentityUser(user_id=uid, username=uname, display_name=disp, role=role, user_type=utype)
            for uid, uname, disp, role, utype in USERS
        ]
        session.add_all(users)

        assets = [
            Asset(
                asset_id=aid,
                name=name,
                asset_type=atype,
                mission_role=role,
                criticality=crit,
                dependencies=deps,
                max_allowed_outage_seconds=outage,
                containment_cost=cost,
                rollback_supported=rollback,
            )
            for aid, name, atype, role, crit, deps, outage, cost, rollback in ASSETS
        ]
        session.add_all(assets)

        service_accounts = [u for u in USERS if u[4] == "service_account"]
        tokens = [
            ServiceToken(
                token_id=f"tok-{owner_id}",
                owner_user_id=owner_id,
                token_type="service",
                valid=True,
            )
            for owner_id, _, _, _, _ in service_accounts
        ]
        # One extra token on the telemetry service account for a realistic multi-token baseline.
        tokens.append(
            ServiceToken(
                token_id="tok-svc-telemetry-01-b",
                owner_user_id="svc-telemetry-01",
                token_type="service",
            )
        )
        session.add_all(tokens)

        human_users = [u for u in USERS if u[4] == "human"]
        records = [
            MissionRecord(
                record_id=f"rec-{i:03d}",
                title=title,
                body=f"Synthetic mission record body for '{title}'. No real operational content.",
                owner_user_id=human_users[i % len(human_users)][0],
            )
            for i, title in enumerate(MISSION_RECORD_TITLES)
        ]
        session.add_all(records)

        telemetry = [
            TelemetrySample(
                sample_id=str(uuid.uuid4()),
                asset_id=aid,
                battery=90,
                link_quality=95,
                latitude=35.028,
                longitude=-106.612,
            )
            for aid in ("sim-uav-017", "sim-uav-042")
        ]
        session.add_all(telemetry)

        session.add(
            AuditEvent(
                audit_id=str(uuid.uuid4()),
                actor_type="lab_control",
                actor_id="reset-lab",
                action="seed.reset",
                object_type="missionnet",
                object_id="baseline",
                detail={"assets": len(assets), "users": len(users), "records": len(records)},
                severity="info",
            )
        )

        await session.commit()

    print(
        f"MissionNet seeded: {len(assets)} assets, {len(users)} users, {len(tokens)} tokens, "
        f"{len(records)} mission records, {len(telemetry)} telemetry samples."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Wipe/reseed the pristine baseline")
    args = parser.parse_args()
    if not args.reset:
        parser.error("Only --reset is supported: seeding always restores the baseline")
    asyncio.run(reset_and_seed())


if __name__ == "__main__":
    main()
