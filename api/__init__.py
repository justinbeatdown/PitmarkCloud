from api import founders_race as founders_race
from api import prt_ui as prt_ui

# Keep Founder's Race inside the existing PRT surface without creating a
# separate application or deployment. main.py already mounts prt_ui.router.
prt_ui.router.include_router(founders_race.router)
