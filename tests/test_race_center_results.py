from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from services.database import Base
from services import race_center_results as store

def test_round_trip_and_idempotent_updates(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread":False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[store.ResultEvent.__table__,store.ResultSession.__table__,store.ResultEntry.__table__])
    monkeypatch.setattr(store, "SessionLocal", sessionmaker(bind=engine))
    body = {
      "source_name":"Test official track","external_id":"event-1",
      "source_url":"https://example.org/results/1",
      "track":"Test Speedway","series":"Test Series","event_name":"Friday Feature",
      "race_date":date(2026,10,9),"status":"official",
      "sessions":[{"class_name":"Late Model","session_name":"Feature",
                   "entries":[{"finish":1,"start":4,"driver":"Alex Example","car_number":"3","laps":30,"result_status":"finished"},
                              {"finish":2,"start":2,"driver":"Jordan Example","car_number":"2","laps":30,"result_status":"finished"}]}]
    }
    key = store.upsert_verified(body)
    assert store.list_events(track="Speedway")[0]["key"] == key
    assert len(store.get_event(key)["sessions"][0]["entries"]) == 2
    assert store.driver_results("Alex Example")[0]["finish"] == 1
    body["sessions"][0]["entries"] = [body["sessions"][0]["entries"][0]]
    assert store.upsert_verified(body) == key
    assert len(store.get_event(key)["sessions"][0]["entries"]) == 1
    assert len(store.list_events()) == 1
