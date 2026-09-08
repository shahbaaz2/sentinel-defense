"""Normalizes a Postgres connection string to the `postgresql+asyncpg://` scheme SQLAlchemy's
asyncpg driver requires. Managed Postgres providers (Render, Heroku, and others) hand out
`postgres://` or plain `postgresql://` URLs - without this, pasting one of those verbatim into
`SENTINEL_DATABASE_URL`/`MISSIONNET_DATABASE_URL`/`DEMOCONTROL_DATABASE_URL` fails with a driver
error that gives no hint what to change. See docs/deployment.md.
"""


def normalize_async_postgres_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://") :]
    return url
