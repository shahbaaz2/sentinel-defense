from domain.db_url import normalize_async_postgres_url


def test_already_correct_scheme_is_unchanged():
    url = "postgresql+asyncpg://user:pass@host:5432/db"
    assert normalize_async_postgres_url(url) == url


def test_render_style_postgres_scheme_is_upgraded():
    url = "postgres://user:pass@dpg-example.render.com/sentinel"
    assert normalize_async_postgres_url(url) == (
        "postgresql+asyncpg://user:pass@dpg-example.render.com/sentinel"
    )


def test_plain_postgresql_scheme_is_upgraded():
    url = "postgresql://user:pass@host:5432/db"
    assert normalize_async_postgres_url(url) == "postgresql+asyncpg://user:pass@host:5432/db"


def test_unrecognized_scheme_is_passed_through_unchanged():
    url = "sqlite:///local.db"
    assert normalize_async_postgres_url(url) == url
