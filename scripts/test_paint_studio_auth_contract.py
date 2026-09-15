from services.control_access import permission_for_path


def test_paint_studio_auth_is_owned_by_endpoint():
    """Paint Studio must handle its own owner/admin auth so browser GETs can redirect to login."""
    assert permission_for_path("/api/control/content/paint-studio") is None
    assert permission_for_path("/api/control/content/paint-studio.css") is None
    assert permission_for_path("/api/control/content/paint-studio.js") is None
    assert permission_for_path("/api/control/content/paint-studio/generate") is None
