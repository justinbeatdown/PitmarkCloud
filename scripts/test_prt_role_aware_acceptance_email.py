from api.early_access_admin import _acceptance_message


def main() -> None:
    driver = _acceptance_message("Test Driver", "PRT-EA-TEST-CODE", "quick-apply-driver")
    broadcaster = _acceptance_message("Test Broadcaster", "PRT-EA-TEST-CODE", "quick-apply-broadcaster")
    league = _acceptance_message("Test League", "PRT-EA-TEST-CODE", "quick-apply-league")
    media = _acceptance_message("Test Media", "PRT-EA-TEST-CODE", "quick-apply-media")

    assert "real iRacing drivers involved now" in driver
    assert "actual race conditions" in driver

    assert "real iRacing drivers involved now" not in broadcaster
    assert "broadcast" in broadcaster.lower()
    assert "spectator" in broadcaster.lower()
    assert "Broadcast Studio is in development" in broadcaster

    assert "real iRacing drivers involved now" not in league
    assert "league" in league.lower()
    assert "admin" in league.lower()

    assert "real iRacing drivers involved now" not in media
    assert "media" in media.lower() or "developer" in media.lower()
    assert "review" in media.lower() or "inspect" in media.lower()

    source = open("api/early_access_admin.py", encoding="utf-8").read()
    assert '_acceptance_message(name, invite["code"], row.get("placement") or "quick-apply")' in source

    print("PRT role-aware acceptance email contract OK")


if __name__ == "__main__":
    main()
