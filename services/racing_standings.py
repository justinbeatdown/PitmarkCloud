from __future__ import annotations

import copy
import io
import hashlib
import json
import logging
import re
import threading
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader
from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column

from services.database import Base, SessionLocal

log = logging.getLogger("pitmark.racing_standings")

USER_AGENT = "PitmarkRacingStandings/1.0 (+https://pitmarkracing.com)"
CACHE_SECONDS = 20 * 60

SERIES: tuple[dict[str, Any], ...] = (
    {
        "key": "nascar-cup",
        "name": "NASCAR Cup Series",
        "short_name": "Cup",
        "group": "NASCAR",
        "provider": "espn",
        "league": "nascar-premier",
        "official_url": "https://www.nascar.com/standings/nascar-cup-series/",
        "logo_source_url": "https://www.nascar.com/",
        "logo_url": "https://www.nascar.com/wp-content/uploads/sites/7/2023/05/10/nascar_cup_series_logo.svg",
        "metadata_provider": "nascar_driver_directory",
        "metadata_url": "https://www.nascar.com/drivers/nascar-cup-series/",
    },
    {
        "key": "nascar-oreilly",
        "name": "NASCAR O'Reilly Auto Parts Series",
        "short_name": "O'Reilly",
        "group": "NASCAR",
        "provider": "espn",
        "league": "nascar-secondary",
        "official_url": "https://www.nascar.com/standings/nascar-oreilly-auto-parts-series/",
        "logo_source_url": "https://www.nascar.com/",
        "logo_url": "https://www.nascar.com/wp-content/uploads/sites/7/2025/09/30/NOAPS-Primary_FullColor-RGB.svg",
        "metadata_provider": "nascar_driver_directory",
        "metadata_url": "https://www.nascar.com/drivers/nascar-oreilly-auto-parts-series/",
    },
    {
        "key": "nascar-truck",
        "name": "NASCAR CRAFTSMAN Truck Series",
        "short_name": "Trucks",
        "group": "NASCAR",
        "provider": "espn",
        "league": "nascar-truck",
        "official_url": "https://www.nascar.com/standings/nascar-craftsman-truck-series/",
        "logo_source_url": "https://www.nascar.com/",
        "logo_url": "https://www.nascar.com/wp-content/uploads/sites/7/2026/02/13/nascar-craftman-truck-series-1.svg",
        "metadata_provider": "nascar_driver_directory",
        "metadata_url": "https://www.nascar.com/drivers/nascar-craftsman-truck-series/",
    },
    {
        "key": "nascar-whelen-modified",
        "name": "NASCAR Whelen Modified Tour",
        "short_name": "Whelen Modified",
        "group": "NASCAR",
        "provider": "nascar_regional",
        "official_url": "https://www.nascar.com/regional/",
        "regional_heading": "Whelen Modified Tour",
        "logo_source_url": "https://www.nascar.com/whelen-modified-tour/",
        "logo_url": "https://www.nascar.com/wp-content/uploads/sites/7/2024/01/05/NWMT_Logo.svg",
        "metadata_provider": "nascar_driver_directory",
        "metadata_url": "https://www.nascar.com/nascar-whelen-modified-tour-drivers/",
        "source_name": "NASCAR Regional official Whelen Modified Tour standings",
        "name_headers": ("driver",),
        "position_headers": ("number", "pos", "position", "rank"),
        "number_headers": ("car #", "car no.", "no."),
        "points_headers": ("points",),
        "wins_headers": ("wins",),
        "starts_headers": ("races", "starts"),
    },
    {
        "key": "arca-east",
        "name": "ARCA Menards Series East",
        "short_name": "ARCA East",
        "group": "NASCAR",
        "provider": "nascar_regional",
        "official_url": "https://www.nascar.com/regional/",
        "regional_heading": "ARCA Menards East",
        "logo_source_url": "https://www.arcaracing.com/competitor-site/",
        "logo_url": "https://www.arcaracing.com/wp-content/uploads/sites/36/2021/02/02/ArcaMenardsSeries_East_ANASCARTouringDivision_Primary_4C_BLK.png",
        "metadata_provider": "arca_driver_directory",
        "metadata_url": "https://www.arcaracing.com/drivers-arca-menards-east/",
        "source_name": "NASCAR Regional official ARCA Menards East standings",
        "name_headers": ("driver",),
        "position_headers": ("number", "pos", "position", "rank"),
        "number_headers": ("car #", "car no.", "no."),
        "points_headers": ("points",),
        "wins_headers": ("wins",),
        "starts_headers": ("races", "starts"),
    },
    {
        "key": "arca-west",
        "name": "ARCA Menards Series West",
        "short_name": "ARCA West",
        "group": "NASCAR",
        "provider": "nascar_regional",
        "official_url": "https://www.nascar.com/regional/",
        "regional_heading": "ARCA Menards West",
        "logo_source_url": "https://www.arcaracing.com/competitor-site/",
        "logo_url": "https://www.arcaracing.com/wp-content/uploads/sites/36/2021/02/02/ArcaMenardsSeries_West_ANASCARTouringDivision_Primary_4C_BLK.png",
        "metadata_provider": "arca_driver_directory",
        "metadata_url": "https://www.arcaracing.com/drivers-arca-menards-west/",
        "source_name": "NASCAR Regional official ARCA Menards West standings",
        "name_headers": ("driver",),
        "position_headers": ("number", "pos", "position", "rank"),
        "number_headers": ("car #", "car no.", "no."),
        "points_headers": ("points",),
        "wins_headers": ("wins",),
        "starts_headers": ("races", "starts"),
    },
    {
        "key": "nascar-local",
        "name": "NASCAR Local Racing Series",
        "short_name": "NASCAR Local",
        "group": "Grassroots / Stock Cars",
        "provider": "official_table",
        "official_url": "https://www.nascar.com/local-racing-series/",
        "logo_source_url": "https://www.nascar.com/local-racing-series/",
        "source_name": "NASCAR Local Racing Series official standings",
        "name_headers": ("driver",),
        "number_headers": ("number", "no.", "no"),
        "points_headers": ("points",),
        "position_headers": ("pos", "position", "rank"),
        "wins_headers": ("wins",),
        "starts_headers": ("races", "starts"),
    },
    {
        "key": "ascs-national",
        "name": "American Sprint Car Series National Tour",
        "short_name": "ASCS",
        "group": "Grassroots / Dirt",
        "provider": "official_table",
        "official_url": "https://ascsracing.com/series-points/",
        "logo_source_url": "https://ascsracing.com/",
        "source_name": "ASCS official driver points",
        "name_headers": ("driver",),
        "number_headers": ("no.", "no", "number"),
        "points_headers": ("points",),
        "position_headers": ("pos.", "pos", "position"),
        "behind_headers": ("gap",),
        "wins_headers": ("wins",),
        "starts_headers": ("starts",),
    },
    {
        "key": "world-of-outlaws-sprint",
        "name": "World of Outlaws Sprint Car Series",
        "short_name": "WoO Sprint",
        "group": "Dirt",
        "provider": "official_table",
        "official_url": "https://worldofoutlaws.com/series-points/",
        "logo_source_url": "https://about.worldofoutlaws.com/how-to-watch",
        "logo_url": "https://about.worldofoutlaws.com/hubfs/2023-Fan%20101%20Microsite/images/NOS_SCS_LOGO_FINAL_RGB.svg",
        "source_name": "World of Outlaws official points",
        "name_headers": ("driver",),
        "points_headers": ("points",),
        "position_headers": ("pos", "position"),
        "behind_headers": ("gap",),
        "wins_headers": ("wins",),
        "starts_headers": ("starts",),
    },
    {
        "key": "world-of-outlaws-late-models",
        "name": "World of Outlaws Late Model Series",
        "short_name": "WoO Late Models",
        "group": "Dirt",
        "provider": "official_table",
        "official_url": "https://worldofoutlaws.com/latemodels/series-points/",
        "logo_source_url": "https://about.worldofoutlaws.com/how-to-watch",
        "logo_url": "https://about.worldofoutlaws.com/hs-fs/hubfs/WoOLM_200.png?height=125&name=WoOLM_200.png&width=200",
        "source_name": "World of Outlaws official points",
        "name_headers": ("driver",),
        "points_headers": ("points",),
        "position_headers": ("pos", "position"),
        "behind_headers": ("gap",),
        "wins_headers": ("wins",),
        "starts_headers": ("starts",),
    },
    {
        "key": "lucas-oil-late-models",
        "name": "Lucas Oil Late Model Dirt Series",
        "short_name": "Lucas Oil LM",
        "group": "Dirt",
        "provider": "official_table",
        "official_url": "https://www.lucasdirt.com/standings/",
        "logo_source_url": "https://www.lucasdirt.com/",
        "source_name": "Lucas Oil Late Model Dirt Series official standings",
        "name_headers": ("driver", "competitor"),
        "points_headers": ("points", "pts"),
        "position_headers": ("pos", "position", "rank"),
        "behind_headers": ("gap", "behind"),
        "wins_headers": ("wins",),
        "starts_headers": ("starts", "races"),
    },
    {
        "key": "high-limit-sprint",
        "name": "High Limit Racing",
        "short_name": "High Limit",
        "group": "Dirt",
        "provider": "official_table",
        "official_url": "https://www.highlimitracing.com/standings",
        "logo_source_url": "https://www.highlimitracing.com/",
        "logo_url": "https://cdn.myracepass.com/v1/siteresources/44498/v1/img/logo.png",
        "source_name": "High Limit Racing official standings",
        "name_headers": ("driver", "competitor"),
        "points_headers": ("points", "pts"),
        "position_headers": ("pos", "position", "rank"),
        "behind_headers": ("gap", "behind"),
        "wins_headers": ("wins",),
        "starts_headers": ("starts", "races", "features"),
        "fallback_urls": ("https://www.tonystewartracing.com/schedule/",),
    },
    {
        "key": "usac-national-sprint",
        "name": "USAC AMSOIL National Sprint",
        "short_name": "USAC Sprint",
        "group": "Dirt",
        "provider": "column_sections",
        "column_title": "Driver Standings",
        "official_url": "https://www.usacracing.com/series-point-standings/national-sprint",
        "logo_source_url": "https://www.usacracing.com/",
        "logo_url": "https://cdn.prod.website-files.com/65a055cdd264f6a7981147fe/65edc3afc8c77c845c80e17b_USAC_Racing_Logo_White.avif",
        "source_name": "USAC official standings",
        "name_headers": ("driver",),
        "points_headers": ("points",),
        "position_headers": ("pos", "position"),
        "wins_headers": ("wins",),
        "starts_headers": ("starts",),
    },
    {
        "key": "usac-national-midget",
        "name": "USAC NOS Energy Drink National Midget",
        "short_name": "USAC Midget",
        "group": "Dirt",
        "provider": "column_sections",
        "column_title": "Driver Standings",
        "official_url": "https://www.usacracing.com/series-point-standings/national-midget",
        "logo_source_url": "https://www.usacracing.com/",
        "logo_url": "https://cdn.prod.website-files.com/65a055cdd264f6a7981147fe/65edc3afc8c77c845c80e17b_USAC_Racing_Logo_White.avif",
        "source_name": "USAC official standings",
        "name_headers": ("driver",),
        "points_headers": ("points",),
        "position_headers": ("pos", "position"),
        "wins_headers": ("wins",),
        "starts_headers": ("starts",),
    },
    {
        "key": "usac-silver-crown",
        "name": "USAC Silver Crown",
        "short_name": "Silver Crown",
        "group": "Dirt / Pavement",
        "provider": "column_sections",
        "column_title": "Driver Standings",
        "official_url": "https://www.usacracing.com/series-point-standings/silver-crown",
        "logo_source_url": "https://www.usacracing.com/",
        "logo_url": "https://cdn.prod.website-files.com/65a055cdd264f6a7981147fe/65edc3afc8c77c845c80e17b_USAC_Racing_Logo_White.avif",
        "source_name": "USAC official standings",
        "name_headers": ("driver",),
        "points_headers": ("points",),
        "position_headers": ("pos", "position"),
        "wins_headers": ("wins",),
        "starts_headers": ("starts",),
    },
    {
        "key": "arca-menards",
        "name": "ARCA Menards Series",
        "short_name": "ARCA",
        "group": "Stock Cars",
        "provider": "official_table",
        "official_url": "https://www.arcaracing.com/standings/arca-menards-series/",
        "logo_source_url": "https://www.arcaracing.com/competitor-site/",
        "logo_url": "https://www.arcaracing.com/wp-content/uploads/sites/36/2022/11/10/Menards_ANASCARTouringDivision_Primary_4C_BLK.png",
        "metadata_provider": "arca_driver_directory",
        "metadata_url": "https://www.arcaracing.com/driver-list/",
        "source_name": "ARCA official standings",
        "name_headers": ("driver", "name"),
        "points_headers": ("points", "pts"),
        "position_headers": ("pos", "position", "rank", "column 1"),
        "behind_headers": ("diff", "behind"),
        "wins_headers": ("wins", "win"),
        "starts_headers": ("races", "starts"),
        "fallback_urls": ("https://theconwaybulletin.com/league/arca/standings/",),
    },
    {
        "key": "cars-tour-lmsc",
        "name": "zMAX CARS Tour — Late Model Stock",
        "short_name": "CARS LMSC",
        "group": "Short Track",
        "provider": "official_table",
        "official_url": "https://www.carsracingtour.com/standings-lmsc/",
        "logo_source_url": "https://www.carsracingtour.com/",
        "logo_url": "https://www.carsracingtour.com/wp-content/uploads/sites/61/2024/05/09/ZMAXGeneric.jpg",
        "source_name": "zMAX CARS Tour official LMSC standings",
        "name_headers": ("driver",),
        "number_headers": ("num", "number", "#"),
        "points_headers": ("points", "pts"),
        "position_headers": ("pos", "position", "rank"),
        "behind_headers": ("gap", "behind"),
        "wins_headers": ("wins",),
        "starts_headers": ("events", "starts", "races"),
    },
    {
        "key": "asa-stars",
        "name": "ASA STARS National Tour",
        "short_name": "ASA STARS",
        "group": "Short Track",
        "provider": "linked_pdf",
        "official_url": "https://starsnationaltour.com/stats/standings/",
        "logo_source_url": "https://starsnationaltour.com/asa-stars-national-tour-reveals-its-official-logo/",
        "logo_url": "https://slms.dev/data/2023/01/ASA-STARS-National-Tour-Logo-2000px-TEMP-1024x650.webp",
        "source_name": "ASA STARS official standings",
        "pdf_link_text": "Driver Standings",
        "pdf_format": "asa_stars",
    },
    {
        "key": "smart-modified",
        "name": "SMART Modified Tour",
        "short_name": "SMART Mods",
        "group": "Short Track",
        "provider": "linked_pdf",
        "official_url": "https://smartmodifiedtour.com/standings",
        "logo_source_url": "https://smartmodifiedtour.com/history",
        "logo_url": "https://img1.wsimg.com/isteam/ip/32d806cc-87e5-46d0-87cb-e81ce9615680/SMART%20LOGO%20CUBE%20copy.jpg/%3A/cr%3Dt%3A25%25%2Cl%3A0%25%2Cw%3A100%25%2Ch%3A50%25/rs%3Dw%3A600%2Ch%3A300%2Ccg%3Atrue",
        "source_name": "SMART Modified Tour official standings",
        "pdf_link_text": "Click to Download PDF",
        "pdf_format": "smart_modified",
    },
    {
        "key": "dirtcar-late-model",
        "name": "DIRTcar Late Model National Points",
        "short_name": "DIRTcar Late Model",
        "group": "Grassroots / Dirt",
        "provider": "official_table",
        "official_url": "https://dirtcar.com/points/late-model-points/national/",
        "logo_source_url": "https://dirtcar.com/",
        "source_name": "DIRTcar Late Model official national points",
        "name_headers": ("driver",),
        "number_headers": ("car #", "car", "number"),
        "points_headers": ("points",),
        "position_headers": ("pos", "position"),
        "behind_headers": ("behind",),
        "wins_headers": ("wins",),
        "starts_headers": ("races",),
    },
    {
        "key": "dirtcar-ump-modified",
        "name": "DIRTcar UMP Modified National Points",
        "short_name": "DIRTcar UMP Modified",
        "group": "Grassroots / Dirt",
        "provider": "official_table",
        "official_url": "https://dirtcar.com/points/ump-modified-points/national/",
        "logo_source_url": "https://dirtcar.com/",
        "source_name": "DIRTcar UMP Modified official national points",
        "name_headers": ("driver",),
        "number_headers": ("car #", "car", "number"),
        "points_headers": ("points",),
        "position_headers": ("pos", "position"),
        "behind_headers": ("behind",),
        "wins_headers": ("wins",),
        "starts_headers": ("races",),
    },
    {
        "key": "dirtcar-stock-car",
        "name": "DIRTcar Stock Car National Points",
        "short_name": "DIRTcar Stock Car",
        "group": "Grassroots / Dirt",
        "provider": "official_table",
        "official_url": "https://dirtcar.com/points/stock-car-points/national/",
        "logo_source_url": "https://dirtcar.com/",
        "source_name": "DIRTcar Stock Car official national points",
        "name_headers": ("driver",),
        "number_headers": ("car #", "car", "number"),
        "points_headers": ("points",),
        "position_headers": ("pos", "position"),
        "behind_headers": ("behind",),
        "wins_headers": ("wins",),
        "starts_headers": ("races",),
    },
    {
        "key": "dirtcar-pro-modified",
        "name": "DIRTcar Pro Modified National Points",
        "short_name": "DIRTcar Pro Modified",
        "group": "Grassroots / Dirt",
        "provider": "official_table",
        "official_url": "https://dirtcar.com/points/pro-modified-points/national/",
        "logo_source_url": "https://dirtcar.com/",
        "source_name": "DIRTcar Pro Modified official national points",
        "name_headers": ("driver",),
        "number_headers": ("car #", "car", "number"),
        "points_headers": ("points",),
        "position_headers": ("pos", "position"),
        "behind_headers": ("behind",),
        "wins_headers": ("wins",),
        "starts_headers": ("races",),
    },
    {
        "key": "dirtcar-sport-compact",
        "name": "DIRTcar Sport Compact National Points",
        "short_name": "DIRTcar Sport Compact",
        "group": "Grassroots / Dirt",
        "provider": "official_table",
        "official_url": "https://dirtcar.com/points/sport-compact-points/national/",
        "logo_source_url": "https://dirtcar.com/",
        "source_name": "DIRTcar Sport Compact official national points",
        "name_headers": ("driver",),
        "number_headers": ("car #", "car", "number"),
        "points_headers": ("points",),
        "position_headers": ("pos", "position"),
        "behind_headers": ("behind",),
        "wins_headers": ("wins",),
        "starts_headers": ("races",),
    },
    {
        "key": "dirtcar-factory-stock",
        "name": "DIRTcar Factory Stock National Points",
        "short_name": "DIRTcar Factory Stock",
        "group": "Grassroots / Dirt",
        "provider": "official_table",
        "official_url": "https://dirtcar.com/points/factory-stock-points/national/",
        "logo_source_url": "https://dirtcar.com/",
        "source_name": "DIRTcar Factory Stock official national points",
        "name_headers": ("driver",),
        "number_headers": ("car #", "car", "number"),
        "points_headers": ("points",),
        "position_headers": ("pos", "position"),
        "behind_headers": ("behind",),
        "wins_headers": ("wins",),
        "starts_headers": ("races",),
    },
    {
        "key": "nhra-top-fuel",
        "logo_source_url": "https://www.nhra.com/media-center/logos",
        "logo_url": "https://upload.wikimedia.org/wikipedia/commons/5/54/National_Hot_Rod_Association_Logo.svg",
        "name": "NHRA Top Fuel",
        "short_name": "NHRA Top Fuel",
        "group": "Drag Racing",
        "provider": "official_table",
        "official_url_template": "https://www.nhra.com/standings/{season}/nhra-mission-foods-drag-racing-series/nhra-mission-foods-drag-racing-series?tab=top-fuel",
        "source_name": "NHRA official standings",
        "name_headers": ("driver",),
        "points_headers": ("points",),
        "position_headers": ("position", "pos"),
        "behind_headers": ("points behind leader", "behind"),
    },
    {
        "key": "nhra-funny-car",
        "logo_source_url": "https://www.nhra.com/media-center/logos",
        "logo_url": "https://upload.wikimedia.org/wikipedia/commons/5/54/National_Hot_Rod_Association_Logo.svg",
        "name": "NHRA Funny Car",
        "short_name": "NHRA Funny Car",
        "group": "Drag Racing",
        "provider": "official_table",
        "official_url_template": "https://www.nhra.com/standings/{season}/nhra-mission-foods-drag-racing-series/nhra-mission-foods-drag-racing-series?tab=funny-car",
        "source_name": "NHRA official standings",
        "name_headers": ("driver",),
        "points_headers": ("points",),
        "position_headers": ("position", "pos"),
        "behind_headers": ("points behind leader", "behind"),
    },
    {
        "key": "nhra-pro-stock",
        "logo_source_url": "https://www.nhra.com/media-center/logos",
        "logo_url": "https://upload.wikimedia.org/wikipedia/commons/5/54/National_Hot_Rod_Association_Logo.svg",
        "name": "NHRA Pro Stock",
        "short_name": "NHRA Pro Stock",
        "group": "Drag Racing",
        "provider": "official_table",
        "official_url_template": "https://www.nhra.com/standings/{season}/nhra-mission-foods-drag-racing-series/nhra-mission-foods-drag-racing-series?tab=pro-stock",
        "source_name": "NHRA official standings",
        "name_headers": ("driver",),
        "points_headers": ("points",),
        "position_headers": ("position", "pos"),
        "behind_headers": ("points behind leader", "behind"),
    },
    {
        "key": "nhra-pro-stock-motorcycle",
        "logo_source_url": "https://www.nhra.com/media-center/logos",
        "logo_url": "https://upload.wikimedia.org/wikipedia/commons/5/54/National_Hot_Rod_Association_Logo.svg",
        "name": "NHRA Pro Stock Motorcycle",
        "short_name": "NHRA PSM",
        "group": "Drag Racing",
        "provider": "official_table",
        "official_url_template": "https://www.nhra.com/standings/{season}/nhra-mission-foods-drag-racing-series/nhra-mission-foods-drag-racing-series?tab=pro-stock-motorcycle",
        "source_name": "NHRA official standings",
        "name_headers": ("driver",),
        "points_headers": ("points",),
        "position_headers": ("position", "pos"),
        "behind_headers": ("points behind leader", "behind"),
    },
    {
        "key": "f1",
        "name": "Formula 1",
        "short_name": "F1",
        "group": "Open Wheel",
        "provider": "jolpica",
        "official_url_template": "https://www.formula1.com/en/results/{season}/drivers",
        "metadata_url": "https://www.formula1.com/en/results/2026/races/1287/spain/race-result",
        "name_headers": ("driver",),
        "team_headers": ("team",),
        "logo_source_url": "https://www.formula1.com/",
        "logo_url": "https://upload.wikimedia.org/wikipedia/commons/3/33/F1.svg",
    },
    {
        "key": "indycar",
        "name": "NTT INDYCAR SERIES",
        "short_name": "INDYCAR",
        "group": "Open Wheel",
        "provider": "espn",
        "league": "irl",
        "official_url": "https://www.indycar.com/standings",
        "logo_source_url": "https://www.indycar.com/",
        "logo_url": "https://www.indycar.com/-/media/IndyCar/Content/Footer/indycar-horizontal.png",
        "metadata_provider": "indycar_driver_directory",
        "metadata_url": "https://www.indycar.com/Drivers",
        "official_identity_hosts": ("www.indycar.com", "indycar.com"),
    },
    {
        "key": "formula-e",
        "name": "ABB FIA Formula E World Championship",
        "short_name": "Formula E",
        "group": "Open Wheel",
        "provider": "official_table",
        "official_url_template": "https://www.fiaformulae.com/en/results-and-standings?season={fe_season}&tab=drivers",
        "logo_source_url": "https://www.fiaformulae.com/en/results-and-standings?season=12&tab=drivers",
        "logo_url": "https://www.fiaformulae.com/images/formula-e-footer.svg",
        "source_name": "Formula E official standings",
        "name_headers": ("driver",),
        "points_headers": ("pts", "points"),
        "position_headers": ("pos", "position"),
        "team_headers": ("team",),
    },
    {
        "key": "imsa-weathertech",
        "name": "IMSA WeatherTech — GTP Drivers",
        "short_name": "IMSA GTP",
        "group": "Sports Cars",
        "provider": "imsa",
        "official_url": "https://www.imsa.com/weathertech/standings/",
        "logo_source_url": "https://www.imsa.com/media-center/",
        "logo_url": "https://www.imsa.com/wp-content/uploads/sites/32/2025/12/08/2025_IWSC_Logo_MediaCenter.png",
    },
    {
        "key": "imsa-michelin-pilot",
        "name": "IMSA Michelin Pilot Challenge",
        "short_name": "IMSA Pilot",
        "group": "Sports Cars",
        "provider": "imsa_linked_pdf",
        "official_url": "https://www.imsa.com/michelinpilotchallenge/standings/",
        "logo_source_url": "https://www.imsa.com/media-center/",
        "logo_url": "https://www.imsa.com/wp-content/uploads/sites/32/2025/12/08/2025_IMPC_Logo_MediaCenter.png",
        "pdf_link_text": "click here",
        "pdf_url": "https://www.imsa.com/wp-content/uploads/sites/32/2026/08/31/2026_IMPC_VIR_OfficialPoints.pdf",
        "pdf_section_title": "IMSA Michelin Pilot Challenge Grand Sport Drivers",
        "source_name": "IMSA Michelin Pilot Challenge official points",
    },
    {
        "key": "imsa-vp-racing",
        "name": "IMSA VP Racing SportsCar Challenge",
        "short_name": "IMSA VP Racing",
        "group": "Sports Cars",
        "provider": "imsa_linked_pdf",
        "official_url": "https://www.imsa.com/vpracingsportscarchallenge/standings/",
        "logo_source_url": "https://www.imsa.com/media-center/",
        "logo_url": "https://www.imsa.com/wp-content/uploads/sites/32/2025/12/08/2025_VPRC_Logo_MediaCenter.png",
        "pdf_link_text": "click here",
        "pdf_url": "https://www.imsa.com/wp-content/uploads/sites/32/2026/08/31/2026_VPRC_VIR_OfficialPoints.pdf",
        "pdf_section_title": "IMSA VP Racing Sportscar Challenge P3 Drivers",
        "source_name": "IMSA VP Racing SportsCar Challenge official points",
    },
    {
        "key": "wec",
        "name": "FIA World Endurance Championship",
        "short_name": "WEC",
        "group": "Sports Cars",
        "provider": "wec",
        "official_url": "https://www.fiawec.com/en/page/drivers-classification/34",
        "logo_source_url": "https://www.fiawec.com/en/page/drivers-classification/34",
        "logo_url": "https://www.fiawec.com/uploads/wec-logo-69d50a53ddfee895249122.png",
    },
    {
        "key": "supercars",
        "name": "Repco Supercars Championship",
        "short_name": "Supercars",
        "group": "Touring Cars",
        "provider": "official_table",
        "official_url_template": "https://www.supercars.com/standings/{season}/supercars",
        "logo_source_url": "https://www.supercars.com/news/supercars-reveals-new-logo-and-hashtag",
        "logo_url": "https://www.supercars.com/_next/image?q=100&url=https%3A%2F%2Fimages.ctfassets.net%2Fxd502h20t7lh%2F22NjnKq2xXMiZOUr1QGFsw%2F9e39b09bd650317a5721180d638e82de%2Flogo-main.jpg&w=3840",
        "source_name": "Supercars official standings",
        "name_headers": ("driver",),
        "points_headers": ("pts", "points"),
        "position_headers": ("pos", "position"),
        "behind_headers": ("gap",),
        "wins_headers": ("wins",),
    },
    {
        "key": "motogp",
        "name": "MotoGP World Championship",
        "short_name": "MotoGP",
        "group": "Motorcycles",
        "provider": "official_table",
        "official_url": "https://stats.motogp.com/en/world-standing",
        "official_identity_hosts": ("stats.motogp.com", "www.motogp.com"),
        "metadata_provider": "motogp_riders",
        "metadata_url": "https://www.motogp.com/en/riders/",
        "logo_source_url": "https://www.motogp.com/",
        "logo_url": "https://upload.wikimedia.org/wikipedia/commons/f/f9/MotoGP_logo_%282024%29.svg",
        "source_name": "MotoGP official statistics",
        "name_headers": ("rider",),
        "points_headers": ("points", "pts"),
        "position_headers": ("pos", "position"),
        "behind_headers": ("gap",),
        "team_headers": ("team",),
        "manufacturer_headers": ("bike",),
        "fallback_url_templates": (
            "https://www.motogp.com/en/world-standing/{season}/motogp/team-standings",
        ),
    },
)
 
OFFICIAL_LOGO_TERMS: dict[str, tuple[str, ...]] = {
    "nascar-cup": ("nascar cup", "cup series"),
    "nascar-oreilly": ("o'reilly auto parts", "oreilly auto parts"),
    "nascar-truck": ("craftsman truck", "truck series"),
    "world-of-outlaws-sprint": ("world of outlaws", "outlaws sprint"),
    "world-of-outlaws-late-models": ("world of outlaws", "outlaws late model"),
    "lucas-oil-late-models": ("lucas oil late model", "late model dirt series"),
    "high-limit-sprint": ("high limit racing", "high limit"),
    "usac-national-sprint": ("usac",),
    "usac-national-midget": ("usac",),
    "usac-silver-crown": ("usac", "silver crown"),
    "arca-menards": ("arca menards", "arca"),
    "cars-tour-lmsc": ("cars tour", "zmax cars"),
    "asa-stars": ("asa stars", "stars national tour"),
    "smart-modified": ("smart modified", "smart tour"),
    "nhra-top-fuel": ("nhra",),
    "nhra-funny-car": ("nhra",),
    "nhra-pro-stock": ("nhra",),
    "nhra-pro-stock-motorcycle": ("nhra",),
    "f1": ("formula 1", "f1"),
    "indycar": ("indycar",),
    "formula-e": ("formula e",),
    "imsa-weathertech": ("imsa", "weathertech"),
    "imsa-michelin-pilot": ("imsa", "michelin pilot"),
    "imsa-vp-racing": ("imsa", "vp racing"),
    "wec": ("fia wec", "world endurance championship"),
    "supercars": ("supercars",),
    "motogp": ("motogp",),
}

NUMBER_HEADERS = (
    "#", "no", "no.", "num", "number", "car", "car #", "car no", "car no.",
    "vehicle no", "vehicle #", "bike #", "rider #",
)
TEAM_HEADERS = ("team", "entrant", "organization")
MANUFACTURER_HEADERS = ("manufacturer", "make", "marque", "bike", "constructor")

# Verified 2026 NASCAR identity fallback. NASCAR blocks Render's datacenter IPs
# and the rendered-reader service can rate-limit. These values come from
# NASCAR-owned 2026 driver profiles; live official directory data overrides
# them whenever it is available.
NASCAR_2026_IDENTITY_FALLBACK: dict[str, dict[str, dict[str, str | None]]] = {
    "nascar-cup": {
        "kylelarson": {"number": "5", "team": "Hendrick Motorsports", "manufacturer": "Chevrolet"},
        "dennyhamlin": {"number": "11", "team": "Joe Gibbs Racing", "manufacturer": "Toyota"},
        "joeylogano": {"number": "22", "team": "Team Penske", "manufacturer": "Ford"},
        "christopherbell": {"number": "20", "team": "Joe Gibbs Racing", "manufacturer": "Toyota"},
        "tygibbs": {"number": "54", "team": "Joe Gibbs Racing", "manufacturer": "Toyota"},
        "carsonhocevar": {"number": "77", "team": "Spire Motorsports", "manufacturer": "Chevrolet"},
    },
    "nascar-oreilly": {
        "sheldoncreed": {"number": "00", "team": "Haas Factory Team", "manufacturer": "Chevrolet"},
        "justinallgaier": {"number": "7", "team": "JR Motorsports", "manufacturer": "Chevrolet"},
        "carsonkvapil": {"number": "1", "team": "JR Motorsports", "manufacturer": "Chevrolet"},
        "jesselove": {"number": "2", "team": "Richard Childress Racing", "manufacturer": "Chevrolet"},
        "sammayer": {"number": "41", "team": "Haas Factory Team", "manufacturer": "Chevrolet"},
    },
    "nascar-truck": {
        "layneriggs": {"number": "34", "team": "Front Row Motorsports", "manufacturer": "Ford"},
        "kadenhoneycutt": {"number": "11", "team": "TRICON Garage", "manufacturer": "Toyota"},
        "chandlersmith": {"number": "38", "team": "Front Row Motorsports", "manufacturer": "Ford"},
        "tymajeski": {"number": "88", "team": "ThorSport Racing", "manufacturer": "Ford"},
        "giovanniruggiero": {"number": "17", "team": "TRICON Garage", "manufacturer": "Toyota"},
    },
}

CARS_2026_LMSC_FALLBACK: list[dict[str, Any]] = [
    {"position": 1, "number": "88", "name": "Caden Kvapil", "starts": 10, "wins": 2, "points": 380, "behind": 0},
    {"position": 2, "number": "77L", "name": "Treyten Lapcevich", "starts": 10, "wins": 0, "points": 359, "behind": -21},
    {"position": 3, "number": "44", "name": "Conner Jones", "starts": 10, "wins": 1, "points": 342, "behind": -38},
    {"position": 4, "number": "16", "name": "Chad McCumbee", "starts": 10, "wins": 0, "points": 314, "behind": -66},
    {"position": 5, "number": "5B", "name": "Chase Burrow", "starts": 10, "wins": 0, "points": 305, "behind": -75},
    {"position": 6, "number": "20", "name": "Carson Loftin", "starts": 10, "wins": 1, "points": 288, "behind": -92},
    {"position": 7, "number": "5", "name": "Carson Brown", "starts": 9, "wins": 0, "points": 285, "behind": -95},
    {"position": 8, "number": "57", "name": "Landon Huffman", "starts": 10, "wins": 0, "points": 277, "behind": -103},
    {"position": 9, "number": "4", "name": "Parker Eatmon", "starts": 9, "wins": 0, "points": 272, "behind": -108},
    {"position": 10, "number": "29", "name": "Landen Lewis", "starts": 8, "wins": 1, "points": 271, "behind": -109},
    {"position": 11, "number": "95", "name": "London McKenzie", "starts": 10, "wins": 0, "points": 265, "behind": -115},
    {"position": 12, "number": "04", "name": "Ronnie Bassett Jr.", "starts": 9, "wins": 0, "points": 211, "behind": -169},
]


LUCAS_2026_FULL_STANDINGS: list[dict[str, Any]] = [
    {"position": 1, "number": "1", "name": "Brandon Sheppard", "points": 6305},
    {"position": 2, "number": "71", "name": "Hudson O'Neal", "points": 6250},
    {"position": 3, "number": "99", "name": "Devin Moran", "points": 6200},
    {"position": 4, "number": "76", "name": "Brandon Overton", "points": 5855},
    {"position": 5, "number": "20RT", "name": "Ricky Thornton Jr", "points": 5800},
    {"position": 6, "number": "111", "name": "Max Blair", "points": 5720},
    {"position": 7, "number": "11", "name": "Josh Rice", "points": 5430},
    {"position": 8, "number": "3s", "name": "Brian Shirley", "points": 5405},
    {"position": 9, "number": "58", "name": "Garrett Alberson", "points": 5370},
    {"position": 10, "number": "40B", "name": "Kyle Bronson", "points": 5070},
    {"position": 11, "number": "6", "name": "Clay Harris", "points": 5060},
    {"position": 12, "number": "93", "name": "Carson Ferguson", "points": 5015},
    {"position": 13, "number": "60", "name": "Dan Ebert", "points": 4975},
    {"position": 14, "number": "8", "name": "Dillon McCowan", "points": 4845},
    {"position": 15, "number": "22", "name": "Daniel Hilsabeck", "points": 4390},
    {"position": 16, "number": "17SS", "name": "Brenden Smith", "points": 4035},
    {"position": 17, "number": "93L", "name": "Cory Lawler", "points": 3720},
]

HIGH_LIMIT_2026_ROSTER_SUPPLEMENT: list[dict[str, Any]] = [
    {"number": "5", "name": "Brenham Crouch", "team": "CJB Motorsports"},
    {"number": "9R", "name": "Chase Randall", "team": "Chase Randall Racing"},
    {"number": "42", "name": "Sye Lynch", "team": "Mosites Lynch Racing"},
    {"number": "24D", "name": "Danny Sams III", "team": "Randerson Racing"},
    {"number": "17GP", "name": "Brock Zearfoss", "team": "Michael Dutcher Motorsports"},
]


IMSA_2026_STANDINGS_FALLBACK: dict[str, list[tuple[int, str, int]]] = {
    "imsa-michelin-pilot": [
        (1, "Dillon Machavern", 2010), (1, "Luca Mars", 2010),
        (2, "Austin Krainz", 1930), (2, "Stevan McAleer", 1930),
        (3, "Robert Noaker", 1910), (4, "Nate Cicero", 1810),
        (5, "Bryce Ward", 1780), (6, "Caio Chaves", 1780),
        (7, "Michael Cooper", 1720), (7, "Moisey Uretsky", 1720),
        (8, "Trenton Estep", 1710), (8, "Allen Patten", 1710),
        (9, "Hannah Greenemeier", 1630), (9, "Hannah Grisham", 1630),
        (10, "Morgan Burkhard", 1510), (10, "Gordon Scully", 1510),
    ],
    "imsa-vp-racing": [
        (1, "Ari Balogh", 1230), (1, "Garett Grist", 1230),
        (2, "Wyatt Brichacek", 1190), (3, "Valentino Catalano", 1180),
        (3, "Oscar Tunjo", 1180), (4, "Patrick Kujala", 1160),
        (4, "Brian Thienes", 1160), (5, "Danny Soufi", 1050),
        (5, "Jake Williamson", 1050), (6, "Travis Hill", 1010),
        (7, "Lincoln Day", 840), (8, "Matt Forbush", 790),
        (9, "Jagger Jones", 760), (9, "Farhan Siddiqi", 760),
        (10, "Nicole Havrda", 760), (11, "Jules Caranta", 550),
        (12, "Jon Hirshberg", 510), (12, "Patrick Liddy", 510),
        (13, "Daniel Oliver", 460), (14, "Titus Sherlock", 350),
        (15, "Andy Lee", 260), (15, "Slade Stewart", 260),
        (16, "Tom Long", 240), (17, "Brady Clapham", 220),
        (17, "Chris McMurry", 220), (18, "Martin Bruhat", 210),
    ],
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


DRIVER_IDENTITY_RESOLVER_VERSION = 4


class RaceCenterDriverIdentityCache(Base):
    __tablename__ = "race_center_driver_identity_cache"
    __table_args__ = (
        UniqueConstraint(
            "series_key",
            "season",
            "driver_key",
            name="uq_race_center_driver_identity_cache",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    series_key: Mapped[str] = mapped_column(String(120), index=True)
    season: Mapped[int] = mapped_column(Integer, index=True)
    driver_key: Mapped[str] = mapped_column(String(180), index=True)
    driver_name: Mapped[str] = mapped_column(String(180))
    number: Mapped[str] = mapped_column(String(40), default="")
    team: Mapped[str] = mapped_column(String(220), default="")
    manufacturer: Mapped[str] = mapped_column(String(120), default="")
    bio: Mapped[str] = mapped_column(Text, default="")
    photo_url: Mapped[str] = mapped_column(Text, default="")
    photo_use_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    photo_source_url: Mapped[str] = mapped_column(Text, default="")
    photo_license: Mapped[str] = mapped_column(String(160), default="")
    photo_attribution: Mapped[str] = mapped_column(Text, default="")
    source_kind: Mapped[str] = mapped_column(String(40), default="")
    source_name: Mapped[str] = mapped_column(String(160), default="")
    source_url: Mapped[str] = mapped_column(Text, default="")
    official_source_url: Mapped[str] = mapped_column(Text, default="")
    secondary_source_url: Mapped[str] = mapped_column(Text, default="")
    field_sources_json: Mapped[str] = mapped_column(Text, default="{}")
    resolver_version: Mapped[int] = mapped_column(Integer, default=DRIVER_IDENTITY_RESOLVER_VERSION)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class RacingStandingSnapshot(Base):
    __tablename__ = "racing_standing_snapshots"
    __table_args__ = (
        UniqueConstraint("series_key", "season", "fingerprint", name="uq_racing_standing_snapshot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    series_key: Mapped[str] = mapped_column(String(64), index=True)
    season: Mapped[int] = mapped_column(Integer, index=True)
    source_name: Mapped[str] = mapped_column(String(120))
    source_url: Mapped[str] = mapped_column(Text)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    payload_json: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


_cache_lock = threading.Lock()
_cache: dict[str, Any] = {"at": None, "value": None}
_snapshot_cache: dict[str, Any] = {"at": None, "season": None, "value": None}
SNAPSHOT_CACHE_SECONDS = 90
_profile_metadata_lock = threading.Lock()
_profile_metadata_cache: dict[str, tuple[datetime, dict[str, dict[str, str | None]], str | None]] = {}


def _num(value: Any) -> float | None:
    if value is None:
        return None
    raw = str(value).strip().replace(",", "").replace("+", "")
    if not raw or raw in {"—", "-", "null", "None"}:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _clean_points(value: Any) -> int | float | str | None:
    number = _num(value)
    if number is None:
        text = str(value or "").strip()
        return text or None
    return int(number) if number.is_integer() else number


def _fingerprint(entries: list[dict[str, Any]]) -> str:
    stable = [
        {
            "position": item.get("position"),
            "name": item.get("name"),
            "points": item.get("points"),
            "wins": item.get("wins"),
        }
        for item in entries
    ]
    raw = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _stats_map(entry: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for stat in entry.get("stats") or []:
        if not isinstance(stat, dict):
            continue
        names = [
            stat.get("name"),
            stat.get("abbreviation"),
            stat.get("displayName"),
            stat.get("shortDisplayName"),
        ]
        value = stat.get("displayValue")
        if value in (None, ""):
            value = stat.get("value")
        for name in names:
            if name:
                result[str(name).strip().lower()] = value
    return result


def _entity_name(value: Any) -> tuple[str, str | None]:
    if not isinstance(value, dict):
        return "", None
    name = (
        value.get("displayName")
        or value.get("fullName")
        or value.get("name")
        or value.get("shortName")
        or ""
    )
    team = None
    if isinstance(value.get("team"), dict):
        team = value["team"].get("displayName") or value["team"].get("name")
    return str(name).strip(), str(team).strip() if team else None


def _find_espn_entries(payload: Any) -> list[dict[str, Any]]:
    candidates: list[list[dict[str, Any]]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            standings = node.get("standings")
            if isinstance(standings, dict) and isinstance(standings.get("entries"), list):
                candidates.append([x for x in standings["entries"] if isinstance(x, dict)])
            entries = node.get("entries")
            if isinstance(entries, list) and entries and all(isinstance(x, dict) for x in entries):
                if any(("athlete" in x or "team" in x) and "stats" in x for x in entries):
                    candidates.append(entries)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(payload)
    if not candidates:
        return []
    return max(candidates, key=len)


def _fetch_espn(config: dict[str, str], season: int) -> dict[str, Any]:
    league = config["league"]
    urls = (
        f"https://site.web.api.espn.com/apis/v2/sports/racing/{league}/standings?season={season}&seasontype=1&type=0&level=3",
        f"https://site.api.espn.com/apis/v2/sports/racing/{league}/standings?season={season}",
    )
    last_error = ""
    with httpx.Client(timeout=14.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        for url in urls:
            try:
                response = client.get(url)
                response.raise_for_status()
                payload = response.json()
                raw_entries = _find_espn_entries(payload)
                if not raw_entries:
                    last_error = "structured standings were empty"
                    continue
                normalized: list[dict[str, Any]] = []
                for index, row in enumerate(raw_entries, start=1):
                    athlete = row.get("athlete") or row.get("team") or row.get("competitor") or {}
                    name, team = _entity_name(athlete)
                    if not name and isinstance(row.get("name"), str):
                        name = row["name"].strip()
                    if not name:
                        continue
                    stats = _stats_map(row)
                    position = (
                        row.get("position")
                        or stats.get("rank")
                        or stats.get("position")
                        or stats.get("pos")
                        or index
                    )
                    try:
                        position = int(float(str(position)))
                    except (TypeError, ValueError):
                        position = index
                    points = (
                        stats.get("points")
                        or stats.get("pts")
                        or stats.get("championship points")
                        or stats.get("championshippoints")
                    )
                    wins = stats.get("wins") or stats.get("w")
                    behind = stats.get("behind") or stats.get("gb") or stats.get("points behind")
                    starts = stats.get("starts") or stats.get("races")
                    normalized.append(
                        {
                            "position": position,
                            "name": name,
                            "number": None,
                            "team": None,
                            "manufacturer": None,
                            "points": _clean_points(points),
                            "behind": _clean_points(behind),
                            "wins": _clean_points(wins),
                            "starts": _clean_points(starts),
                        }
                    )
                if normalized:
                    normalized.sort(key=lambda x: x["position"])
                    return {
                        "entries": normalized,
                        "source_name": "ESPN structured racing feed",
                        "provider_url": url,
                    }
                last_error = "standings entries could not be normalized"
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
    raise RuntimeError(last_error or "ESPN standings unavailable")


def _fetch_f1(config: dict[str, str], season: int) -> dict[str, Any]:
    url = f"https://api.jolpi.ca/ergast/f1/{season}/driverstandings.json"
    with httpx.Client(timeout=14.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        response = client.get(url)
        response.raise_for_status()
        payload = response.json()
    lists = (
        payload.get("MRData", {})
        .get("StandingsTable", {})
        .get("StandingsLists", [])
    )
    if not lists:
        raise RuntimeError("F1 standings response was empty")
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(lists[0].get("DriverStandings") or [], start=1):
        driver = row.get("Driver") or {}
        constructors = row.get("Constructors") or []
        team = constructors[0].get("name") if constructors and isinstance(constructors[0], dict) else None
        name = " ".join(
            part for part in [driver.get("givenName"), driver.get("familyName")] if part
        ).strip() or driver.get("code") or f"Driver {index}"
        normalized.append(
            {
                "position": int(row.get("position") or index),
                "name": name,
                "number": None,
                "team": None,
                "manufacturer": None,
                "points": _clean_points(row.get("points")),
                "behind": None,
                "wins": _clean_points(row.get("wins")),
                "starts": None,
            }
        )
    if not normalized:
        raise RuntimeError("F1 standings had no drivers")
    return {"entries": normalized, "source_name": "Jolpica F1", "provider_url": url}


def _parse_html_tables(html: str) -> list[tuple[list[str], list[list[str]]]]:
    soup = BeautifulSoup(html, "html.parser")
    tables: list[tuple[list[str], list[list[str]]]] = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        header: list[str] = []
        body: list[list[str]] = []
        for row_index, row in enumerate(rows):
            cell_nodes = row.find_all(["th", "td"], recursive=False)
            if not cell_nodes:
                cell_nodes = row.find_all(["th", "td"])
            cells = [
                " ".join(cell.get_text(" ", strip=True).split())
                for cell in cell_nodes
            ]
            if not cells:
                continue
            in_thead = row.find_parent("thead") is not None
            all_header_cells = bool(cell_nodes) and all(getattr(cell, "name", "") == "th" for cell in cell_nodes)
            # Accessible standings tables often use <th scope="row"> in EVERY
            # driver row. Treat only real <thead> rows (or an initial all-TH
            # row) as column headers; otherwise we'd throw away the standings.
            if in_thead or (not header and row_index == 0 and all_header_cells):
                if len(cells) >= len(header):
                    header = cells
                continue
            if not header and all_header_cells:
                header = cells
                continue
            body.append(cells)
        if body:
            tables.append((header, body))
    return tables


def _clean_markdown_cell(value: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = text.replace("**", "").replace("__", "").replace(chr(96), "")
    return " ".join(text.split()).strip()


def _parse_markdown_tables(markdown: str) -> list[tuple[list[str], list[list[str]]]]:
    lines = [line.strip() for line in str(markdown or "").splitlines()]
    tables: list[tuple[list[str], list[list[str]]]] = []
    index = 0

    def split_row(line: str) -> list[str]:
        raw = line.strip().strip("|")
        return [_clean_markdown_cell(cell) for cell in raw.split("|")]

    def separator(line: str) -> bool:
        if "|" not in line:
            return False
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell or "") for cell in cells)

    while index + 1 < len(lines):
        if "|" not in lines[index] or not separator(lines[index + 1]):
            index += 1
            continue
        header = split_row(lines[index])
        body: list[list[str]] = []
        index += 2
        while index < len(lines) and "|" in lines[index]:
            row = split_row(lines[index])
            if row and any(cell for cell in row):
                body.append(row)
            index += 1
        if header and body:
            tables.append((header, body))
    return tables


def _reader_url(url: str) -> str:
    parts = urlsplit(url)
    path = parts.path or "/"
    query = f"?{parts.query}" if parts.query else ""
    return f"https://r.jina.ai/http://{parts.netloc}{path}{query}"


def _reader_markdown(url: str) -> str:
    reader_url = _reader_url(url)
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/plain,text/markdown;q=0.9,*/*;q=0.5",
        "X-Return-Format": "markdown",
    }
    with httpx.Client(timeout=24.0, follow_redirects=True, headers=headers) as client:
        response = client.get(reader_url)
        response.raise_for_status()
    return response.text


def _reader_table_rows(url: str) -> list[tuple[list[str], list[list[str]]]]:
    tables = _parse_markdown_tables(_reader_markdown(url))
    if not tables:
        raise RuntimeError("rendered reader returned no standings tables")
    return tables


def _direct_html_table_rows(url: str) -> list[tuple[list[str], list[list[str]]]]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    }
    with httpx.Client(timeout=16.0, follow_redirects=True, headers=headers) as client:
        response = client.get(url)
        response.raise_for_status()
    tables = _parse_html_tables(response.text)
    if not tables:
        raise RuntimeError("official page returned no static standings tables")
    return tables


def _html_table_rows(url: str) -> list[tuple[list[str], list[list[str]]]]:
    direct_error: Exception | None = None
    try:
        return _direct_html_table_rows(url)
    except Exception as exc:
        direct_error = exc

    try:
        return _reader_table_rows(url)
    except Exception as reader_error:
        raise RuntimeError(
            f"official source unavailable ({direct_error}); rendered fallback failed ({reader_error})"
        ) from reader_error


def _linked_pdf_url(config: dict[str, Any], season: int) -> str:
    landing_url = _series_url(config, season)
    wanted = str(config.get("pdf_link_text") or "").strip().lower()
    fallback: str | None = None
    direct_error: Exception | None = None

    try:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }
        with httpx.Client(timeout=16.0, follow_redirects=True, headers=headers) as client:
            response = client.get(landing_url)
            response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for anchor in soup.find_all("a", href=True):
            href = str(anchor.get("href") or "").strip()
            if not href:
                continue
            text = " ".join(anchor.get_text(" ", strip=True).split()).lower()
            absolute = urljoin(landing_url, href)
            looks_pdf = ".pdf" in absolute.lower() or "pdf" in text
            if not looks_pdf:
                continue
            if fallback is None:
                fallback = absolute
            if wanted and wanted in text:
                return absolute
        if fallback:
            return fallback
    except Exception as exc:
        direct_error = exc

    try:
        reader_url = _reader_url(landing_url)
        with httpx.Client(
            timeout=24.0,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "X-Return-Format": "markdown"},
        ) as client:
            response = client.get(reader_url)
            response.raise_for_status()
        markdown = response.text
        for label, href in re.findall(r"\[([^\]]*)\]\(([^)]+)\)", markdown):
            text = " ".join(label.split()).lower()
            absolute = urljoin(landing_url, href.strip())
            looks_pdf = ".pdf" in absolute.lower() or "pdf" in text
            if not looks_pdf:
                continue
            if fallback is None:
                fallback = absolute
            if wanted and wanted in text:
                return absolute
        if fallback:
            return fallback
    except Exception as reader_error:
        raise RuntimeError(
            f"standings PDF link unavailable ({direct_error}); rendered fallback failed ({reader_error})"
        ) from reader_error

    raise RuntimeError("standings PDF link was not found on the official page")


def _pdf_text(url: str) -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/pdf,*/*;q=0.5",
    }
    with httpx.Client(timeout=24.0, follow_redirects=True, headers=headers) as client:
        response = client.get(url)
        response.raise_for_status()
    reader = PdfReader(io.BytesIO(response.content))
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    if not text.strip():
        raise RuntimeError("standings PDF contained no extractable text")
    return text


def _parse_asa_stars_pdf(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in text.splitlines():
        line = " ".join(raw.split())
        parts = line.split()
        if len(parts) < 8 or not parts[0].isdigit():
            continue
        # Position, car number, driver..., bonus, stage, race, total, difference.
        tail = parts[-5:]
        if not all(_num(value) is not None for value in tail[:4]):
            continue
        name = " ".join(parts[2:-5]).strip()
        if not name:
            continue
        points = _clean_points(tail[-2])
        if points is None:
            continue
        rows.append(
            {
                "position": int(parts[0]),
                "name": name.rstrip("*").strip(),
                "number": parts[1].strip() or None,
                "team": None,
                "manufacturer": None,
                "points": points,
                "behind": _clean_points(tail[-1]) if _num(tail[-1]) is not None else None,
                "wins": None,
                "starts": None,
            }
        )
    return rows


def _parse_smart_modified_pdf(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in text.splitlines():
        line = " ".join(raw.split())
        parts = line.split()
        if len(parts) < 5 or not parts[0].isdigit():
            continue
        position = int(parts[0])
        if position < 1 or position > 200:
            continue
        point_index: int | None = None
        for index in range(2, len(parts)):
            if _num(parts[index]) is not None:
                point_index = index
                break
        if point_index is None or point_index <= 2:
            continue
        name = " ".join(parts[2:point_index]).strip()
        points = _clean_points(parts[point_index])
        if not name or points is None:
            continue
        behind = None
        if point_index + 1 < len(parts):
            candidate = parts[point_index + 1].replace("−", "-")
            if candidate.startswith("-") and _num(candidate) is not None:
                behind = _clean_points(candidate)
        rows.append(
            {
                "position": position,
                "name": name,
                "number": parts[1].strip() or None,
                "team": None,
                "manufacturer": None,
                "points": points,
                "behind": behind,
                "wins": None,
                "starts": None,
            }
        )
    return rows


def _fetch_linked_pdf(config: dict[str, Any], season: int) -> dict[str, Any]:
    pdf_url = _linked_pdf_url(config, season)
    text = _pdf_text(pdf_url)
    fmt = str(config.get("pdf_format") or "").strip().lower()
    if fmt == "asa_stars":
        entries = _parse_asa_stars_pdf(text)
    elif fmt == "smart_modified":
        entries = _parse_smart_modified_pdf(text)
    else:
        raise RuntimeError(f"Unknown standings PDF format: {fmt}")
    if len(entries) < 3:
        raise RuntimeError(f"standings PDF rows could not be parsed ({len(entries)} rows)")
    entries.sort(key=lambda item: item["position"])
    return {
        "entries": entries,
        "source_name": str(config.get("source_name") or "Official standings"),
        "provider_url": pdf_url,
    }



def _imsa_official_pdf_text(pdf_url: str) -> str:
    """Read an IMSA-owned official points PDF, falling back to rendered text."""
    try:
        return _pdf_text(pdf_url)
    except Exception as direct_error:
        try:
            return _reader_markdown(pdf_url)
        except Exception as reader_error:
            raise RuntimeError(
                f"official IMSA points PDF unavailable ({direct_error}); "
                f"rendered PDF fallback failed ({reader_error})"
            ) from reader_error


def _parse_imsa_points_section(
    text: str,
    *,
    section_title: str,
) -> list[dict[str, Any]]:
    target = " ".join(str(section_title or "").casefold().split())
    if not target:
        raise RuntimeError("IMSA PDF section title is not configured")

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    active = False

    for raw in str(text or "").splitlines():
        line = " ".join(raw.replace("\u00a0", " ").split()).strip()
        if not line:
            continue
        normalized = line.casefold()

        if target in normalized:
            active = True
            continue

        if active and normalized.startswith("imsa "):
            is_identity_heading = any(
                token in normalized
                for token in (" drivers", " teams", " manufacturers", " bronze drivers")
            )
            if is_identity_heading and target not in normalized and rows:
                break

        if not active:
            continue

        # Official IMSA points sheets begin driver rows with:
        # <position> <driver name> <total points> ...
        match = re.match(r"^\s*(\d{1,3})\s+(.+?)\s+(\d{1,6})(?:\s|$)", line)
        if not match:
            continue

        position = int(match.group(1))
        name = " ".join(match.group(2).split()).strip()
        points = _clean_points(match.group(3))
        if not name or points is None:
            continue
        if name.casefold() in {"round", "driver", "pos", "points"}:
            continue

        key = _identity_key(name)
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "position": position,
                "name": name,
                "number": None,
                "team": None,
                "manufacturer": None,
                "points": points,
                "behind": None,
                "wins": None,
                "starts": None,
            }
        )

    if len(rows) < 3:
        raise RuntimeError(
            f"official IMSA points section could not be parsed ({len(rows)} rows): {section_title}"
        )
    rows.sort(key=lambda item: (item["position"], item["name"]))
    return rows


def _fetch_imsa_linked_pdf(config: dict[str, Any], season: int) -> dict[str, Any]:
    # IMSA can block Render from both HTML and PDF assets. Use the live
    # IMSA-owned document when reachable; otherwise retain the most recently
    # verified 2026 official standings snapshot embedded below.
    pdf_url = str(config.get("pdf_url") or "").strip()
    try:
        if not pdf_url:
            pdf_url = _linked_pdf_url(config, season)
        text = _imsa_official_pdf_text(pdf_url)
        entries = _parse_imsa_points_section(
            text,
            section_title=str(config.get("pdf_section_title") or ""),
        )
        provider_url = pdf_url
        source_name = str(config.get("source_name") or "IMSA official points")
    except Exception:
        fallback = IMSA_2026_STANDINGS_FALLBACK.get(str(config.get("key") or ""), [])
        if not fallback:
            raise
        entries = [
            {
                "position": position,
                "name": name,
                "number": None,
                "team": None,
                "manufacturer": None,
                "points": points,
                "behind": None,
                "wins": None,
                "starts": None,
            }
            for position, name, points in fallback
        ]
        provider_url = str(config.get("official_url") or "")
        source_name = str(config.get("source_name") or "IMSA official standings") + " · verified fallback snapshot"

    return {
        "entries": entries,
        "source_name": source_name,
        "provider_url": provider_url,
    }



def _page_tokens(url: str) -> list[str]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }
    direct_error: Exception | None = None
    try:
        with httpx.Client(timeout=16.0, follow_redirects=True, headers=headers) as client:
            response = client.get(url)
            response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        tokens = [" ".join(text.split()) for text in soup.stripped_strings if " ".join(text.split())]
        if tokens:
            return tokens
        direct_error = RuntimeError("official page returned no readable text")
    except Exception as exc:
        direct_error = exc

    try:
        reader_url = _reader_url(url)
        with httpx.Client(
            timeout=24.0,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "X-Return-Format": "markdown"},
        ) as client:
            response = client.get(reader_url)
            response.raise_for_status()
        tokens: list[str] = []
        for raw in response.text.splitlines():
            value = _clean_markdown_cell(raw.lstrip("#>*- ").strip())
            if value:
                tokens.append(value)
        if tokens:
            return tokens
        raise RuntimeError("rendered reader returned no readable text")
    except Exception as reader_error:
        raise RuntimeError(
            f"official text unavailable ({direct_error}); rendered fallback failed ({reader_error})"
        ) from reader_error


def _token_index(tokens: list[str], needle: str, start: int = 0) -> int | None:
    target = _norm_header(needle)
    for index in range(max(0, start), len(tokens)):
        if _norm_header(tokens[index]) == target:
            return index
    return None



def _split_collapsed_driver_names(value: str, expected_count: int) -> list[str]:
    words = [
        word for word in str(value or "").replace("\u00a0", " ").split()
        if word and word not in {"(R)", "(r)"}
    ]
    if not words or expected_count <= 0:
        return []
    suffixes = {"jr.", "jr", "sr.", "sr", "ii", "iii", "iv", "v"}
    names: list[str] = []
    index = 0
    while index < len(words) and len(names) < expected_count:
        remaining_names = expected_count - len(names)
        remaining_words = len(words) - index
        if remaining_words < remaining_names * 2:
            break
        take = 2
        if index + 2 < len(words) and words[index + 2].lower() in suffixes:
            take = 3
        name = " ".join(words[index:index + take]).strip()
        if name:
            names.append(name)
        index += take
    return names


def _fetch_column_sections(config: dict[str, Any], season: int) -> dict[str, Any]:
    url = _series_url(config, season)
    tokens = _page_tokens(url)
    title = str(config.get("column_title") or "Driver Standings")
    title_index = _token_index(tokens, title, 0) or 0
    pos_index = _token_index(tokens, "Pos.", title_index)
    if pos_index is None:
        pos_index = _token_index(tokens, "Pos", title_index)
    name_index = _token_index(tokens, "Driver", (pos_index or title_index) + 1)
    points_index = _token_index(tokens, "Points", (name_index or title_index) + 1)
    if pos_index is None or name_index is None or points_index is None:
        raise RuntimeError("standings columns were not found in official page text")

    stop_labels = (
        "Home town",
        "Hometown",
        "Starts",
        "Wins",
        "Top 5s",
        "Top 10s",
        "FQs",
        "Scroll Over >",
        "Entrant Standings",
    )
    stop_index = len(tokens)
    for label in stop_labels:
        found = _token_index(tokens, label, points_index + 1)
        if found is not None:
            stop_index = min(stop_index, found)

    positions: list[int] = []
    for token in tokens[pos_index + 1:name_index]:
        for piece in str(token or "").split():
            value = _parse_position(piece)
            if value is not None:
                positions.append(value)

    point_values: list[int | float | str | None] = []
    for token in tokens[points_index + 1:stop_index]:
        for piece in str(token or "").replace(",", "").split():
            if _num(piece) is not None:
                point_values.append(_clean_points(piece))

    raw_names = [
        name for name in tokens[name_index + 1:points_index]
        if name
        and _norm_header(name) not in {
            "image", "driver standings", "entrant standings", "home town",
            "hometown", "starts", "wins", "top 5s", "top 10s", "fqs",
        }
    ]
    if len(raw_names) == 1 and point_values:
        names = _split_collapsed_driver_names(raw_names[0], len(point_values))
    else:
        names = [
            " ".join(str(name).replace("(R)", "").split()).strip()
            for name in raw_names
            if _num(name) is None
        ]

    count = min(len(names), len(point_values))
    if positions:
        count = min(count, len(positions))
    if count < 3:
        raise RuntimeError(
            f"standings columns were incomplete (positions={len(positions)} names={len(names)} points={len(point_values)})"
        )

    normalized: list[dict[str, Any]] = []
    for index in range(count):
        normalized.append(
            {
                "position": positions[index] if positions else index + 1,
                "name": names[index],
                "number": None,
                "team": None,
                "manufacturer": None,
                "points": point_values[index],
                "behind": None,
                "wins": None,
                "starts": None,
            }
        )
    return {
        "entries": normalized,
        "source_name": str(config.get("source_name") or "Official standings"),
        "provider_url": url,
    }


def _series_url(config: dict[str, Any], season: int) -> str:
    template = str(config.get("official_url_template") or "").strip()
    if template:
        fe_season = max(1, season - 2014)
        return template.format(season=season, fe_season=fe_season)
    return str(config.get("official_url") or "").strip()


def _norm_header(value: str) -> str:
    return " ".join(
        "".join(ch if ch.isalnum() else " " for ch in str(value or "").lower()).split()
    )


def _header_index(header: list[str], aliases: tuple[str, ...] | list[str] | None) -> int | None:
    normalized = [_norm_header(item) for item in header]
    for alias in aliases or ():
        needle = _norm_header(alias)
        for index, value in enumerate(normalized):
            if value == needle or needle in value:
                return index
    return None


def _parse_position(value: Any) -> int | None:
    digits = ""
    for ch in str(value or "").strip():
        if ch.isdigit():
            digits += ch
        elif digits:
            break
    try:
        return int(digits) if digits else None
    except ValueError:
        return None


def _fetch_nascar_regional(config: dict[str, Any], season: int) -> dict[str, Any]:
    """Extract one championship table from NASCAR's shared Regional standings page."""
    url = _series_url(config, season)
    wanted = " ".join(str(config.get("regional_heading") or "").split()).casefold()
    if not wanted:
        raise RuntimeError("NASCAR Regional standings heading is not configured")

    markdown = _reader_markdown(url)
    lines = str(markdown or "").splitlines()
    heading_index: int | None = None
    for index, raw in enumerate(lines):
        match = re.match(r"^\s*#{1,6}\s+(.+?)\s*$", raw)
        if not match:
            continue
        label = _clean_markdown_cell(match.group(1)).casefold()
        if label == wanted:
            heading_index = index
            break
    if heading_index is None:
        raise RuntimeError(f"NASCAR Regional standings section not found: {config.get('regional_heading')}")

    # Each series heading is followed by its own standings table. Parse only
    # the first table after the requested heading so another series with the
    # same columns can never win the generic table-scoring heuristic.
    for index in range(heading_index + 1, len(lines) - 1):
        if "|" not in lines[index]:
            continue
        tables = _parse_markdown_tables("\n".join(lines[index:index + 80]))
        if not tables:
            continue
        return _normalize_official_tables(config, url, [tables[0]])

    raise RuntimeError(f"NASCAR Regional standings table not found: {config.get('regional_heading')}")


def _fetch_official_table(config: dict[str, Any], season: int) -> dict[str, Any]:
    urls = [_series_url(config, season)]
    for fallback in config.get("fallback_urls") or ():
        value = str(fallback or "").strip()
        if value:
            urls.append(value.format(season=season, fe_season=max(1, season - 2014)))
    for template in config.get("fallback_url_templates") or ():
        value = str(template or "").strip()
        if value:
            urls.append(value.format(season=season, fe_season=max(1, season - 2014)))

    key = str(config.get("key") or "")
    errors: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if not url or url in seen:
            continue
        seen.add(url)
        try:
            fetched = _fetch_official_table_url(config, url)

            # Some official standings pages intentionally render only a top-10
            # summary. Keep the public Race Center complete by replacing that
            # summary with the latest verified full championship table.
            if key == "lucas-oil-late-models" and season == 2026:
                current = fetched.get("entries") or []
                if len(current) < len(LUCAS_2026_FULL_STANDINGS):
                    entries = [
                        {
                            **row,
                            "team": None,
                            "manufacturer": None,
                            "behind": None,
                            "wins": None,
                            "starts": None,
                        }
                        for row in LUCAS_2026_FULL_STANDINGS
                    ]
                    return {
                        "entries": entries,
                        "source_name": "Lucas Oil Late Model Dirt Series standings · verified full-field snapshot",
                        "provider_url": url,
                    }
            return fetched
        except Exception as exc:
            errors.append(f"{url}: {exc}")

    if key == "cars-tour-lmsc" and season == 2026:
        entries = [
            {
                **row,
                "team": None,
                "manufacturer": None,
            }
            for row in CARS_2026_LMSC_FALLBACK
        ]
        return {
            "entries": entries,
            "source_name": "zMAX CARS Tour official LMSC standings · verified fallback snapshot",
            "provider_url": "https://www.carsracingtour.com/standings-lmsc/",
        }

    if key == "lucas-oil-late-models" and season == 2026:
        entries = [
            {
                **row,
                "team": None,
                "manufacturer": None,
                "behind": None,
                "wins": None,
                "starts": None,
            }
            for row in LUCAS_2026_FULL_STANDINGS
        ]
        return {
            "entries": entries,
            "source_name": "Lucas Oil Late Model Dirt Series standings · verified full-field snapshot",
            "provider_url": _series_url(config, season),
        }

    raise RuntimeError(" ; ".join(errors) or "official standings unavailable")


def _fetch_official_table_url(config: dict[str, Any], url: str) -> dict[str, Any]:
    direct_error: Exception | None = None
    try:
        tables = _direct_html_table_rows(url)
        return _normalize_official_tables(config, url, tables)
    except Exception as exc:
        direct_error = exc

    try:
        tables = _reader_table_rows(url)
        return _normalize_official_tables(config, url, tables)
    except Exception as reader_error:
        raise RuntimeError(
            f"direct table parse failed ({direct_error}); rendered table parse failed ({reader_error})"
        ) from reader_error


def _normalize_official_tables(
    config: dict[str, Any],
    url: str,
    tables: list[tuple[list[str], list[list[str]]]],
) -> dict[str, Any]:
    best: tuple[list[str], list[list[str]], dict[str, int | None]] | None = None
    best_score = -1
    for header, rows in tables:
        indexes = {
            "position": _header_index(header, config.get("position_headers") or ("pos", "position")),
            "name": _header_index(header, config.get("name_headers") or ("driver", "rider")),
            "points": _header_index(header, config.get("points_headers") or ("points", "pts", "total")),
            "behind": _header_index(header, config.get("behind_headers") or ("gap", "behind")),
            "wins": _header_index(header, config.get("wins_headers") or ("wins",)),
            "starts": _header_index(header, config.get("starts_headers") or ("starts", "races", "events")),
            "number": _header_index(header, config.get("number_headers") or NUMBER_HEADERS),
            "team": _header_index(header, config.get("team_headers") or TEAM_HEADERS),
            "manufacturer": _header_index(header, config.get("manufacturer_headers") or MANUFACTURER_HEADERS),
        }
        if indexes["name"] is None or indexes["points"] is None:
            continue
        score = sum(1 for value in indexes.values() if value is not None) + min(len(rows), 40) / 100
        if score > best_score:
            best = (header, rows, indexes)
            best_score = score
    if not best:
        raise RuntimeError("official standings table was not present in page HTML")
    _, rows, indexes = best
    normalized: list[dict[str, Any]] = []
    for fallback_position, row in enumerate(rows, start=1):
        name_index = indexes["name"]
        points_index = indexes["points"]
        if name_index is None or points_index is None:
            continue

        offset = 0
        if name_index < len(row):
            candidate_name = str(row[name_index] or "").strip()
            if candidate_name.startswith("[](") and candidate_name.endswith(")"):
                offset = 1

        def shifted(index: int | None) -> int | None:
            return None if index is None else index + offset

        actual_name_index = shifted(name_index)
        actual_points_index = shifted(points_index)
        if (
            actual_name_index is None
            or actual_points_index is None
            or actual_name_index >= len(row)
            or actual_points_index >= len(row)
        ):
            continue

        name = str(row[actual_name_index] or "").strip()
        name = re.sub(r"\s*[★☆]+\s*$", "", name).strip()
        points = _clean_points(row[actual_points_index])
        if not name or points is None:
            continue

        embedded_number: str | None = None
        if str(config.get("key") or "") == "motogp":
            match = re.match(r"^(\d{1,3})\s*(.+)$", name)
            if match:
                embedded_number = match.group(1)
                name = match.group(2).strip()

        # MyRacePass inserts the unlabeled profile cell AFTER the rank/car columns,
        # so Driver/Points need the offset but championship position does not.
        position_index = indexes["position"]
        position = (
            _parse_position(row[position_index])
            if position_index is not None and position_index < len(row)
            else fallback_position
        ) or fallback_position

        def field(index_name: str) -> Any:
            index = shifted(indexes.get(index_name))
            return row[index] if index is not None and index < len(row) else None

        normalized.append(
            {
                "position": position,
                "name": name,
                "number": (str(field("number") or "").strip() or embedded_number or None),
                "team": str(field("team") or "").strip() or None,
                "manufacturer": str(field("manufacturer") or "").strip() or None,
                "points": points,
                "behind": _clean_points(field("behind")),
                "wins": _clean_points(field("wins")),
                "starts": _clean_points(field("starts")),
            }
        )
    if not normalized:
        raise RuntimeError("official standings rows could not be parsed")
    normalized.sort(key=lambda item: item["position"])
    return {
        "entries": normalized,
        "source_name": str(config.get("source_name") or "Official standings"),
        "provider_url": url,
    }


def _fetch_imsa(config: dict[str, str], season: int) -> dict[str, Any]:
    tables = _html_table_rows(config["official_url"])
    chosen: tuple[list[str], list[list[str]]] | None = None
    for header, rows in tables:
        joined = " ".join(header).lower()
        if "driver" in joined and ("total" in joined or "points" in joined):
            chosen = (header, rows)
            break
    if not chosen:
        raise RuntimeError("IMSA standings table was not present in the page HTML")
    header, rows = chosen
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if len(row) < 3:
            continue
        try:
            position = int(str(row[0]).split()[0])
        except (ValueError, TypeError):
            continue
        name = row[1].strip()
        if not name:
            continue
        points = _clean_points(row[-1])
        normalized.append(
            {
                "position": position,
                "name": name,
                "number": None,
                "team": None,
                "manufacturer": None,
                "points": points,
                "behind": None,
                "wins": None,
                "starts": None,
            }
        )
    if not normalized:
        raise RuntimeError("IMSA standings rows could not be parsed")
    return {
        "entries": normalized,
        "source_name": f"{config.get('name') or 'IMSA'} official standings",
        "provider_url": config["official_url"],
    }


def _fetch_wec(config: dict[str, str], season: int) -> dict[str, Any]:
    tables = _html_table_rows(config["official_url"])
    chosen: tuple[list[str], list[list[str]]] | None = None
    for header, rows in tables:
        joined = " ".join(header).lower()
        if "driver" in joined and "total" in joined:
            chosen = (header, rows)
            break
    if not chosen:
        raise RuntimeError("WEC drivers standings table was not present in the page HTML")
    header, rows = chosen
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if len(row) < 4:
            continue
        try:
            position = int(str(row[0]).split()[0])
        except (ValueError, TypeError):
            continue
        name = row[3].strip() if len(row) >= 5 else row[1].strip()
        manufacturer = row[1].strip() if len(row) >= 5 else None
        number = row[2].strip() if len(row) >= 5 else None
        if not name:
            continue
        normalized.append(
            {
                "position": position,
                "name": name,
                "number": number,
                "team": None,
                "manufacturer": manufacturer,
                "points": _clean_points(row[-1]),
                "behind": None,
                "wins": None,
                "starts": None,
            }
        )
    if not normalized:
        raise RuntimeError("WEC standings rows could not be parsed")
    return {
        "entries": normalized,
        "source_name": "FIA WEC official standings",
        "provider_url": config["official_url"],
    }



def _identity_key(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def _identity_metadata_lookup(
    metadata: dict[str, dict[str, str | None]],
    name: Any,
) -> dict[str, str | None] | None:
    target = _identity_key(name)
    if not target:
        return None
    direct = metadata.get(target)
    if direct:
        return direct

    # Official directories sometimes wrap accessible labels with "Image" or
    # return surname-first display text. Accept only one unambiguous match.
    candidates = [
        values for key, values in metadata.items()
        if key and (key.endswith(target) or target.endswith(key))
    ]
    if len(candidates) == 1:
        return candidates[0]

    words = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]+", str(name or ""))
    if len(words) >= 2:
        reversed_key = _identity_key(" ".join(reversed(words)))
        direct = metadata.get(reversed_key)
        if direct:
            return direct
    return None


def _profile_metadata_cache_get(cache_key: str) -> tuple[dict[str, dict[str, str | None]], str | None] | None:
    now = utcnow()
    with _profile_metadata_lock:
        cached = _profile_metadata_cache.get(cache_key)
        if cached and (now - cached[0]).total_seconds() < 6 * 3600:
            return copy.deepcopy(cached[1]), cached[2]
    return None


def _profile_metadata_cache_set(
    cache_key: str,
    data: dict[str, dict[str, str | None]],
    source_url: str | None,
) -> None:
    with _profile_metadata_lock:
        _profile_metadata_cache[cache_key] = (utcnow(), copy.deepcopy(data), source_url)
        if len(_profile_metadata_cache) > 16:
            oldest = min(_profile_metadata_cache.items(), key=lambda item: item[1][0])[0]
            _profile_metadata_cache.pop(oldest, None)


def _nascar_profile_identity(
    url: str,
) -> tuple[str | None, str | None, str | None]:
    try:
        markdown = _reader_markdown(url)
    except Exception:
        return None, None, None

    number = None
    team = None
    manufacturer = None

    team_match = re.search(r"###\s*TEAM\s*\n+([^\n#]+)", markdown, flags=re.IGNORECASE)
    if team_match:
        team = " ".join(team_match.group(1).split()).strip() or None

    number_match = re.search(r"\bNo\.?\s*([A-Za-z0-9-]+)\b", markdown, flags=re.IGNORECASE)
    if number_match:
        number = number_match.group(1).strip() or None

    make_match = re.search(r"\b(Chevrolet|Ford|Toyota)\b", markdown, flags=re.IGNORECASE)
    if make_match:
        manufacturer = make_match.group(1).title()

    # NASCAR profile bios commonly say:
    # "drives the No. 5 Hendrick Motorsports Chevrolet full-time ..."
    if not team and number and manufacturer:
        pattern = (
            rf"\bNo\.?\s*{re.escape(number)}\s+"
            rf"(.{{2,90}}?)\s+{re.escape(manufacturer)}\b"
        )
        bio_team = re.search(pattern, markdown, flags=re.IGNORECASE)
        if bio_team:
            candidate = " ".join(bio_team.group(1).split()).strip(" ,.;:-")
            if candidate and len(candidate) <= 80:
                team = candidate

    return number, team, manufacturer


def _nascar_profile_url(driver_name: str) -> str:
    text = unicodedata.normalize("NFKD", str(driver_name or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    tokens = text.split()
    # NASCAR collapses common initial pairs such as A.J. into "aj".
    if len(tokens) >= 2 and len(tokens[0]) == 1 and len(tokens[1]) == 1:
        tokens = [tokens[0] + tokens[1], *tokens[2:]]
    slug = "-".join(tokens)
    return f"https://www.nascar.com/drivers/{slug}" if slug else ""


def _official_metadata_nascar_driver_directory(
    config: dict[str, Any],
    season: int,
    wanted_names: list[str] | None = None,
) -> tuple[dict[str, dict[str, str | None]], str | None]:
    url = str(config.get("metadata_url") or "").strip()
    if not url:
        return {}, None

    wanted_keys = {_identity_key(name) for name in (wanted_names or []) if _identity_key(name)}
    cache_scope = ",".join(sorted(wanted_keys)) if wanted_keys else "all"
    cache_key = f"nascar:{url}:{cache_scope}"
    cached = _profile_metadata_cache_get(cache_key)
    if cached:
        return cached

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }

    numbers: dict[str, str] = {}
    profile_links: dict[str, str] = {}

    soup = None
    try:
        with httpx.Client(timeout=18.0, follow_redirects=True, headers=headers) as client:
            response = client.get(url)
            response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception:
        # NASCAR frequently returns 403 to Render datacenter IPs. Use the
        # rendered copy of NASCAR's official page instead of abandoning identity.
        soup = None

    if soup is not None:
        for image in soup.find_all("img"):
            label = " ".join(str(image.get("alt") or "").split()).strip()
            match = re.search(
                r"^(.*?)\s+Badge Number\s+([A-Za-z0-9]+)$",
                label,
                flags=re.IGNORECASE,
            )
            if not match:
                continue
            key = _identity_key(match.group(1))
            if key:
                numbers[key] = match.group(2).strip()

        for anchor in soup.find_all("a", href=True):
            href = str(anchor.get("href") or "").strip()
            if "/drivers/" not in href.lower():
                continue
            key = _identity_key(" ".join(anchor.get_text(" ", strip=True).split()))
            if key:
                profile_links[key] = urljoin(url, href)

    directory_manufacturers: dict[str, str] = {}
    if not numbers or not profile_links:
        try:
            markdown = _reader_markdown(url)
            for raw_name, raw_number in re.findall(
                r"(?:Image:\s*|!\[)([^\]\n]+?)\s+Badge Number\s+([A-Za-z0-9]+)",
                markdown,
                flags=re.IGNORECASE,
            ):
                key = _identity_key(raw_name)
                if key:
                    numbers[key] = str(raw_number).strip()

            for label, href in re.findall(
                r"\[([^\]]+)\]\((https?://www\.nascar\.com/drivers/[^)]+|/drivers/[^)]+)\)",
                markdown,
                flags=re.IGNORECASE,
            ):
                key = _identity_key(" ".join(str(label or "").split()))
                if key:
                    clean_href = re.split(r"(?:\\s+[\"']|%20%22)", href.strip(), maxsplit=1)[0]
                    profile_links[key] = urljoin("https://www.nascar.com/", clean_href)

            # Pair each badge block with the following official Manufacturer Logo.
            badge_matches = list(re.finditer(
                r"(?:Image:\s*|!\[)([^\]\n]+?)\s+Badge Number\s+([A-Za-z0-9]+)",
                markdown,
                flags=re.IGNORECASE,
            ))
            for index, badge in enumerate(badge_matches):
                block_end = badge_matches[index + 1].start() if index + 1 < len(badge_matches) else min(len(markdown), badge.end() + 1200)
                block = markdown[badge.end():block_end]
                make = re.search(
                    r"https?://[^)\s]*(Chevrolet|Toyota|Ford)[^)\s]*\.(?:png|jpg|jpeg|webp|svg)",
                    block,
                    flags=re.IGNORECASE,
                )
                if make:
                    key = _identity_key(badge.group(1))
                    if key:
                        directory_manufacturers[key] = make.group(1).title()
        except Exception as exc:
            log.warning(
                "NASCAR official identity reader failed series=%s error=%s",
                config.get("key"),
                exc,
            )

    out: dict[str, dict[str, str | None]] = {
        key: {
            "number": number,
            "team": None,
            "manufacturer": directory_manufacturers.get(key),
        }
        for key, number in numbers.items()
    }

    # Do not let a temporary official-site block erase verified 2026 identity.
    verified_fallback = NASCAR_2026_IDENTITY_FALLBACK.get(str(config.get("key") or ""), {})
    for key, values in verified_fallback.items():
        if wanted_keys and key not in wanted_keys:
            continue
        current = out.setdefault(key, {"number": None, "team": None, "manufacturer": None})
        for field in ("number", "team", "manufacturer"):
            if not current.get(field) and values.get(field):
                current[field] = values[field]

    def fetch_one(item: tuple[str, str]) -> tuple[str, str | None, str | None, str | None]:
        key, profile_url = item
        number, team, manufacturer = _nascar_profile_identity(profile_url)
        return key, number, team, manufacturer

    links: list[tuple[str, str]] = []
    wanted_name_by_key = {
        _identity_key(name): str(name or "").strip()
        for name in (wanted_names or [])
        if _identity_key(name)
    }
    for key in out:
        if wanted_keys and not any(key == wanted or key.endswith(wanted) or wanted.endswith(key) for wanted in wanted_keys):
            continue
        href = profile_links.get(key)
        if not href:
            matches = [
                value for profile_key, value in profile_links.items()
                if profile_key.endswith(key) or key.endswith(profile_key)
            ]
            if len(matches) == 1:
                href = matches[0]
        if not href and key in wanted_name_by_key:
            href = _nascar_profile_url(wanted_name_by_key[key])
        if href:
            links.append((key, href))
    if links:
        with ThreadPoolExecutor(max_workers=min(2, len(links))) as pool:
            futures = [pool.submit(fetch_one, item) for item in links]
            for future in as_completed(futures):
                try:
                    key, number, team, manufacturer = future.result()
                except Exception:
                    continue
                if key in out:
                    if number and not out[key].get("number"):
                        out[key]["number"] = number
                    if team:
                        out[key]["team"] = team
                    if manufacturer:
                        out[key]["manufacturer"] = manufacturer

    source = url if out else None
    log.info(
        "NASCAR official identity: series=%s numbers=%s profiles=%s enriched=%s",
        config.get("key"),
        len(numbers),
        len(links),
        sum(1 for value in out.values() if value.get("team") or value.get("manufacturer")),
    )
    _profile_metadata_cache_set(cache_key, out, source)
    return out, source

def _official_metadata_arca_driver_directory(
    config: dict[str, Any],
    season: int,
) -> tuple[dict[str, dict[str, str | None]], str | None]:
    url = str(config.get("metadata_url") or "").strip()
    if not url:
        return {}, None
    try:
        tables = _html_table_rows(url)
    except Exception:
        return {}, None

    for header, rows in tables:
        name_index = _header_index(header, ("name", "driver"))
        number_index = _header_index(header, ("no", "number", "#"))
        make_index = _header_index(header, ("make", "manufacturer", "mfr"))
        if name_index is None or number_index is None or make_index is None:
            continue
        out: dict[str, dict[str, str | None]] = {}
        for row in rows:
            delta = max(0, len(row) - len(header))
            ni, noi, mi = name_index + delta, number_index + delta, make_index + delta
            if max(ni, noi, mi) >= len(row):
                continue
            name = " ".join(str(row[ni] or "").split()).strip()
            number = " ".join(str(row[noi] or "").split()).strip()
            make = " ".join(str(row[mi] or "").split()).strip()
            make = re.sub(r"\s+Image:\s*.*$", "", make, flags=re.IGNORECASE).strip()
            key = _identity_key(name)
            if not key:
                continue
            out[key] = {
                "number": number or None,
                "team": None,
                "manufacturer": make or None,
            }
        if out:
            return out, url
    return {}, None


_MOTOGP_COUNTRIES = tuple(sorted((
    "United States of America", "United Kingdom", "South Africa", "New Zealand",
    "Czechia", "Türkiye", "Argentina", "Australia", "Colombia", "France",
    "Indonesia", "Italy", "Japan", "Malaysia", "Netherlands", "Spain",
), key=len, reverse=True))


def _motogp_label_metadata(label: str) -> tuple[str, dict[str, str | None]] | None:
    text = " ".join(str(label or "").split()).strip()
    # Official rider cards start with initials+number, then repeat the race
    # number twice before the rider's full name.
    match = re.match(r"^[A-ZÀ-ÖØ-Ý]{1,4}\d{1,3}\s+(\d{1,3})\s+\1\s+(.+)$", text, re.IGNORECASE)
    if not match:
        return None
    number = match.group(1)
    rest = match.group(2).strip()
    lower_rest = rest.casefold()
    for country in _MOTOGP_COUNTRIES:
        token = f" {country.casefold()} "
        index = lower_rest.find(token)
        if index <= 0:
            continue
        name = rest[:index].strip()
        team = rest[index + len(token):].strip()
        key = _identity_key(name)
        if key and team:
            return key, {"number": number, "team": team, "manufacturer": None}
    return None


def _official_metadata_motogp_riders(
    config: dict[str, Any],
    season: int,
) -> tuple[dict[str, dict[str, str | None]], str | None]:
    url = str(config.get("metadata_url") or "").strip()
    if not url:
        return {}, None

    labels: list[str] = []
    try:
        with httpx.Client(
            timeout=18.0,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        ) as client:
            response = client.get(url)
            response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        labels.extend(
            " ".join(anchor.get_text(" ", strip=True).split())
            for anchor in soup.find_all("a")
            if anchor.get_text(" ", strip=True)
        )
    except Exception:
        pass

    if not any(_motogp_label_metadata(label) for label in labels):
        try:
            markdown = _reader_markdown(url)
            labels.extend(
                _clean_markdown_cell(label)
                for label, _href in re.findall(r"\[([^\]]+)\]\(([^)]+)\)", markdown)
            )
        except Exception:
            pass

    out: dict[str, dict[str, str | None]] = {}
    for label in labels:
        parsed = _motogp_label_metadata(label)
        if parsed:
            key, values = parsed
            out[key] = values
    return out, url if out else None


def _indycar_profile_identity(url: str) -> tuple[str | None, str | None, str | None]:
    try:
        markdown = _reader_markdown(url)
    except Exception:
        return None, None, None

    # Official profiles use prose such as:
    # "Driving the No. 10 Honda for Chip Ganassi Racing..."
    match = re.search(
        r"Driving\s+the\s+No\.\s*([A-Za-z0-9]+)\s+([A-Za-z]+)\s+for\s+([^\n.,]+(?:\s+Racing|\s+Motorsports|\s+Global|\s+ECR|\s+Team\s+Penske|\s+Arrow\s+McLaren|\s+Chip\s+Ganassi\s+Racing|\s+Rahal\s+Letterman\s+Lanigan\s+Racing))",
        markdown,
        flags=re.IGNORECASE,
    )
    if not match:
        return None, None, None
    number = match.group(1).strip()
    manufacturer = match.group(2).strip().title()
    team = " ".join(match.group(3).split()).strip()
    return number or None, team or None, manufacturer or None


def _official_metadata_indycar_driver_directory(
    config: dict[str, Any],
    season: int,
) -> tuple[dict[str, dict[str, str | None]], str | None]:
    url = str(config.get("metadata_url") or "").strip()
    if not url:
        return {}, None

    cache_key = f"indycar:{url}"
    cached = _profile_metadata_cache_get(cache_key)
    if cached:
        return cached

    try:
        markdown = _reader_markdown(url)
    except Exception:
        return {}, None

    links: dict[str, str] = {}
    for label, href in re.findall(r"\[([^\]]+)\]\((https?://www\.indycar\.com/Drivers/[^)]+|/Drivers/[^)]+)\)", markdown):
        clean = " ".join(str(label or "").split()).strip()
        clean = re.sub(r"^\d+\s+\d+\s+Wins\s+\d+\s+Poles\s+\d+\s+Points\s+", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\s+(?:United States|USA|Spain|Mexico|New Zealand|Sweden|Netherlands|Australia|France|Denmark|Norway|Brazil|Japan|England|United Kingdom|Cayman Islands)\s+Driver Details$", "", clean, flags=re.IGNORECASE)
        key = _identity_key(clean)
        if key:
            links[key] = urljoin("https://www.indycar.com/", href.strip())

    out: dict[str, dict[str, str | None]] = {}
    def fetch_one(item: tuple[str, str]) -> tuple[str, str | None, str | None, str | None]:
        key, profile_url = item
        number, team, manufacturer = _indycar_profile_identity(profile_url)
        return key, number, team, manufacturer

    with ThreadPoolExecutor(max_workers=min(8, max(1, len(links)))) as pool:
        futures = [pool.submit(fetch_one, item) for item in links.items()]
        for future in as_completed(futures):
            try:
                key, number, team, manufacturer = future.result()
            except Exception:
                continue
            if number or team or manufacturer:
                out[key] = {"number": number, "team": team, "manufacturer": manufacturer}

    source = url if out else None
    _profile_metadata_cache_set(cache_key, out, source)
    return out, source


def _official_metadata(
    config: dict[str, Any],
    season: int,
    wanted_names: list[str] | None = None,
) -> tuple[dict[str, dict[str, str | None]], str | None]:
    provider = str(config.get("metadata_provider") or "").strip()
    if provider == "nascar_driver_directory":
        return _official_metadata_nascar_driver_directory(config, season, wanted_names)
    if provider == "arca_driver_directory":
        return _official_metadata_arca_driver_directory(config, season)
    if provider == "motogp_riders":
        return _official_metadata_motogp_riders(config, season)
    if provider == "indycar_driver_directory":
        return _official_metadata_indycar_driver_directory(config, season)
    return _official_metadata_from_tables(config, season)


def _official_metadata_from_tables(
    config: dict[str, Any],
    season: int,
) -> tuple[dict[str, dict[str, str | None]], str | None]:
    """Read optional identity columns from the series' own official page only."""
    url = str(config.get("metadata_url") or _series_url(config, season))

    def choose(
        tables: list[tuple[list[str], list[list[str]]]],
    ) -> tuple[list[str], list[list[str]], dict[str, int | None]] | None:
        best: tuple[list[str], list[list[str]], dict[str, int | None]] | None = None
        best_score = -1
        for header, rows in tables:
            indexes = {
                "name": _header_index(header, config.get("name_headers") or ("driver", "rider")),
                "number": _header_index(header, config.get("number_headers") or NUMBER_HEADERS),
                "team": _header_index(header, config.get("team_headers") or TEAM_HEADERS),
                "manufacturer": _header_index(
                    header, config.get("manufacturer_headers") or MANUFACTURER_HEADERS
                ),
            }
            if indexes["name"] is None:
                continue
            identity_columns = sum(
                1 for key in ("number", "team", "manufacturer") if indexes[key] is not None
            )
            if identity_columns == 0:
                continue
            score = identity_columns * 10 + min(len(rows), 50) / 100
            if score > best_score:
                best = (header, rows, indexes)
                best_score = score
        return best

    best = None
    try:
        best = choose(_direct_html_table_rows(url))
    except Exception:
        pass

    # Only spend a rendered-reader request when static HTML did not expose a
    # usable official identity table. This prevents duplicate requests/rate hits.
    if best is None:
        try:
            best = choose(_reader_table_rows(url))
        except Exception:
            best = None
    if not best:
        return {}, None

    header, rows, indexes = best
    out: dict[str, dict[str, str | None]] = {}
    configured_offset = int(config.get("metadata_row_offset") or 0)
    for row in rows:
        offset = configured_offset
        name_index = indexes["name"]
        if name_index is None:
            continue

        # Some official tables insert an unlabeled profile/image cell into every
        # data row. Keep header-derived indexes aligned without guessing fields.
        candidate_index = name_index + offset
        if candidate_index < len(row):
            candidate_name = str(row[candidate_index] or "").strip()
            if candidate_name.startswith("[](") and candidate_name.endswith(")"):
                offset += 1

        actual_name_index = name_index + offset
        if actual_name_index >= len(row):
            continue
        name = str(row[actual_name_index] or "").strip()
        # F1 official results append the three-letter timing code to driver names.
        name = re.sub(r"\s+[A-Z]{3}$", "", name).strip()
        embedded_number: str | None = None
        if str(config.get("key") or "") == "motogp":
            match = re.match(r"^(\d{1,3})\s*(.+)$", name)
            if match:
                embedded_number = match.group(1)
                name = match.group(2).strip()
        key = _identity_key(name)
        if not key:
            continue

        def cell(field: str) -> str | None:
            index = indexes.get(field)
            if index is None:
                return None
            actual_index = index + offset
            if actual_index >= len(row):
                return None
            value = str(row[actual_index] or "").strip()
            return value or None

        out[key] = {
            "number": cell("number") or embedded_number,
            "team": cell("team"),
            "manufacturer": cell("manufacturer"),
        }
    return out, url if out else None


def _same_host(left: str, right: str) -> bool:
    try:
        left_host = (urlsplit(left).hostname or "").lower().removeprefix("www.")
        right_host = (urlsplit(right).hostname or "").lower().removeprefix("www.")
        return bool(left_host and right_host and left_host == right_host)
    except Exception:
        return False


def _http_image_url(value: str) -> bool:
    try:
        return urlsplit(str(value or "")).scheme.lower() in {"http", "https"}
    except Exception:
        return False


def _official_identity_source_allowed(config: dict[str, Any], candidate: str, official_url: str) -> bool:
    if candidate == official_url or _same_host(candidate, official_url):
        return True
    host = (urlsplit(candidate).hostname or "").lower()
    allowed_hosts = {str(value or "").lower() for value in (config.get("official_identity_hosts") or ())}
    return bool(host and host in allowed_hosts)


def _provider_identity_provenance(
    config: dict[str, Any],
    season: int,
    fetched: dict[str, Any],
) -> tuple[bool, str | None]:
    """Approve identity only when its source chain originates with the series itself."""
    provider = str(config.get("provider") or "")
    official_url = _series_url(config, season)
    provider_url = str(fetched.get("provider_url") or "").strip()

    # Linked PDFs are discovered by following a link on the configured official
    # standings page. The PDF may live on a CDN, but the official landing page
    # is the provenance anchor.
    if provider in {"linked_pdf", "imsa_linked_pdf"} and provider_url:
        return True, official_url

    # These adapters consume the configured official series URL directly.
    if provider in {"column_sections", "imsa", "wec"} and provider_url:
        if _official_identity_source_allowed(config, provider_url, official_url):
            return True, official_url

    # official_table may use third-party fallbacks (for example High Limit).
    # Only identity parsed from the configured official host is accepted.
    if provider == "official_table" and provider_url:
        if _official_identity_source_allowed(config, provider_url, official_url):
            return True, provider_url

    return False, None


def _enrich_official_identity(
    config: dict[str, Any],
    season: int,
    fetched: dict[str, Any],
) -> dict[str, Any]:
    entries = [dict(item) for item in fetched.get("entries") or []]
    if not entries:
        result = dict(fetched)
        result["metadata_source_url"] = None
        result["metadata_verified"] = False
        return result

    provider_verified, provider_source = _provider_identity_provenance(
        config, season, fetched
    )

    # Identity parsed from an unverified fallback must never leak into the hub.
    if not provider_verified:
        for item in entries:
            item["number"] = None
            item["team"] = None
            item["manufacturer"] = None

    metadata_source_url = provider_source
    metadata_verified = provider_verified and any(
        item.get("number") or item.get("team") or item.get("manufacturer")
        for item in entries
    )

    # Independently inspect the configured official series page for identity
    # columns. This can fill missing fields even when the standings provider is
    # a structured third-party feed used only for positions/points.
    wanted_names = [
        str(item.get("name") or "").strip()
        for item in entries[:5]
        if str(item.get("name") or "").strip()
    ]
    metadata, table_url = _official_metadata(config, season, wanted_names)
    if metadata:
        matched = False
        for item in entries:
            values = _identity_metadata_lookup(metadata, item.get("name"))
            if not values:
                continue
            for field in ("number", "team", "manufacturer"):
                if not item.get(field) and values.get(field):
                    item[field] = values[field]
                    matched = True
        if matched:
            metadata_source_url = table_url or _series_url(config, season)
            metadata_verified = True

    for item in entries:
        item.setdefault("number", None)
        item.setdefault("team", None)
        item.setdefault("manufacturer", None)

    result = dict(fetched)
    result["entries"] = entries
    result["metadata_source_url"] = metadata_source_url if metadata_verified else None
    result["metadata_verified"] = bool(metadata_verified)
    return result


def _logo_score(text: str, url: str, terms: tuple[str, ...]) -> int:
    hay = f"{text} {url}".lower()
    has_logo_signal = "logo" in hay
    matched_terms = [
        term.lower().strip()
        for term in terms
        if term and term.lower().strip() in hay
    ]
    # Official page alone is not enough. The asset itself must identify the
    # series and look explicitly like a logo, otherwise we leave it blank.
    if not has_logo_signal or not matched_terms:
        return -100
    score = 12 + min(6, len(matched_terms) * 2)
    if any(bad in hay for bad in (
        "sponsor", "partner", "advert", "ticket", "driver", "car-photo",
        "hero-", "instagram", "facebook", "youtube", "team-logo", "team_logo",
        "team logo", "teams logo", "75th", "anniversary",
    )):
        score -= 20
    return score


def _discover_official_logo(
    config: dict[str, Any],
    season: int,
) -> tuple[str | None, str | None]:
    """Return only imagery referenced by the configured official series page."""
    official_url = _series_url(config, season)
    configured_source = str(config.get("logo_source_url") or "").strip()
    source_url = configured_source or official_url
    if bool(config.get("logo_disabled")):
        return None, None
    explicit_logo = str(config.get("logo_url") or "").strip()
    explicit_source = configured_source or official_url
    if explicit_logo and _http_image_url(explicit_logo) and explicit_source:
        return explicit_logo, explicit_source

    terms = OFFICIAL_LOGO_TERMS.get(str(config.get("key") or ""), ())
    if not terms:
        return None, None

    candidates: list[tuple[int, str]] = []
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        with httpx.Client(timeout=14.0, follow_redirects=True, headers=headers) as client:
            response = client.get(source_url)
            response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Official sites increasingly expose their primary brand mark through
        # OpenGraph/Twitter metadata or <link rel=...> instead of a normal img.
        for meta in soup.find_all("meta"):
            prop = str(meta.get("property") or meta.get("name") or "").casefold()
            if prop not in {"og:image", "twitter:image", "twitter:image:src"}:
                continue
            raw_url = str(meta.get("content") or "").strip()
            if not raw_url:
                continue
            absolute = urljoin(source_url, raw_url)
            if not _http_image_url(absolute):
                continue
            score = _logo_score(prop + " logo", absolute, terms)
            if score >= 7:
                candidates.append((score, absolute))

        for link in soup.find_all("link"):
            rel = " ".join(str(x) for x in (link.get("rel") or [])).casefold()
            if not any(token in rel for token in ("icon", "logo")):
                continue
            raw_url = str(link.get("href") or "").strip()
            if not raw_url:
                continue
            absolute = urljoin(source_url, raw_url)
            if not _http_image_url(absolute):
                continue
            score = _logo_score(rel + " logo", absolute, terms)
            if score >= 7:
                candidates.append((score, absolute))

        for image in soup.find_all(["img", "source"]):
            raw_url = (
                image.get("src")
                or image.get("data-src")
                or image.get("data-lazy-src")
                or image.get("srcset")
                or image.get("data-srcset")
                or ""
            )
            if "," in str(raw_url):
                raw_url = str(raw_url).split(",", 1)[0].strip().split(" ", 1)[0]
            raw_url = str(raw_url).strip()
            if not raw_url:
                continue
            absolute = urljoin(source_url, raw_url)
            if not _http_image_url(absolute):
                continue
            label = " ".join(
                str(value or "")
                for value in (
                    image.get("alt"), image.get("title"), image.get("id"),
                    " ".join(image.get("class") or []),
                )
            )
            score = _logo_score(label, absolute, terms)
            if score >= 7:
                candidates.append((score, absolute))
    except Exception:
        pass

    if not candidates:
        try:
            reader_url = _reader_url(source_url)
            with httpx.Client(
                timeout=20.0,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT, "X-Return-Format": "markdown"},
            ) as client:
                response = client.get(reader_url)
                response.raise_for_status()
            for alt, raw_url in re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", response.text):
                absolute = urljoin(source_url, raw_url.strip())
                if not _http_image_url(absolute):
                    continue
                score = _logo_score(alt, absolute, terms)
                if score >= 7:
                    candidates.append((score, absolute))
        except Exception:
            pass

    if not candidates:
        return None, None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1], source_url



def _fetch_series(config: dict[str, Any], season: int) -> dict[str, Any]:
    provider = config["provider"]
    if provider == "espn":
        return _fetch_espn(config, season)
    if provider == "jolpica":
        return _fetch_f1(config, season)
    if provider == "imsa":
        return _fetch_imsa(config, season)
    if provider == "imsa_linked_pdf":
        return _fetch_imsa_linked_pdf(config, season)
    if provider == "wec":
        return _fetch_wec(config, season)
    if provider == "nascar_regional":
        return _fetch_nascar_regional(config, season)
    if provider == "official_table":
        return _fetch_official_table(config, season)
    if provider == "linked_pdf":
        return _fetch_linked_pdf(config, season)
    if provider == "column_sections":
        return _fetch_column_sections(config, season)
    raise RuntimeError(f"Unknown standings provider: {provider}")


def _decode_snapshot(row: RacingStandingSnapshot | None) -> dict[str, Any] | None:
    if not row:
        return None
    try:
        payload = json.loads(row.payload_json or "{}")
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload["snapshot_id"] = row.id
    payload["fetched_at"] = row.fetched_at.isoformat() if row.fetched_at else None
    return payload


def _latest_snapshot(series_key: str, season: int, *, excluding: str | None = None) -> RacingStandingSnapshot | None:
    with SessionLocal() as db:
        stmt = (
            select(RacingStandingSnapshot)
            .where(
                RacingStandingSnapshot.series_key == series_key,
                RacingStandingSnapshot.season == season,
            )
            .order_by(RacingStandingSnapshot.fetched_at.desc(), RacingStandingSnapshot.id.desc())
        )
        if excluding:
            stmt = stmt.where(RacingStandingSnapshot.fingerprint != excluding)
        return db.scalar(stmt.limit(1))


def _standings_entries_plausible(entries: list[dict[str, Any]]) -> bool:
    """Reject malformed scrape/PDF parses before they can become the public standings."""
    if not isinstance(entries, list) or len(entries) < 3:
        return False

    valid_names = 0
    numeric_points = 0
    positions: list[int] = []
    for item in entries:
        if not isinstance(item, dict):
            continue

        name = " ".join(str(item.get("name") or "").split()).strip()
        if (
            name
            and re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]", name)
            and "http://" not in name.casefold()
            and "https://" not in name.casefold()
            and "[](" not in name
        ):
            valid_names += 1

        try:
            pos = int(float(str(item.get("position"))))
            if pos > 0:
                positions.append(pos)
        except (TypeError, ValueError):
            pass

        if _num(item.get("points")) is not None:
            numeric_points += 1

    total = len(entries)
    if valid_names / total < 0.75:
        return False
    if len(positions) / total < 0.75:
        return False
    if numeric_points / total < 0.60:
        return False

    # This catches a common parser failure where car numbers become positions
    # (e.g. 71, 99, 76 in a 10-driver table).
    position_limit = max(30, total * 3)
    if sum(1 for value in positions if value <= position_limit) / max(1, len(positions)) < 0.80:
        return False

    return True


def _latest_valid_snapshot(
    series_key: str,
    season: int,
    *,
    excluding: str | None = None,
    limit: int = 12,
) -> RacingStandingSnapshot | None:
    with SessionLocal() as db:
        stmt = (
            select(RacingStandingSnapshot)
            .where(
                RacingStandingSnapshot.series_key == series_key,
                RacingStandingSnapshot.season == season,
            )
            .order_by(RacingStandingSnapshot.fetched_at.desc(), RacingStandingSnapshot.id.desc())
        )
        if excluding:
            stmt = stmt.where(RacingStandingSnapshot.fingerprint != excluding)
        rows = list(db.scalars(stmt.limit(limit)).all())

    for row in rows:
        payload = _decode_snapshot(row) or {}
        if _standings_entries_plausible(payload.get("entries") or []):
            return row
    return None


def _comparison_snapshot_plausible(previous_entries: list[dict[str, Any]]) -> bool:
    return _standings_entries_plausible(previous_entries)


def _looks_like_uniform_table_shift(
    entries: list[dict[str, Any]],
    previous_entries: list[dict[str, Any]],
) -> bool:
    """Reject movement when a scrape looks like the whole table shifted.

    A common parser/source artifact drops or inserts one row while leaving
    everybody else's points untouched. That makes many drivers appear to move
    exactly one position even though the championship itself did not change.
    """
    old_by_name = {
        _identity_key(item.get("name")): item
        for item in previous_entries
        if _identity_key(item.get("name"))
    }
    matched = 0
    shifts: dict[int, dict[str, int]] = {}

    for current in entries:
        key = _identity_key(current.get("name"))
        prior = old_by_name.get(key) if key else None
        if not prior:
            continue
        try:
            prior_pos = int(prior.get("position"))
            now_pos = int(current.get("position"))
        except (TypeError, ValueError):
            continue

        matched += 1
        shift = prior_pos - now_pos
        if shift == 0:
            continue

        bucket = shifts.setdefault(shift, {"count": 0, "zero_points": 0})
        bucket["count"] += 1
        prior_points = _num(prior.get("points"))
        current_points = _num(current.get("points"))
        if prior_points is not None and current_points is not None and current_points == prior_points:
            bucket["zero_points"] += 1

    if matched < 6 or not shifts:
        return False

    _, dominant = max(shifts.items(), key=lambda item: item[1]["count"])
    dominant_count = dominant["count"]
    zero_points = dominant["zero_points"]

    return (
        dominant_count >= 4
        and dominant_count * 10 >= matched * 6
        and zero_points * 10 >= dominant_count * 8
    )


def _movement(entries: list[dict[str, Any]], previous: dict[str, Any] | None) -> list[dict[str, Any]]:
    previous_entries = (previous or {}).get("entries", []) or []
    snapshot_valid = _comparison_snapshot_plausible(previous_entries)
    if snapshot_valid and _looks_like_uniform_table_shift(entries, previous_entries):
        snapshot_valid = False

    old_by_name: dict[str, dict[str, Any]] = {}
    old_by_number: dict[str, dict[str, Any]] = {}
    duplicate_numbers: set[str] = set()
    if snapshot_valid:
        for item in previous_entries:
            key = _identity_key(item.get("name"))
            if key:
                old_by_name[key] = item
            number = str(item.get("number") or "").strip().lstrip("#")
            if number:
                if number in old_by_number:
                    duplicate_numbers.add(number)
                else:
                    old_by_number[number] = item
        for number in duplicate_numbers:
            old_by_number.pop(number, None)

    out: list[dict[str, Any]] = []
    current_count = max(1, len(entries))
    for item in entries:
        current = dict(item)
        key = _identity_key(current.get("name"))
        prior_item = old_by_name.get(key) if key else None
        if prior_item is None:
            number = str(current.get("number") or "").strip().lstrip("#")
            if number:
                prior_item = old_by_number.get(number)

        try:
            prior_pos = int(prior_item.get("position")) if prior_item and prior_item.get("position") is not None else None
        except (TypeError, ValueError):
            prior_pos = None
        try:
            now_pos = int(current.get("position")) if current.get("position") is not None else None
        except (TypeError, ValueError):
            now_pos = None

        movement = (
            prior_pos - now_pos
            if prior_pos is not None and now_pos is not None
            else None
        )

        # Even after a valid-table check, fail closed on impossible jumps. A
        # driver can move a lot, but a delta larger than the tracked field is a
        # parser/layout change, not championship movement.
        if movement is not None and abs(movement) > current_count:
            movement = None
            prior_item = None

        comparison_ready = prior_item is not None
        current["comparison_ready"] = comparison_ready

        prior_points = _num(prior_item.get("points")) if prior_item else None
        current_points = _num(current.get("points"))
        if prior_points is not None and current_points is not None:
            delta = current_points - prior_points
            points_delta = int(delta) if float(delta).is_integer() else round(delta, 2)
        else:
            points_delta = None

        # "Verified movement" must have corroborating championship change.
        # A non-zero rank shift with identical/unknown points is too easy to
        # manufacture through row insertion/removal or source parser drift.
        movement_verified = bool(
            comparison_ready
            and movement not in (None, 0)
            and points_delta not in (None, 0)
        )
        current["movement"] = movement if movement_verified else None
        current["movement_verified"] = movement_verified
        current["points_delta"] = points_delta

        out.append(current)
    return out


def _persist(config: dict[str, Any], season: int, fetched: dict[str, Any]) -> dict[str, Any]:
    entries = fetched["entries"]
    if not _standings_entries_plausible(entries):
        raise RuntimeError("standings payload failed Pitmark data-quality validation")
    fingerprint = _fingerprint(entries)
    previous_row = _latest_valid_snapshot(config["key"], season, excluding=fingerprint)
    previous = _decode_snapshot(previous_row)
    normalized = {
        "series_key": config["key"],
        "series_name": config["name"],
        "short_name": config["short_name"],
        "group": config["group"],
        "season": season,
        "official_url": _series_url(config, season),
        "source_name": fetched.get("source_name") or "Standings source",
        "provider_url": fetched.get("provider_url"),
        "metadata_source_url": fetched.get("metadata_source_url"),
        "metadata_verified": bool(fetched.get("metadata_verified")),
        "series_logo_url": fetched.get("series_logo_url"),
        "series_logo_source_url": fetched.get("series_logo_source_url"),
        "entries": entries,
        "fingerprint": fingerprint,
    }
    with SessionLocal() as db:
        existing = db.scalar(
            select(RacingStandingSnapshot).where(
                RacingStandingSnapshot.series_key == config["key"],
                RacingStandingSnapshot.season == season,
                RacingStandingSnapshot.fingerprint == fingerprint,
            )
        )
        if not existing:
            row = RacingStandingSnapshot(
                series_key=config["key"],
                season=season,
                source_name=normalized["source_name"],
                source_url=_series_url(config, season),
                fingerprint=fingerprint,
                payload_json=json.dumps(normalized, ensure_ascii=False, default=str),
                fetched_at=utcnow(),
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            fetched_at = row.fetched_at
            snapshot_id = row.id
        else:
            # Metadata/logo provenance can improve without the points changing.
            # A successful poll also refreshes freshness even when the championship
            # fingerprint itself has not changed.
            existing.source_name = normalized["source_name"]
            existing.source_url = _series_url(config, season)
            existing.payload_json = json.dumps(normalized, ensure_ascii=False, default=str)
            existing.fetched_at = utcnow()
            db.commit()
            db.refresh(existing)
            fetched_at = existing.fetched_at
            snapshot_id = existing.id
    normalized["entries"] = _movement(entries, previous)
    normalized["fetched_at"] = fetched_at.isoformat() if fetched_at else utcnow().isoformat()
    normalized["snapshot_id"] = snapshot_id
    normalized["status"] = "live"
    normalized["stale"] = False
    normalized["error"] = None
    return normalized


def _fallback(config: dict[str, Any], season: int, error: Exception) -> dict[str, Any]:
    latest = _latest_valid_snapshot(config["key"], season)
    cached = _decode_snapshot(latest)
    if cached:
        cached.update(
            {
                "series_key": config["key"],
                "series_name": config["name"],
                "short_name": config["short_name"],
                "group": config["group"],
                "official_url": _series_url(config, season),
                "season": season,
                "status": "stale",
                "stale": True,
                "error": str(error),
            }
        )
        previous_row = _latest_valid_snapshot(
            config["key"],
            season,
            excluding=cached.get("fingerprint"),
        )
        previous = _decode_snapshot(previous_row)
        cached["entries"] = _movement(cached.get("entries") or [], previous)
        if config.get("metadata_provider") or config.get("metadata_url"):
            try:
                metadata, metadata_url = _official_metadata(config, season)
            except Exception:
                metadata, metadata_url = {}, None
            matched = False
            if metadata:
                for entry in cached["entries"]:
                    values = _identity_metadata_lookup(metadata, entry.get("name"))
                    if not values:
                        continue
                    for field in ("number", "team", "manufacturer"):
                        if values.get(field):
                            entry[field] = values[field]
                            matched = True
            if matched:
                cached["metadata_verified"] = True
                cached["metadata_source_url"] = metadata_url
        return _sanitize_identity_payload(cached)
    return {
        "series_key": config["key"],
        "series_name": config["name"],
        "short_name": config["short_name"],
        "group": config["group"],
        "official_url": _series_url(config, season),
        "season": season,
        "source_name": None,
        "provider_url": None,
        "metadata_source_url": None,
        "metadata_verified": False,
        "entries": [],
        "fetched_at": None,
        "snapshot_id": None,
        "status": "unavailable",
        "stale": True,
        "error": str(error),
    }



def _sanitize_identity_payload(item: dict[str, Any]) -> dict[str, Any]:
    """Fail closed: identity fields are visible only with verified official provenance."""
    result = copy.deepcopy(item)
    verified = bool(result.get("metadata_verified"))
    result["metadata_verified"] = verified
    if not verified:
        result["metadata_source_url"] = None
        for entry in result.get("entries") or []:
            entry["number"] = None
            entry["team"] = None
            entry["manufacturer"] = None
    return result


def _load_one(config: dict[str, Any], season: int) -> dict[str, Any]:
    try:
        fetched = _fetch_series(config, season)
        if not _standings_entries_plausible(fetched.get("entries") or []):
            raise RuntimeError("remote standings failed Pitmark data-quality validation")
        fetched = _enrich_official_identity(config, season, fetched)
        logo_url, logo_source_url = _discover_official_logo(config, season)
        fetched["series_logo_url"] = logo_url
        fetched["series_logo_source_url"] = logo_source_url
        return _persist(config, season, fetched)
    except Exception as exc:
        log.warning("Standings fetch failed series=%s error=%s", config["key"], exc)
        return _fallback(config, season, exc)


def get_standings_hub(*, force: bool = False, season: int | None = None) -> dict[str, Any]:
    season = int(season or utcnow().year)
    now = utcnow()
    with _cache_lock:
        cached_at = _cache.get("at")
        cached_value = _cache.get("value")
        if (
            not force
            and cached_at
            and cached_value
            and cached_value.get("season") == season
            and (now - cached_at).total_seconds() < CACHE_SECONDS
        ):
            return copy.deepcopy(cached_value)

    results: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=min(8, len(SERIES))) as pool:
        future_map = {pool.submit(_load_one, config, season): config for config in SERIES}
        for future in as_completed(future_map):
            config = future_map[future]
            try:
                results[config["key"]] = future.result()
            except Exception as exc:
                results[config["key"]] = _fallback(config, season, exc)

    ordered = [_sanitize_identity_payload(results[config["key"]]) for config in SERIES]
    live = sum(1 for item in ordered if item.get("status") == "live")
    stale = sum(1 for item in ordered if item.get("status") == "stale")
    unavailable = sum(1 for item in ordered if item.get("status") == "unavailable")
    synced_times = [item.get("fetched_at") for item in ordered if item.get("fetched_at")]
    value = {
        "season": season,
        "generated_at": now.isoformat(),
        "series": ordered,
        "summary": {
            "series_total": len(ordered),
            "live": live,
            "stale": stale,
            "unavailable": unavailable,
            "last_snapshot_at": max(synced_times) if synced_times else None,
        },
    }
    with _cache_lock:
        _cache["at"] = now
        _cache["value"] = copy.deepcopy(value)
    return value


def _hydrate_saved_identity(
    series_key: str,
    season: int,
    entries: list[dict[str, Any]],
    cached_rows: dict[str, RaceCenterDriverIdentityCache] | None = None,
) -> list[dict[str, Any]]:
    """Merge persisted/verified identity into saved standings rows without remote I/O."""
    if not entries:
        return []

    cached: dict[str, RaceCenterDriverIdentityCache] = cached_rows if cached_rows is not None else {}
    if cached_rows is None:
        try:
            with SessionLocal() as db:
                rows = list(db.scalars(
                    select(RaceCenterDriverIdentityCache).where(
                        RaceCenterDriverIdentityCache.series_key == series_key,
                        RaceCenterDriverIdentityCache.season == season,
                        RaceCenterDriverIdentityCache.resolver_version == DRIVER_IDENTITY_RESOLVER_VERSION,
                    )
                ).all())
                cached = {row.driver_key: row for row in rows}
        except Exception as exc:
            log.info("Saved identity hydration cache read failed series=%s error=%s", series_key, exc)

    verified_fallback = (
        NASCAR_2026_IDENTITY_FALLBACK.get(series_key, {})
        if season == 2026
        else {}
    )

    hydrated: list[dict[str, Any]] = []
    for raw in entries:
        item = dict(raw)
        key = _identity_key(item.get("name"))
        cache_row = cached.get(key)
        fallback = verified_fallback.get(key, {})

        if not item.get("number"):
            item["number"] = (
                (cache_row.number if cache_row else None)
                or fallback.get("number")
                or None
            )
        if not item.get("team"):
            item["team"] = (
                (cache_row.team if cache_row else None)
                or fallback.get("team")
                or None
            )
        if not item.get("manufacturer"):
            item["manufacturer"] = (
                (cache_row.manufacturer if cache_row else None)
                or fallback.get("manufacturer")
                or None
            )

        if cache_row and cache_row.photo_use_allowed and cache_row.photo_url:
            item["photo_url"] = cache_row.photo_url
            item["photo_use_allowed"] = True
            item["photo_source_url"] = cache_row.photo_source_url or None
            item["photo_license"] = cache_row.photo_license or None
            item["photo_attribution"] = cache_row.photo_attribution or None

        hydrated.append(item)
    return hydrated


def get_standings_snapshot_hub(*, season: int | None = None) -> dict[str, Any]:
    """Return the latest saved standings immediately without touching remote sources."""
    season = int(season or utcnow().year)
    now = utcnow()

    # The background sync already builds the exact public-safe standings shape.
    # Reuse that in-memory snapshot instead of re-reading the same championship
    # rows from Postgres on every page load.
    with _cache_lock:
        live_cached_at = _cache.get("at")
        live_cached = _cache.get("value")
        if (
            live_cached_at
            and live_cached
            and int(live_cached.get("season") or 0) == season
            and (now - live_cached_at).total_seconds() <= 6 * 3600
        ):
            return copy.deepcopy(live_cached)

        cached_at = _snapshot_cache.get("at")
        cached_value = _snapshot_cache.get("value")
        if (
            cached_at
            and cached_value
            and int(_snapshot_cache.get("season") or 0) == season
            and (now - cached_at).total_seconds() < SNAPSHOT_CACHE_SECONDS
        ):
            return copy.deepcopy(cached_value)

    # Cold-start fallback: read the whole current-season snapshot set and
    # persisted identity cache in two queries, then resolve each series in memory.
    # The old path performed multiple Postgres round-trips per championship.
    snapshots_by_series: dict[str, list[RacingStandingSnapshot]] = {}
    identity_by_series: dict[str, dict[str, RaceCenterDriverIdentityCache]] = {}
    bulk_loaded = False
    try:
        with SessionLocal() as db:
            snapshot_rows = list(db.scalars(
                select(RacingStandingSnapshot)
                .where(RacingStandingSnapshot.season == season)
                .order_by(
                    RacingStandingSnapshot.series_key.asc(),
                    RacingStandingSnapshot.fetched_at.desc(),
                    RacingStandingSnapshot.id.desc(),
                )
            ).all())
            identity_rows = list(db.scalars(
                select(RaceCenterDriverIdentityCache).where(
                    RaceCenterDriverIdentityCache.season == season,
                    RaceCenterDriverIdentityCache.resolver_version == DRIVER_IDENTITY_RESOLVER_VERSION,
                )
            ).all())
        for row in snapshot_rows:
            snapshots_by_series.setdefault(str(row.series_key), []).append(row)
        for row in identity_rows:
            identity_by_series.setdefault(str(row.series_key), {})[str(row.driver_key)] = row
        bulk_loaded = True
    except Exception as exc:
        log.info("Bulk saved standings read failed; using per-series fallback error=%s", exc)

    ordered: list[dict[str, Any]] = []
    for config in SERIES:
        latest_row: RacingStandingSnapshot | None = None
        previous_row: RacingStandingSnapshot | None = None
        snapshot: dict[str, Any] | None = None
        previous: dict[str, Any] | None = None

        if bulk_loaded:
            for row in snapshots_by_series.get(config["key"], []):
                candidate = _decode_snapshot(row)
                if not candidate or not _standings_entries_plausible(candidate.get("entries") or []):
                    continue
                if latest_row is None:
                    latest_row = row
                    snapshot = candidate
                    continue
                if row.fingerprint != latest_row.fingerprint:
                    previous_row = row
                    previous = candidate
                    break
        else:
            latest_row = _latest_valid_snapshot(config["key"], season)
            snapshot = _decode_snapshot(latest_row)
            if snapshot:
                previous_row = _latest_valid_snapshot(
                    config["key"],
                    season,
                    excluding=snapshot.get("fingerprint"),
                )
                previous = _decode_snapshot(previous_row)

        if snapshot:
            entries = snapshot.get("entries") or []
            fetched_at = latest_row.fetched_at if latest_row else None
            age_seconds = (now - fetched_at).total_seconds() if fetched_at else None
            fresh = age_seconds is not None and age_seconds <= 6 * 3600
            snapshot.update(
                {
                    "series_key": config["key"],
                    "series_name": config["name"],
                    "short_name": config["short_name"],
                    "group": config["group"],
                    "season": season,
                    "official_url": _series_url(config, season),
                    "source_name": snapshot.get("source_name") or latest_row.source_name,
                    "metadata_verified": bool(snapshot.get("metadata_verified")),
                    "entries": _hydrate_saved_identity(
                        config["key"],
                        season,
                        _movement(entries, previous),
                        cached_rows=identity_by_series.get(config["key"], {}) if bulk_loaded else None,
                    ),
                    "status": "live" if fresh else "stale",
                    "stale": not fresh,
                    "error": None,
                }
            )
            if bool(config.get("logo_disabled")):
                snapshot["series_logo_url"] = None
                snapshot["series_logo_source_url"] = None
            elif config.get("logo_url"):
                snapshot["series_logo_url"] = str(config.get("logo_url") or "").strip() or None
                snapshot["series_logo_source_url"] = str(
                    config.get("logo_source_url") or _series_url(config, season)
                ).strip() or None
            ordered.append(_sanitize_identity_payload(snapshot))
            continue
        ordered.append(
            {
                "series_key": config["key"],
                "series_name": config["name"],
                "short_name": config["short_name"],
                "group": config["group"],
                "official_url": _series_url(config, season),
                "season": season,
                "source_name": None,
                "provider_url": None,
                "metadata_source_url": None,
                "metadata_verified": False,
                "entries": [],
                "fetched_at": None,
                "snapshot_id": None,
                "status": "unavailable",
                "stale": True,
                "error": "No saved Pitmark snapshot yet.",
                "series_logo_url": (
                    None
                    if bool(config.get("logo_disabled"))
                    else (str(config.get("logo_url") or "").strip() or None)
                ),
                "series_logo_source_url": (
                    None
                    if bool(config.get("logo_disabled")) or not str(config.get("logo_url") or "").strip()
                    else str(config.get("logo_source_url") or _series_url(config, season)).strip() or None
                ),
            }
        )

    live = sum(1 for item in ordered if item.get("status") == "live")
    stale = sum(1 for item in ordered if item.get("status") == "stale")
    unavailable = sum(1 for item in ordered if item.get("status") == "unavailable")
    synced_times = [item.get("fetched_at") for item in ordered if item.get("fetched_at")]
    value = {
        "season": season,
        "generated_at": now.isoformat(),
        "series": ordered,
        "summary": {
            "series_total": len(ordered),
            "live": live,
            "stale": stale,
            "unavailable": unavailable,
            "last_snapshot_at": max(synced_times) if synced_times else None,
        },
    }
    with _cache_lock:
        _snapshot_cache["at"] = now
        _snapshot_cache["season"] = season
        _snapshot_cache["value"] = copy.deepcopy(value)
    return value



def get_series_logo_info(series_key: str, *, season: int | None = None) -> dict[str, str] | None:
    season = int(season or utcnow().year)
    config = next((item for item in SERIES if item["key"] == series_key), None)
    if not config:
        return None
    if bool(config.get("logo_disabled")):
        return None

    official_url = _series_url(config, season)
    configured_logo_source = str(config.get("logo_source_url") or "").strip()
    explicit_logo = str(config.get("logo_url") or "").strip()
    if explicit_logo and _http_image_url(explicit_logo):
        return {
            "url": explicit_logo,
            "source_url": configured_logo_source or official_url,
        }

    snapshot = _decode_snapshot(_latest_snapshot(series_key, season))
    if not snapshot:
        return None
    logo_url = str(snapshot.get("series_logo_url") or "").strip()
    source_url = str(snapshot.get("series_logo_source_url") or "").strip()
    if not logo_url or not source_url or not _http_image_url(logo_url):
        return None

    # Auto-discovered imagery is trusted only when its source page is one of
    # the exact official provenance anchors configured for that series.
    allowed_sources = {official_url}
    if configured_logo_source:
        allowed_sources.add(configured_logo_source)
    if source_url not in allowed_sources:
        return None
    return {"url": logo_url, "source_url": source_url}



def get_series_roster(
    series_key: str,
    entries: list[dict[str, Any]] | None = None,
    *,
    season: int | None = None,
) -> list[dict[str, Any]]:
    season = int(season or utcnow().year)
    roster: list[dict[str, Any]] = []
    seen: set[str] = set()

    for raw in entries or []:
        name = str(raw.get("name") or "").strip()
        key = _identity_key(name)
        if not name or not key or key in seen:
            continue
        seen.add(key)
        roster.append(
            {
                "name": name,
                "number": raw.get("number"),
                "team": raw.get("team"),
                "manufacturer": raw.get("manufacturer"),
                "in_standings": True,
            }
        )

    supplements: list[dict[str, Any]] = []
    if series_key == "high-limit-sprint" and season == 2026:
        supplements = HIGH_LIMIT_2026_ROSTER_SUPPLEMENT

    for raw in supplements:
        name = str(raw.get("name") or "").strip()
        key = _identity_key(name)
        if not name or not key or key in seen:
            continue
        seen.add(key)
        roster.append(
            {
                "name": name,
                "number": raw.get("number"),
                "team": raw.get("team"),
                "manufacturer": raw.get("manufacturer"),
                "in_standings": False,
            }
        )
    return roster



WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
WIKIPEDIA_BASE_URL = "https://en.wikipedia.org/wiki/"
WIKIMEDIA_COMMONS_API_URL = "https://commons.wikimedia.org/w/api.php"

_WIKIPEDIA_TEAM_LABELS: dict[str, tuple[str, ...]] = {
    "nascar-cup": ("cup car team", "cup team"),
    "nascar-oreilly": (
        "busch car team",
        "xfinity car team",
        "nationwide car team",
        "oreilly car team",
        "o'reilly car team",
    ),
    "nascar-truck": ("truck car team", "truck team"),
    "arca-menards": ("arca car team", "arca team"),
}
_WIKIPEDIA_NUMBER_LABELS = (
    "car number",
    "car no.",
    "car no",
    "number",
    "bike number",
    "racing number",
)
_WIKIPEDIA_GENERIC_TEAM_LABELS = (
    "current team",
    "team",
    "constructor",
    "current series team",
)
_WIKIPEDIA_MANUFACTURER_LABELS = (
    "manufacturer",
    "make",
    "marque",
    "constructor",
)
_WIKIPEDIA_MANUFACTURERS = (
    "Chevrolet",
    "Ford",
    "Toyota",
    "Honda",
    "Acura",
    "Cadillac",
    "Porsche",
    "Ferrari",
    "BMW",
    "Mercedes",
    "Mercedes-Benz",
    "McLaren",
    "Aston Martin",
    "Lamborghini",
    "Lexus",
    "Nissan",
    "Subaru",
    "Mazda",
    "Dodge",
    "KTM",
    "Ducati",
    "Yamaha",
    "Aprilia",
)


def _wikipedia_infobox(soup: BeautifulSoup) -> dict[str, str]:
    values: dict[str, str] = {}
    table = soup.find("table", class_=lambda value: value and "infobox" in str(value))
    if not table:
        return values
    for row in table.find_all("tr"):
        heading = row.find("th")
        cell = row.find("td")
        if not heading or not cell:
            continue
        key = _norm_header(" ".join(heading.get_text(" ", strip=True).split()))
        value = " ".join(cell.get_text(" ", strip=True).split()).strip()
        if key and value:
            values[key] = value
    return values


def _wikipedia_pick_page(driver_name: str) -> tuple[str, str] | None:
    clean_name = " ".join(str(driver_name or "").split()).strip()
    target = _identity_key(clean_name)
    if not target:
        return None

    # Most racing biographies use the driver's exact name as the article title.
    # Resolve that first so enrichment does not depend on Wikipedia search ranking.
    exact_params = {
        "action": "query",
        "titles": clean_name,
        "redirects": "1",
        "format": "json",
        "formatversion": "2",
    }
    with httpx.Client(
        timeout=12.0,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    ) as client:
        exact_response = client.get(WIKIPEDIA_API_URL, params=exact_params)
        exact_response.raise_for_status()
        exact_pages = ((exact_response.json() or {}).get("query") or {}).get("pages") or []
    if exact_pages and not exact_pages[0].get("missing"):
        exact_title = " ".join(str(exact_pages[0].get("title") or clean_name).split()).strip()
        if exact_title and "disambiguation" not in exact_title.lower():
            return exact_title, WIKIPEDIA_BASE_URL + quote(exact_title.replace(" ", "_"))

    params = {
        "action": "query",
        "list": "search",
        "srsearch": f'"{clean_name}" racing driver',
        "srnamespace": "0",
        "srlimit": "8",
        "format": "json",
        "utf8": "1",
    }
    with httpx.Client(
        timeout=12.0,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    ) as client:
        response = client.get(WIKIPEDIA_API_URL, params=params)
        response.raise_for_status()
        items = ((response.json() or {}).get("query") or {}).get("search") or []

    best: tuple[int, str] | None = None
    for item in items:
        title = " ".join(str(item.get("title") or "").split()).strip()
        if not title:
            continue
        title_key = _identity_key(title)
        score = 0
        if title_key == target:
            score += 100
        elif target and (target in title_key or title_key in target):
            score += 45
        snippet = BeautifulSoup(str(item.get("snippet") or ""), "html.parser").get_text(" ", strip=True).lower()
        if "racing driver" in snippet or "race car driver" in snippet or "stock car" in snippet:
            score += 20
        if "disambiguation" in snippet or "disambiguation" in title.lower():
            score -= 80
        if best is None or score > best[0]:
            best = (score, title)

    if not best or best[0] < 20:
        return None
    title = best[1]
    return title, WIKIPEDIA_BASE_URL + quote(title.replace(" ", "_"))


def _wikipedia_team_and_number(
    infobox: dict[str, str],
    series_key: str,
) -> tuple[str | None, str | None]:
    labels = (
        *_WIKIPEDIA_TEAM_LABELS.get(series_key, ()),
        *_WIKIPEDIA_GENERIC_TEAM_LABELS,
    )
    number: str | None = None
    team: str | None = None

    for label in labels:
        value = infobox.get(_norm_header(label))
        if not value:
            continue
        match = re.search(
            r"(?:No\.?\s*)?([A-Za-z0-9-]+)\s*\(([^()]+)\)",
            value,
            flags=re.IGNORECASE,
        )
        if match:
            number = match.group(1).strip() or None
            team = " ".join(match.group(2).split()).strip() or None
            break
        team = value.strip() or None
        if team:
            break

    for label in _WIKIPEDIA_NUMBER_LABELS:
        value = infobox.get(_norm_header(label))
        if value and not number:
            match = re.search(r"(?:No\.?\s*)?([A-Za-z0-9-]+)", value, flags=re.IGNORECASE)
            if match:
                number = match.group(1).strip() or None
                break

    return team, number


def _wikipedia_manufacturer(
    infobox: dict[str, str],
    summary: str,
    number: str | None,
) -> str | None:
    for label in _WIKIPEDIA_MANUFACTURER_LABELS:
        value = infobox.get(_norm_header(label))
        if not value:
            continue
        for manufacturer in _WIKIPEDIA_MANUFACTURERS:
            if manufacturer.lower() in value.lower():
                return manufacturer

    search_text = summary or ""
    if number:
        number_match = re.search(
            rf"\bNo\.?\s*{re.escape(str(number))}\b(.{{0,120}})",
            search_text,
            flags=re.IGNORECASE,
        )
        if number_match:
            search_text = number_match.group(0)

    for manufacturer in _WIKIPEDIA_MANUFACTURERS:
        if re.search(rf"\b{re.escape(manufacturer)}\b", search_text, flags=re.IGNORECASE):
            return manufacturer
    return None


_WIKIPEDIA_SERIES_HINTS: dict[str, tuple[str, ...]] = {
    "nascar-cup": ("nascar cup series",),
    "nascar-oreilly": (
        "nascar o'reilly auto parts series",
        "nascar xfinity series",
        "nascar nationwide series",
        "nascar busch series",
    ),
    "nascar-truck": ("nascar craftsman truck series", "nascar truck series"),
    "arca-menards": ("arca menards series",),
    "indycar": ("indycar series", "ntt indycar series"),
    "f1": ("formula one", "formula 1"),
    "formula-e": ("formula e",),
}


def _wikipedia_series_clause(summary: str, series_key: str) -> str:
    text = " ".join(str(summary or "").split()).strip()
    if not text:
        return ""
    lower = text.lower()
    for hint in _WIKIPEDIA_SERIES_HINTS.get(series_key, ()):
        index = lower.find(hint)
        if index >= 0:
            # Keep the requested series clause intact. Splitting on periods
            # breaks stock-car biographies at abbreviations such as "No. 5".
            return text[max(0, index - 20): index + 280]
    return text


def _wikipedia_identity_from_summary(
    summary: str,
    series_key: str,
) -> tuple[str | None, str | None, str | None]:
    clause = _wikipedia_series_clause(summary, series_key)
    if not clause:
        return None, None, None

    number: str | None = None
    team: str | None = None
    manufacturer: str | None = None

    number_match = re.search(r"\bNo\.?\s*([A-Za-z0-9-]+)\b", clause, flags=re.IGNORECASE)
    if number_match:
        number = number_match.group(1).strip() or None

    for make in sorted(_WIKIPEDIA_MANUFACTURERS, key=len, reverse=True):
        if re.search(rf"\b{re.escape(make)}\b", clause, flags=re.IGNORECASE):
            manufacturer = make
            break

    # Stock-car biographies commonly use:
    # "driving the No. 5 Chevrolet ... for Hendrick Motorsports".
    team_match = re.search(
        r"\bfor\s+([A-Z][A-Za-z0-9&'’.\- ]{2,80}?)(?=\s+and\s+(?:part-time|full-time)|,\s+(?:and\s+)?(?:part-time|full-time)|,\s+(?:and|while)|[.;]|$)",
        clause,
    )
    if team_match:
        candidate = " ".join(team_match.group(1).split()).strip(" ,.;")
        if candidate and not candidate.lower().startswith(("the ", "a ")):
            team = candidate

    return team, number, manufacturer


def _wikipedia_page_payload(title: str) -> dict[str, Any]:
    params = {
        "action": "query",
        "prop": "extracts|pageimages",
        "titles": title,
        "redirects": "1",
        "exintro": "1",
        "explaintext": "1",
        "piprop": "name|thumbnail|original",
        "pithumbsize": "720",
        "format": "json",
        "formatversion": "2",
    }
    with httpx.Client(
        timeout=14.0,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    ) as client:
        response = client.get(WIKIPEDIA_API_URL, params=params)
        response.raise_for_status()
        pages = ((response.json() or {}).get("query") or {}).get("pages") or []
    return pages[0] if pages else {}


def _wikipedia_parsed_html(title: str) -> BeautifulSoup | None:
    params = {
        "action": "parse",
        "page": title,
        "prop": "text",
        "format": "json",
        "formatversion": "2",
    }
    with httpx.Client(
        timeout=14.0,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    ) as client:
        response = client.get(WIKIPEDIA_API_URL, params=params)
        response.raise_for_status()
        html = ((response.json() or {}).get("parse") or {}).get("text") or ""
    return BeautifulSoup(html, "html.parser") if html else None


def _wikipedia_licensed_photo(page: dict[str, Any]) -> dict[str, Any]:
    filename = " ".join(str(page.get("pageimage") or "").split()).strip()
    if not filename:
        return {}

    params = {
        "action": "query",
        "prop": "imageinfo",
        "titles": f"File:{filename}",
        "iiprop": "url|extmetadata",
        "iiurlwidth": "720",
        "format": "json",
        "formatversion": "2",
    }
    with httpx.Client(
        timeout=14.0,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    ) as client:
        response = client.get(WIKIPEDIA_API_URL, params=params)
        response.raise_for_status()
        pages = ((response.json() or {}).get("query") or {}).get("pages") or []

    info = ((pages[0] if pages else {}).get("imageinfo") or [{}])[0]
    metadata = info.get("extmetadata") or {}
    license_name = str((metadata.get("LicenseShortName") or {}).get("value") or "").strip()
    normalized_license = license_name.lower()
    allowed = (
        normalized_license.startswith("cc by")
        or normalized_license.startswith("cc0")
        or normalized_license.startswith("public domain")
        or normalized_license.startswith("pd-")
    )
    if not allowed:
        return {
            "photo_use_allowed": False,
            "photo_license": license_name or None,
            "photo_source_url": info.get("descriptionurl"),
        }

    artist_html = str((metadata.get("Artist") or {}).get("value") or "")
    credit_html = str((metadata.get("Credit") or {}).get("value") or "")
    artist = " ".join(BeautifulSoup(artist_html, "html.parser").get_text(" ", strip=True).split())
    credit = " ".join(BeautifulSoup(credit_html, "html.parser").get_text(" ", strip=True).split())
    attribution = artist or credit

    thumbnail = page.get("thumbnail") or {}
    original = page.get("original") or {}
    photo_url = (
        info.get("thumburl")
        or thumbnail.get("source")
        or info.get("url")
        or original.get("source")
    )
    return {
        "photo_use_allowed": bool(photo_url),
        "photo_url": photo_url,
        "photo_source_url": info.get("descriptionurl"),
        "photo_license": license_name or None,
        "photo_attribution": attribution[:320] if attribution else None,
    }


def _licensed_image_payload(info: dict[str, Any], *, fallback_url: str | None = None) -> dict[str, Any]:
    metadata = info.get("extmetadata") or {}
    license_name = str((metadata.get("LicenseShortName") or {}).get("value") or "").strip()
    normalized_license = license_name.lower()
    allowed = (
        normalized_license.startswith("cc by")
        or normalized_license.startswith("cc0")
        or normalized_license.startswith("public domain")
        or normalized_license.startswith("pd-")
    )
    if not allowed:
        return {}

    artist_html = str((metadata.get("Artist") or {}).get("value") or "")
    credit_html = str((metadata.get("Credit") or {}).get("value") or "")
    artist = " ".join(BeautifulSoup(artist_html, "html.parser").get_text(" ", strip=True).split())
    credit = " ".join(BeautifulSoup(credit_html, "html.parser").get_text(" ", strip=True).split())
    attribution = artist or credit
    photo_url = info.get("thumburl") or info.get("url")
    source_url = info.get("descriptionurl") or fallback_url
    if not photo_url:
        return {}
    return {
        "photo_use_allowed": True,
        "photo_url": photo_url,
        "photo_source_url": source_url,
        "photo_license": license_name or None,
        "photo_attribution": attribution[:320] if attribution else None,
    }


def _commons_driver_photo(driver_name: str) -> dict[str, Any]:
    clean_name = " ".join(str(driver_name or "").split()).strip()
    target = _identity_key(clean_name)
    if not target:
        return {}

    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": f'"{clean_name}"',
        "gsrnamespace": "6",
        "gsrlimit": "16",
        "prop": "imageinfo|categories",
        "iiprop": "url|extmetadata",
        "iiurlwidth": "720",
        "cllimit": "50",
        "format": "json",
        "formatversion": "2",
    }
    with httpx.Client(
        timeout=16.0,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    ) as client:
        response = client.get(WIKIMEDIA_COMMONS_API_URL, params=params)
        response.raise_for_status()
        pages = ((response.json() or {}).get("query") or {}).get("pages") or []

    best: tuple[int, dict[str, Any]] | None = None
    racing_terms = (
        "racing driver", "race car driver", "nascar", "indycar", "formula",
        "motorsport", "sprint car", "late model", "modified", "stock car",
        "midget", "arca", "imsa", "motogp", "driver",
    )
    reject_terms = ("logo", "signature", "helmet", "car only", "vehicle only")

    for page in pages:
        title = " ".join(str(page.get("title") or "").split()).strip()
        info = ((page.get("imageinfo") or [{}])[0]) if isinstance(page, dict) else {}
        metadata = info.get("extmetadata") or {}
        description_html = str((metadata.get("ImageDescription") or {}).get("value") or "")
        description = " ".join(BeautifulSoup(description_html, "html.parser").get_text(" ", strip=True).split())
        object_name = str((metadata.get("ObjectName") or {}).get("value") or "")
        categories = " ".join(
            str(item.get("title") or "")
            for item in (page.get("categories") or [])
            if isinstance(item, dict)
        )
        haystack = " ".join((title, description, object_name, categories)).casefold()
        if any(term in haystack for term in reject_terms):
            continue

        title_key = _identity_key(re.sub(r"^File:", "", title, flags=re.IGNORECASE))
        description_key = _identity_key(description)
        score = 0
        if target and target in title_key:
            score += 80
        if target and target in description_key:
            score += 60
        if any(term in haystack for term in racing_terms):
            score += 25
        if "portrait" in haystack or "headshot" in haystack:
            score += 12
        if "driver" in haystack:
            score += 8
        if score < 70:
            continue

        licensed = _licensed_image_payload(info)
        if not licensed:
            continue
        if best is None or score > best[0]:
            best = (score, licensed)

    return best[1] if best else {}


def _wikipedia_driver_identity(
    config: dict[str, Any],
    driver_name: str,
    season: int,
) -> dict[str, Any]:
    cache_key = f"wikipedia-driver-v2:{config.get('key')}:{_identity_key(driver_name)}"
    cached = _profile_metadata_cache_get(cache_key)
    if cached:
        data, source_url = cached
        values = _identity_metadata_lookup(data, driver_name) or {}
        return {**values, "source_url": source_url, "source_name": "Wikipedia"}

    picked = _wikipedia_pick_page(driver_name)
    if not picked:
        log.info("Wikipedia driver page not found series=%s driver=%s", config.get("key"), driver_name)
        try:
            commons_photo = _commons_driver_photo(driver_name)
        except Exception as exc:
            log.info("Wikimedia Commons photo lookup failed driver=%s error=%s", driver_name, exc)
            commons_photo = {}
        if commons_photo:
            result = {**commons_photo}
            data = {_identity_key(driver_name): result}
            _profile_metadata_cache_set(
                cache_key,
                data,
                str(commons_photo.get("photo_source_url") or "") or None,
            )
            return {
                **result,
                "source_url": commons_photo.get("photo_source_url"),
                "source_name": "Wikimedia Commons",
            }
        return {}
    title, page_url = picked

    page = _wikipedia_page_payload(title)
    summary = " ".join(str(page.get("extract") or "").split()).strip()

    infobox: dict[str, str] = {}
    try:
        soup = _wikipedia_parsed_html(title)
        if soup:
            infobox = _wikipedia_infobox(soup)
    except Exception as exc:
        log.info("Wikipedia infobox parse failed driver=%s error=%s", driver_name, exc)

    team, number = _wikipedia_team_and_number(infobox, str(config.get("key") or ""))
    manufacturer = _wikipedia_manufacturer(infobox, summary, number)

    summary_team, summary_number, summary_manufacturer = _wikipedia_identity_from_summary(
        summary,
        str(config.get("key") or ""),
    )
    team = team or summary_team
    number = number or summary_number
    manufacturer = manufacturer or summary_manufacturer

    photo: dict[str, Any] = {}
    try:
        photo = _wikipedia_licensed_photo(page)
    except Exception as exc:
        log.info("Wikipedia photo license lookup failed driver=%s error=%s", driver_name, exc)

    if not photo.get("photo_use_allowed"):
        try:
            commons_photo = _commons_driver_photo(driver_name)
            if commons_photo:
                photo = commons_photo
        except Exception as exc:
            log.info("Wikimedia Commons fallback failed driver=%s error=%s", driver_name, exc)

    result = {
        "number": number,
        "team": team,
        "manufacturer": manufacturer,
        "bio": summary[:900] if summary else None,
        "wikipedia_title": title,
        **photo,
    }

    if not any(
        result.get(field)
        for field in ("number", "team", "manufacturer", "bio", "photo_url")
    ):
        return {}

    data = {_identity_key(driver_name): result}
    _profile_metadata_cache_set(cache_key, data, page_url)
    return {**result, "source_url": page_url, "source_name": "Wikipedia"}


def _driver_identity_cache_get(
    series_key: str,
    driver_name: str,
    season: int,
) -> dict[str, Any] | None:
    key = _identity_key(driver_name)
    if not key:
        return None
    with SessionLocal() as db:
        row = db.scalar(
            select(RaceCenterDriverIdentityCache).where(
                RaceCenterDriverIdentityCache.series_key == series_key,
                RaceCenterDriverIdentityCache.season == season,
                RaceCenterDriverIdentityCache.driver_key == key,
                RaceCenterDriverIdentityCache.resolver_version == DRIVER_IDENTITY_RESOLVER_VERSION,
            )
        )
        if row is None:
            return None
        updated = row.updated_at
        if updated is None:
            return None
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        age_seconds = (utcnow() - updated).total_seconds()
        complete = bool(row.number and row.team and row.manufacturer)
        ttl = 24 * 3600 if complete else 4 * 3600
        if age_seconds > ttl:
            return None
        try:
            field_sources = json.loads(row.field_sources_json or "{}")
        except Exception:
            field_sources = {}
        return {
            "verified": row.source_kind == "official" and complete,
            "resolved": bool(row.number or row.team or row.manufacturer),
            "series_key": row.series_key,
            "driver_name": row.driver_name,
            "number": row.number or None,
            "team": row.team or None,
            "manufacturer": row.manufacturer or None,
            "bio": row.bio or None,
            "photo_url": row.photo_url or None,
            "photo_use_allowed": bool(row.photo_use_allowed and row.photo_url),
            "photo_source_url": row.photo_source_url or None,
            "photo_license": row.photo_license or None,
            "photo_attribution": row.photo_attribution or None,
            "field_sources": field_sources,
            "source_kind": row.source_kind or "unresolved",
            "source_name": row.source_name or None,
            "source_url": row.source_url or None,
            "official_source_url": row.official_source_url or None,
            "secondary_source_url": row.secondary_source_url or None,
            "identity_quality": "complete" if complete else "partial",
            "cached": True,
            "updated_at": updated.isoformat(),
        }


def _driver_identity_cache_set(payload: dict[str, Any], season: int) -> None:
    series_key = str(payload.get("series_key") or "").strip()
    driver_name = str(payload.get("driver_name") or "").strip()
    key = _identity_key(driver_name)
    if not series_key or not key:
        return
    with SessionLocal() as db:
        row = db.scalar(
            select(RaceCenterDriverIdentityCache).where(
                RaceCenterDriverIdentityCache.series_key == series_key,
                RaceCenterDriverIdentityCache.season == season,
                RaceCenterDriverIdentityCache.driver_key == key,
            )
        )
        if row is None:
            row = RaceCenterDriverIdentityCache(
                series_key=series_key,
                season=season,
                driver_key=key,
                driver_name=driver_name,
            )
            db.add(row)
        row.driver_name = driver_name
        row.number = str(payload.get("number") or "")[:40]
        row.team = str(payload.get("team") or "")[:220]
        row.manufacturer = str(payload.get("manufacturer") or "")[:120]
        row.bio = str(payload.get("bio") or "")[:4000]
        row.photo_url = str(payload.get("photo_url") or "")[:4000]
        row.photo_use_allowed = bool(payload.get("photo_use_allowed") and row.photo_url)
        row.photo_source_url = str(payload.get("photo_source_url") or "")[:4000]
        row.photo_license = str(payload.get("photo_license") or "")[:160]
        row.photo_attribution = str(payload.get("photo_attribution") or "")[:1000]
        row.source_kind = str(payload.get("source_kind") or "")[:40]
        row.source_name = str(payload.get("source_name") or "")[:160]
        row.source_url = str(payload.get("source_url") or "")[:4000]
        row.official_source_url = str(payload.get("official_source_url") or "")[:4000]
        row.secondary_source_url = str(payload.get("secondary_source_url") or "")[:4000]
        row.field_sources_json = json.dumps(payload.get("field_sources") or {}, sort_keys=True)
        row.resolver_version = DRIVER_IDENTITY_RESOLVER_VERSION
        row.updated_at = utcnow()
        db.commit()


def get_driver_identity(
    series_key: str,
    driver_name: str,
    *,
    season: int | None = None,
) -> dict[str, Any]:
    """Resolve official identity fields lazily for one driver profile.

    Standings snapshots stay lightweight. A driver page can ask for the richer
    identity only when somebody actually opens that profile.
    """
    season = int(season or utcnow().year)
    config = next((item for item in SERIES if item["key"] == series_key), None)
    clean_name = " ".join(str(driver_name or "").split()).strip()
    if not clean_name:
        return {
            "verified": False,
            "resolved": False,
            "series_key": series_key,
            "driver_name": clean_name,
            "number": None,
            "team": None,
            "manufacturer": None,
            "source_url": None,
            "identity_quality": "unavailable",
        }

    if not config:
        cached_identity = _driver_identity_cache_get(series_key, clean_name, season)
        if cached_identity:
            return cached_identity
        try:
            photo = _commons_driver_photo(clean_name)
        except Exception as exc:
            log.info("Generic Commons driver photo failed driver=%s error=%s", clean_name, exc)
            photo = {}
        result = {
            "verified": False,
            "resolved": bool(photo.get("photo_url")),
            "series_key": series_key,
            "driver_name": clean_name,
            "number": None,
            "team": None,
            "manufacturer": None,
            "bio": None,
            "photo_url": photo.get("photo_url"),
            "photo_use_allowed": bool(photo.get("photo_use_allowed")),
            "photo_source_url": photo.get("photo_source_url"),
            "photo_license": photo.get("photo_license"),
            "photo_attribution": photo.get("photo_attribution"),
            "field_sources": {},
            "source_kind": "wikimedia_commons" if photo.get("photo_url") else "unresolved",
            "source_name": "Wikimedia Commons" if photo.get("photo_url") else None,
            "source_url": photo.get("photo_source_url"),
            "official_source_url": None,
            "secondary_source_url": photo.get("photo_source_url"),
            "identity_quality": "photo" if photo.get("photo_url") else "unavailable",
            "cached": False,
            "updated_at": utcnow().isoformat(),
        }
        try:
            _driver_identity_cache_set(result, season)
        except Exception as exc:
            log.info("Generic driver photo cache write failed driver=%s error=%s", clean_name, exc)
        return result

    cached_identity = _driver_identity_cache_get(series_key, clean_name, season)
    if cached_identity:
        return cached_identity

    try:
        metadata, source_url = _official_metadata(config, season, [clean_name])
    except Exception as exc:
        log.warning(
            "Driver identity lookup failed series=%s driver=%s error=%s",
            series_key,
            clean_name,
            exc,
        )
        metadata, source_url = {}, None

    official_values = _identity_metadata_lookup(metadata, clean_name) or {}
    official_source_url = source_url or (
        str(config.get("metadata_url") or "").strip() or _series_url(config, season)
    )
    number = official_values.get("number")
    team = official_values.get("team")
    manufacturer = official_values.get("manufacturer")

    # Hard completeness floor for current NASCAR profiles. These values are
    # verified from NASCAR-owned 2026 driver pages and exist specifically so a
    # temporary directory/profile-reader failure can never reduce a known driver
    # to only a car number.
    if season == 2026:
        verified_fallback = (
            NASCAR_2026_IDENTITY_FALLBACK
            .get(series_key, {})
            .get(_identity_key(clean_name), {})
        )
        number = number or verified_fallback.get("number")
        team = team or verified_fallback.get("team")
        manufacturer = manufacturer or verified_fallback.get("manufacturer")

    field_sources = {
        "number": "official" if number else None,
        "team": "official" if team else None,
        "manufacturer": "official" if manufacturer else None,
    }

    secondary: dict[str, Any] = {}
    try:
        # Every driver profile gets a trusted secondary lookup when the official
        # source is incomplete. This is deliberately profile-on-demand so Race
        # Center does not hammer Wikipedia for an entire field every refresh.
        # Secondary enrichment also supplies biography and reusable photo
        # metadata, so run it even when official identity is already complete.
        secondary = _wikipedia_driver_identity(config, clean_name, season)
    except Exception as exc:
        log.info(
            "Wikipedia driver enrichment failed series=%s driver=%s error=%s",
            series_key,
            clean_name,
            exc,
        )

    if not number and secondary.get("number"):
        number = secondary.get("number")
        field_sources["number"] = "wikipedia"
    if not team and secondary.get("team"):
        team = secondary.get("team")
        field_sources["team"] = "wikipedia"
    if not manufacturer and secondary.get("manufacturer"):
        manufacturer = secondary.get("manufacturer")
        field_sources["manufacturer"] = "wikipedia"

    resolved = any((number, team, manufacturer))
    fully_official = bool(
        number
        and team
        and manufacturer
        and all(
            field_sources.get(field) == "official"
            for field in ("number", "team", "manufacturer")
        )
    )
    source_kind = (
        "official"
        if fully_official
        else "mixed"
        if any(value == "official" for value in field_sources.values())
        and any(value == "wikipedia" for value in field_sources.values())
        else "wikipedia"
        if any(value == "wikipedia" for value in field_sources.values())
        else "official_partial"
        if any(value == "official" for value in field_sources.values())
        else "unresolved"
    )
    log.info(
        "Driver identity resolved series=%s driver=%s number=%s team=%s manufacturer=%s source=%s photo=%s",
        series_key,
        clean_name,
        number,
        team,
        manufacturer,
        source_kind,
        bool(secondary.get("photo_url")),
    )
    result = {
        "verified": fully_official,
        "resolved": bool(resolved),
        "series_key": series_key,
        "driver_name": clean_name,
        "number": number,
        "team": team,
        "manufacturer": manufacturer,
        "bio": secondary.get("bio"),
        "photo_url": secondary.get("photo_url"),
        "photo_use_allowed": bool(secondary.get("photo_use_allowed")),
        "photo_source_url": secondary.get("photo_source_url"),
        "photo_license": secondary.get("photo_license"),
        "photo_attribution": secondary.get("photo_attribution"),
        "field_sources": field_sources,
        "source_kind": source_kind,
        "source_name": (
            "Official + Wikipedia"
            if source_kind == "mixed"
            else "Wikipedia"
            if source_kind == "wikipedia"
            else "Official racing source"
            if source_kind == "official"
            else "Official racing source (partial)"
            if source_kind == "official_partial"
            else None
        ),
        "source_url": official_source_url if source_kind == "official" else secondary.get("source_url"),
        "official_source_url": official_source_url,
        "secondary_source_url": secondary.get("source_url"),
        "identity_quality": (
            "complete"
            if number and team and manufacturer
            else "partial"
            if resolved
            else "unavailable"
        ),
        "cached": False,
        "updated_at": utcnow().isoformat(),
    }
    try:
        _driver_identity_cache_set(result, season)
    except Exception as exc:
        log.info(
            "Driver identity cache write failed series=%s driver=%s error=%s",
            series_key,
            clean_name,
            exc,
        )
    return result


def warm_driver_identity_cache(
    *,
    limit: int = 48,
    season: int | None = None,
) -> dict[str, Any]:
    """Proactively enrich current standings drivers so photos are ready before scroll."""
    season = int(season or utcnow().year)
    hub = get_standings_snapshot_hub(season=season)
    candidates: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for series in hub.get("series") or []:
        series_key = str(series.get("series_key") or "").strip()
        if not series_key:
            continue
        for entry in series.get("entries") or []:
            name = " ".join(str(entry.get("name") or "").split()).strip()
            key = _identity_key(name)
            if not name or not key:
                continue
            token = (series_key, key)
            if token in seen:
                continue
            seen.add(token)
            if entry.get("photo_use_allowed") and entry.get("photo_url"):
                continue
            cached = _driver_identity_cache_get(series_key, name, season)
            if cached is not None:
                continue
            candidates.append((series_key, name))

    selected = candidates[: max(0, min(int(limit or 0), 120))]
    photo_count = 0
    resolved_count = 0
    errors = 0

    def resolve(item: tuple[str, str]) -> dict[str, Any]:
        series_key, name = item
        return get_driver_identity(series_key, name, season=season)

    if selected:
        with ThreadPoolExecutor(max_workers=min(4, len(selected))) as pool:
            futures = [pool.submit(resolve, item) for item in selected]
            for future in as_completed(futures):
                try:
                    result = future.result()
                except Exception:
                    errors += 1
                    continue
                if result.get("resolved"):
                    resolved_count += 1
                if result.get("photo_use_allowed") and result.get("photo_url"):
                    photo_count += 1

    return {
        "season": season,
        "attempted": len(selected),
        "photos": photo_count,
        "resolved": resolved_count,
        "remaining": max(0, len(candidates) - len(selected)),
        "errors": errors,
    }


def clear_standings_cache() -> None:
    with _cache_lock:
        _cache["at"] = None
        _cache["value"] = None
        _snapshot_cache["at"] = None
        _snapshot_cache["season"] = None
        _snapshot_cache["value"] = None
