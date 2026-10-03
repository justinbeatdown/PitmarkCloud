"""Regression: warm standings must include persisted permitted driver photos."""
import sys
import unittest
from pathlib import Path
from datetime import timedelta
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from services import racing_standings as standings


class DriverPhotoSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        standings.RaceCenterDriverIdentityCache.__table__.create(self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.session_patch = patch.object(standings, "SessionLocal", self.sessions)
        self.session_patch.start()
        self.addCleanup(self.session_patch.stop)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(standings.clear_standings_cache)
        standings.clear_standings_cache()
        with self.sessions() as db:
            db.add(standings.RaceCenterDriverIdentityCache(
                series_key="nascar-cup", season=2026, driver_key="kylelarson",
                driver_name="Kyle Larson", photo_url="https://example.com/larson.jpg",
                photo_use_allowed=True, photo_source_url="https://example.com/license",
                photo_license="CC BY-SA 4.0", photo_attribution="Photographer",
                resolver_version=standings.DRIVER_IDENTITY_RESOLVER_VERSION,
            ))
            db.add(standings.RaceCenterDriverIdentityCache(
                series_key="nascar-cup", season=2026, driver_key="dennyhamlin",
                driver_name="Denny Hamlin", photo_url="https://example.com/unpermitted.jpg",
                photo_use_allowed=False,
                resolver_version=standings.DRIVER_IDENTITY_RESOLVER_VERSION,
            ))
            db.commit()
        self.raw = {"season": 2026, "series": [{"series_key": "nascar-cup", "entries": [
            {"name": "Kyle Larson"}, {"name": "Denny Hamlin"},
        ]}]}
        standings._cache.update(at=standings.utcnow(), value=self.raw)

    def test_warm_standings_return_saved_photo_and_provenance(self):
        result = standings.get_standings_snapshot_hub(season=2026)
        larson, hamlin = result["series"][0]["entries"]
        self.assertEqual(larson.get("photo_url"), "https://example.com/larson.jpg")
        self.assertTrue(larson.get("photo_use_allowed"))
        self.assertEqual(larson.get("photo_license"), "CC BY-SA 4.0")
        self.assertEqual(larson.get("photo_attribution"), "Photographer")
        self.assertFalse(hamlin.get("photo_url"))
        self.assertNotIn("photo_url", self.raw["series"][0]["entries"][0])

    def test_hydrated_snapshot_is_cached_but_picks_up_new_photos_after_expiry(self):
        reads = []
        event.listen(self.engine, "before_cursor_execute", lambda *args: reads.append(args[2]))
        standings.get_standings_snapshot_hub(season=2026)
        result = standings.get_standings_snapshot_hub(season=2026)
        self.assertEqual(result["series"][0]["entries"][0].get("photo_url"), "https://example.com/larson.jpg")
        self.assertEqual(len(reads), 1, "Warm snapshots should use one bulk identity query, then cache it")
        with self.sessions() as db:
            row = db.query(standings.RaceCenterDriverIdentityCache).filter_by(driver_key="kylelarson").one()
            row.photo_url = "https://example.com/new-larson.jpg"
            db.commit()
        standings._snapshot_cache["at"] = standings.utcnow() - timedelta(seconds=91)
        fresh = standings.get_standings_snapshot_hub(season=2026)
        self.assertEqual(fresh["series"][0]["entries"][0].get("photo_url"), "https://example.com/new-larson.jpg")


if __name__ == "__main__":
    unittest.main()
