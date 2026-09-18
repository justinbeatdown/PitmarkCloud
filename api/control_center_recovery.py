from fastapi import APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter()

_RECOVERY_RELEASE = "20260918nomail1"


@router.get('/control-reset', include_in_schema=False)
def control_reset():
    # This route intentionally sits outside the retired /control/ worker scope.
    # Do not render an intermediate page: redirect immediately into the current HQ.
    return RedirectResponse(
        url=f'/control?fresh={_RECOVERY_RELEASE}',
        status_code=302,
        headers={
            'Cache-Control': 'no-store, max-age=0',
            'Pragma': 'no-cache',
            'Clear-Site-Data': '"cache"',
        },
    )
