"""`make reset-demo`: clears Demo Control's own scenario-run history. Does not touch MissionNet or
Sentinel - pair with `make reset-lab` for a full reset of all three systems (that is exactly what
`make reset-demo` below does).
"""

import asyncio

from sqlalchemy import delete

from apps.demo_control.db import SessionLocal
from apps.demo_control.models import ScenarioRun


async def reset() -> None:
    async with SessionLocal() as session:
        await session.execute(delete(ScenarioRun))
        await session.commit()
    print("Demo Control scenario-run history cleared.")


if __name__ == "__main__":
    asyncio.run(reset())
