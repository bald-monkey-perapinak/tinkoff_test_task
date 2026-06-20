import os
import sys
import tempfile
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import database as db_mod
from models import Favorite, Subscription, Vacancy


@pytest.fixture(autouse=True)
async def setup_db():
    import config
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    original_path = config.DB_PATH
    config.DB_PATH = type(original_path)(tmp.name)
    db_mod.DB_PATH = config.DB_PATH
    await db_mod.init_db()
    yield
    config.DB_PATH = original_path
    db_mod.DB_PATH = original_path
    try:
        os.unlink(tmp.name)
    except OSError:
        pass


@pytest.fixture
def sample_vacancy():
    return Vacancy(
        id="test-vac-1", title="Python Dev", company="TestCo",
        city="Moscow", salary="100k", salary_from=100000, salary_to=None,
        schedule="remote", experience="between1And3",
        skills=["python"], url="https://example.com/1",
        description="Test", published_at="2025-01-01", is_mock=True,
    )


@pytest.fixture
def sample_fav():
    return Favorite(
        chat_id=12345, vacancy_id="test-vac-1",
        title="Python Dev", company="TestCo", url="https://example.com/1",
    )


@pytest.fixture
def sample_sub():
    return Subscription(
        chat_id=12345, query="Python", area="Moscow",
        schedule="remote", min_salary=80000, is_active=True,
    )


class TestFavorites:
    async def test_add_and_get(self, sample_fav):
        await db_mod.add_favorite(sample_fav)
        favs = await db_mod.get_favorites(12345)
        assert len(favs) == 1
        assert favs[0].vacancy_id == "test-vac-1"

    async def test_remove(self, sample_fav):
        await db_mod.add_favorite(sample_fav)
        await db_mod.remove_favorite(12345, "test-vac-1")
        favs = await db_mod.get_favorites(12345)
        assert len(favs) == 0

    async def test_isolation_by_chat_id(self, sample_fav):
        await db_mod.add_favorite(sample_fav)
        favs = await db_mod.get_favorites(99999)
        assert len(favs) == 0

    async def test_duplicate_insert_ignored(self, sample_fav):
        await db_mod.add_favorite(sample_fav)
        await db_mod.add_favorite(sample_fav)
        favs = await db_mod.get_favorites(12345)
        assert len(favs) == 1


class TestSubscriptions:
    async def test_add_and_get(self, sample_sub):
        sub_id = await db_mod.add_subscription(sample_sub)
        assert sub_id > 0
        subs = await db_mod.get_active_subscriptions(12345)
        assert len(subs) == 1
        assert subs[0].query == "Python"

    async def test_remove(self, sample_sub):
        sub_id = await db_mod.add_subscription(sample_sub)
        await db_mod.remove_subscription(12345, sub_id)
        subs = await db_mod.get_active_subscriptions(12345)
        assert len(subs) == 0

    async def test_get_all(self, sample_sub):
        await db_mod.add_subscription(sample_sub)
        all_subs = await db_mod.get_active_subscriptions()
        assert len(all_subs) >= 1


class TestSeenVacancies:
    async def test_mark_and_check(self):
        await db_mod.mark_vacancy_seen(12345, "v1")
        assert await db_mod.is_vacancy_seen(12345, "v1")
        assert not await db_mod.is_vacancy_seen(12345, "v2")

    async def test_batch(self):
        await db_mod.batch_mark_vacancies_seen(12345, ["v1", "v2", "v3"])
        seen = await db_mod.batch_is_vacancy_seen(12345, ["v1", "v2", "v3", "v4"])
        assert seen == {"v1", "v2", "v3"}

    async def test_isolation(self):
        await db_mod.mark_vacancy_seen(12345, "v1")
        assert not await db_mod.is_vacancy_seen(99999, "v1")


class TestSessions:
    async def test_save_and_get(self, sample_vacancy):
        await db_mod.save_session("sess-1", [sample_vacancy], time.time())
        session = await db_mod.get_session("sess-1")
        assert session is not None
        assert len(session["vacancies"]) == 1
        assert session["vacancies"][0].id == "test-vac-1"

    async def test_get_nonexistent(self):
        session = await db_mod.get_session("nonexistent")
        assert session is None
