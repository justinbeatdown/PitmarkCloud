from __future__ import annotations

import io
import textwrap
from functools import lru_cache

import httpx
from fastapi import APIRouter
from fastapi.responses import Response
from PIL import Image, ImageDraw, ImageFont

router = APIRouter()

ORANGE = (255, 85, 0)
BLACK = (18, 18, 18)
DARK = (42, 42, 42)
GRAY = (105, 105, 105)
LIGHT = (245, 245, 245)
WHITE = (255, 255, 255)
CONTACT = "contact@pitmarkracing.com"
SITE = "prl.pitmarkracing.com"
LOGO_URL = "https://cdn.shopify.com/s/files/1/1067/3913/8641/files/prl-logo.png?v=1791152433"

SCHEDULE = [
    ("R01","Jan 13","Daytona International Speedway","80 laps / 200 mi","Season Opener"),
    ("R02","Jan 19","Charlotte Motor Speedway","100 laps / 150 mi",""),
    ("R03","Jan 27","Iowa Speedway","150 laps / 131.25 mi",""),
    ("R04","Feb 2","Phoenix Raceway","150 laps / 150 mi",""),
    ("R05","Feb 10","Richmond Raceway","200 laps / 150 mi",""),
    ("R06","Feb 16","Michigan International Speedway","100 laps / 200 mi",""),
    ("R07","Feb 24","Martinsville Speedway","200 laps / 105.2 mi",""),
    ("R08","Mar 2","Kansas Speedway","100 laps / 150 mi",""),
    ("R09","Mar 10","Watkins Glen International","41 laps / ~100 mi","Road Course"),
    ("R10","Mar 16","Nashville Superspeedway","120 laps / ~160 mi",""),
    ("R11","Mar 24","Talladega Superspeedway","76 laps / ~202 mi","CHASE CUTOFF"),
    ("R12","Mar 30","Bristol Motor Speedway","200 laps / ~106.6 mi","CHASE 1"),
    ("R13","Apr 7","Dover Motor Speedway","150 laps / 150 mi","CHASE 2"),
    ("R14","Apr 13","Darlington Raceway","125 laps / ~171 mi","CHASE 3"),
    ("R15","Apr 21","Homestead-Miami Speedway","100 laps / 150 mi","CHAMPIONSHIP"),
]

def _font(size: int, bold: bool = False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()

@lru_cache(maxsize=1)
def _logo() -> Image.Image | None:
    try:
        with httpx.Client(timeout=6.0, follow_redirects=True) as client:
            r = client.get(LOGO_URL)
            r.raise_for_status()
        return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except Exception:
        return None

class PdfDoc:
    def __init__(self, title: str, subtitle: str):
        self.title = title
        self.subtitle = subtitle
        self.pages: list[Image.Image] = []
        self.img = None
        self.draw = None
        self.y = 0
        self.page_no = 0
        self.new_page(first=True)

    def new_page(self, first=False):
        if self.img is not None:
            self._footer()
            self.pages.append(self.img.convert("RGB"))
        self.page_no += 1
        self.img = Image.new("RGB", (1275, 1650), WHITE)
        self.draw = ImageDraw.Draw(self.img)
        lg = _logo()
        if lg:
            crop = lg.crop(lg.getbbox())
            maxw, maxh = 420, 175
            scale = min(maxw / crop.width, maxh / crop.height)
            crop = crop.resize((int(crop.width*scale), int(crop.height*scale)), Image.Resampling.LANCZOS)
            self.img.paste(crop, ((1275-crop.width)//2, 45), crop)
            self.y = 235
        else:
            self.draw.text((80, 60), "PRL", font=_font(70, True), fill=ORANGE)
            self.y = 160
        if first:
            self.center(self.title.upper(), 42, ORANGE, True, after=10)
            self.center(self.subtitle, 22, BLACK, True, after=8)
            self.center(f"Official PRL Contact: {CONTACT}  •  {SITE}", 17, GRAY, False, after=24)
            self.draw.line((70, self.y, 1205, self.y), fill=ORANGE, width=5)
            self.y += 28
        else:
            self.y += 10

    def _footer(self):
        self.draw.text((1035, 1605), f"PRL  •  {self.page_no}", font=_font(15), fill=GRAY)

    def center(self, text, size, color=BLACK, bold=False, after=12):
        f=_font(size,bold); box=self.draw.textbbox((0,0),text,font=f)
        self.draw.text(((1275-(box[2]-box[0]))//2,self.y),text,font=f,fill=color)
        self.y += (box[3]-box[1]) + after

    def ensure(self, need=120):
        if self.y + need > 1575:
            self.new_page()

    def heading(self, text):
        self.ensure(75)
        self.draw.text((75,self.y),text,font=_font(27,True),fill=ORANGE)
        self.y += 42

    def para(self, text, size=18, color=BLACK, after=15):
        f=_font(size)
        width = 103
        lines=[]
        for para in text.split("\n"):
            lines.extend(textwrap.wrap(para,width=width) or [""])
        h=(size+9)*len(lines)+after
        self.ensure(h)
        for line in lines:
            self.draw.text((75,self.y),line,font=f,fill=color)
            self.y += size+9
        self.y += after

    def bullet(self, text):
        f=_font(18)
        lines=textwrap.wrap(text,width=96)
        self.ensure((18+9)*len(lines)+5)
        self.draw.ellipse((82,self.y+8,90,self.y+16),fill=BLACK)
        for i,line in enumerate(lines):
            self.draw.text((108,self.y),line,font=f,fill=BLACK)
            self.y += 27
        self.y += 2

    def callout(self, head, body):
        lines=textwrap.wrap(body,width=92)
        h=62+27*len(lines)
        self.ensure(h+15)
        self.draw.rectangle((70,self.y,1205,self.y+h),fill=LIGHT)
        self.draw.text((90,self.y+16),head.upper(),font=_font(20,True),fill=ORANGE)
        yy=self.y+47
        for line in lines:
            self.draw.text((90,yy),line,font=_font(17),fill=BLACK); yy+=25
        self.y += h+20

    def finish(self) -> bytes:
        self._footer()
        self.pages.append(self.img.convert("RGB"))
        out=io.BytesIO()
        self.pages[0].save(out,format="PDF",save_all=True,append_images=self.pages[1:],resolution=150.0)
        return out.getvalue()

def _driver_handbook() -> bytes:
    d=PdfDoc("PRL Driver Handbook","2027 Inaugural ARCA Championship • Driver-Facing Guide")
    d.callout("Welcome to PRL","Pitmark Racing League is built for drivers who want organized, competitive racing without turning every week into a second job. Season 1 uses fixed-setup ARCA cars, realistic race lengths, a rotating Tuesday/Wednesday calendar, and a four-race Chase.")
    d.heading("What You Need to Race")
    for x in ["An active iRacing membership and an eligible current ARCA car.","The tracks for the rounds you plan to enter.","A completed PRL registration form and membership in the Pitmark Discord.","A working microphone is strongly recommended for drivers meetings.","Respect for the league rules, Race Control, and other competitors."]: d.bullet(x)
    d.heading("Race Night at a Glance")
    for x in ["7:00 PM ET - Practice server opens.","7:40 PM ET - Driver check-in closes.","7:45 PM ET - Drivers meeting.","7:50 PM ET - Lone qualifying.","7:55 PM ET - Warmup.","8:00 PM ET - Race window begins."]: d.bullet(x)
    d.callout("Race Length Philosophy","PRL races are intentionally longer than typical quick league sprints. Most events are designed to feel like a proper ARCA feature, generally around 75-100 minutes depending on cautions and track type.")
    d.heading("Season & Chase")
    for x in ["15 championship rounds total.","Rounds 1-11 form the regular season.","Top 8 eligible drivers after Round 11 qualify for the Chase.","Chase points reset to 2,000 plus earned playoff points.","Regular-season wins earn 5 playoff points each; the regular-season champion earns 10 additional playoff points.","No elimination rounds: all four Chase races count.","Non-Chase drivers continue racing and scoring full-season points."]: d.bullet(x)
    d.heading("Points Basics")
    for x in ["1st: 40; 2nd: 35; 3rd: 34; positions then decrease by one point per place.","Pole: +1 point.","Lead a lap: +1 point.","Most laps led: +1 point.","DNS: 0 points."]: d.bullet(x)
    d.heading("Driver Conduct")
    d.para("Race people the way you want to be raced. Hard racing is welcome; retaliation and avoidable nonsense are not.")
    for x in ["One proactive defensive move is allowed; reactionary blocking is not.","Leave reasonable racing room when meaningful overlap exists.","Rejoin only when it is safe.","Follow iRacing pacing and pit-road instructions.","No intentional wrecking, retaliation, threats, or harassment.","Use the protest process after the race instead of arguing incidents live."]: d.bullet(x)
    d.heading("Cautions, Restarts & Overtime")
    for x in ["Automatic full-course cautions on oval events.","Double-file restarts unless Race Control orders otherwise.","Lucky Dog and wave-arounds enabled.","Caution laps count.","Two Green-White-Checkered attempts."]: d.bullet(x)
    d.heading("Incident Limit")
    d.para("Season standard: 12x warning and 20x automatic disqualification.")
    d.heading("Protests")
    d.para("Submit protests privately within 24 hours of the checkered flag. Include lap/time, drivers involved, and a short factual explanation.")
    d.heading("2027 Season Schedule")
    for rnd,date,track,dist,note in SCHEDULE:
        d.bullet(f"{rnd} • {date} • {track} • {dist}" + (f" • {note}" if note else ""))
    d.heading("Questions & Support")
    d.para(f"For registration help, league questions, accessibility needs, sponsor inquiries, or general support, email {CONTACT}.")
    return d.finish()

def _competition_rulebook() -> bytes:
    d=PdfDoc("PRL Competition Rulebook","2027 Inaugural ARCA Championship • Public Sporting Rules")
    d.callout("What this document is","This is the competitor-facing rulebook. It explains the rules drivers are expected to follow on track. Internal staffing, admin tools, and steward workflow are intentionally kept out of this public version.")
    sections=[
        ("1. General Standard","PRL expects clean, competitive racing. Drivers are responsible for maintaining control, racing predictably, and avoiding actions that create unreasonable risk for others."),
        ("2. Starts & Restarts",["All championship races use rolling starts.","Restarts are double-file unless Race Control announces single-file.","Do not lay back, jump the start, brake-check, or manipulate restart lanes.","Follow iRacing pacing instructions unless Race Control gives a direct correction."]),
        ("3. Passing & Blocking",["One proactive defensive move is permitted.","A reactionary move after the trailing car commits is blocking.","Late chops, hooks, deliberate dooring, or forcing another car below the usable racing surface may be penalized.","Superspeedway lane defense remains subject to reasonable racing-room standards."]),
        ("4. Contact & Racing Room","Contact is not automatically a penalty. Review considers overlap, control, closing rate, expected line, avoidability, and consequence."),
        ("5. Rejoins","A driver who leaves the racing surface must return only when it is safe. A dangerous rejoin can be penalized even if the original off-track was not the driver's fault."),
        ("6. Yellow-Flag Conduct",["Maintain predictable pace under caution.","Do not pass under yellow except when iRacing instructs positions to be exchanged.","Avoid unnecessary weaving, brake-checking, or aggressive position games during pacing."]),
        ("7. Pit Road",["Respect pit-entry and pit-exit procedures, blend lines, and speed limits.","Unsafe pit entry or exit may be reviewed even without an automatic iRacing penalty."]),
        ("8. Incident Limits","Season standard: 12x warning and 20x automatic disqualification."),
        ("9. Green-White-Checkered","PRL uses two attempts. If iRacing ends the race under yellow after available attempts, the simulator finish is used subject to post-race stewarding adjustments."),
        ("10. Conduct & Communication",["Intentional wrecking and retaliation are prohibited.","Threats, slurs, discriminatory abuse, or targeted harassment can result in suspension or removal.","Official race voice/text is reserved for Race Control.","Do not argue incidents live during competition."]),
        ("11. Protests","Driver protests must be submitted privately within 24 hours of the checkered flag with the round, lap/time, cars involved, and a concise factual explanation."),
    ]
    for h,b in sections:
        d.heading(h)
        if isinstance(b,list):
            for x in b: d.bullet(x)
        else: d.para(b)
    d.heading("12. Penalty Guide")
    for x in ["Minor avoidable contact - warning or -5 points.","Avoidable contact causing spin/caution - typically -10 points.","Reckless rejoin - typically -10 points.","Reactionary blocking - warning, then -5 points.","Start/restart violation - end-of-line or -5 points.","Ignoring Race Control - typically -10 points.","Intentional wrecking / retaliation - -25 points + minimum one-race suspension; possible removal.","Abusive / discriminatory conduct - suspension or removal."]: d.bullet(x)
    d.heading("13. Appeals")
    d.para("One appeal may be submitted within 24 hours of a published decision when new evidence exists or a rule was materially misapplied.")
    d.heading("14. Service / Connection Problems")
    d.para("Individual hardware, connection, or client failures are normal racing misfortune. A widespread iRacing outage or major PRL configuration error may result in a restart, postponement, or other published remedy.")
    d.heading("15. Rule Changes")
    d.para("Material competitive changes are announced before the next points race and are not applied retroactively.")
    d.heading("Contact")
    d.para(f"Questions or rule clarifications before race night: {CONTACT}.")
    return d.finish()

def _race_night_guide() -> bytes:
    d=PdfDoc("PRL Race Night Guide","2027 Season • Quick Reference for Drivers")
    d.callout("Keep this handy","A quick rules-and-settings reference for race night.")
    d.heading("Timeline")
    for x in ["7:00 PM ET - Practice opens","7:40 PM ET - Check-in deadline","7:45 PM ET - Drivers meeting","7:50 PM ET - Lone qualifying","7:55 PM ET - Warmup","8:00 PM ET - Race window"]: d.bullet(x)
    d.heading("Session Settings")
    for x in ["ARCA 2025 Series • Fixed setup","Rolling start • Double-file restarts","Automatic cautions on oval events","Lucky Dog on • Wave-arounds on • Caution laps count","2 G/W/C attempts • 0 fast repairs","12x warning / 20x DQ","100% fuel • Unlimited tires","Dry weather • Clutch assist only"]: d.bullet(x)
    d.heading("Five Things to Remember")
    for x in ["Check in before 7:40 PM ET.","Do not reaction-block.","Rejoin safely.","Keep race chat clear for Race Control.","Protest privately after the race instead of arguing live."]: d.bullet(x)
    d.heading("After the Race")
    for x in ["Results are provisional immediately after the finish.","Protest window closes 24 hours after the checkered flag.","Official results and penalties are targeted within 48 hours.","Updated standings and Chase status follow official results."]: d.bullet(x)
    d.heading("Need Help?")
    d.para(f"Email {CONTACT} or use the PRL support channels in the Pitmark Discord. Website: {SITE}")
    return d.finish()

DOCS = {
    "driver-handbook": ("PRL_2027_Driver_Handbook.pdf", _driver_handbook),
    "competition-rulebook": ("PRL_2027_Competition_Rulebook.pdf", _competition_rulebook),
    "race-night-guide": ("PRL_2027_Race_Night_Guide.pdf", _race_night_guide),
}

@router.get("/prl/docs/{document}.pdf", include_in_schema=False)
def prl_public_pdf(document: str):
    item=DOCS.get(document)
    if not item:
        return Response(status_code=404)
    filename, builder=item
    data=builder()
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "public, max-age=3600",
        },
    )
