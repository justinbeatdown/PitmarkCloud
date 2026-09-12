from api import founders_race as founders_race
from api import prt_ui as prt_ui
from services import founders_race_activation as founders_race_activation  # noqa: F401

# Keep Founder's Race inside the existing PRT surface without creating a
# separate application or deployment. main.py already mounts prt_ui.router.
prt_ui.router.include_router(founders_race.router)
