from __future__ import annotations
import logging
from typing import Any
from urllib.parse import urlencode
import httpx
from services.discord_hq_blueprint import *
from utils.config import settings
log=logging.getLogger("pitmark.discord.hq")
DISCORD_API="https://discord.com/api/v10"; DISCORD_AUTHORIZE="https://discord.com/oauth2/authorize"

def hq_install_url()->str:
    if not settings.discord_client_id:return ""
    return f"{DISCORD_AUTHORIZE}?"+urlencode({"client_id":settings.discord_client_id,"scope":"bot applications.commands","permissions":str(settings.discord_hq_install_permissions or HQ_REQUIRED_BOT_PERMISSIONS),"guild_id":settings.discord_hq_guild_id,"disable_guild_select":"true"})

def headers(reason:str|None=None)->dict[str,str]:
    h={"Authorization":f"Bot {settings.discord_bot_token}","Content-Type":"application/json"}
    if reason:h["X-Audit-Log-Reason"]=reason[:512]
    return h

async def preflight(guild_id:str,require_community:bool)->dict[str,Any]:
    if not configured() or guild_id!=settings.discord_hq_guild_id:raise RuntimeError("Pitmark HQ guild/owner settings are not configured for this server.")
    async with httpx.AsyncClient(timeout=20.0) as c:
        r=await c.get(f"{DISCORD_API}/users/@me",headers=headers());r.raise_for_status();bot_id=str(r.json()["id"])
        r=await c.get(f"{DISCORD_API}/guilds/{guild_id}",headers=headers());r.raise_for_status();guild=r.json()
        r=await c.get(f"{DISCORD_API}/guilds/{guild_id}/roles",headers=headers());r.raise_for_status();roles=r.json()
        r=await c.get(f"{DISCORD_API}/guilds/{guild_id}/members/{bot_id}",headers=headers());r.raise_for_status();member=r.json()
    role_ids={guild_id,*[str(x) for x in member.get("roles") or []]};perms=0
    for role in roles:
        if str(role.get("id")) in role_ids:perms|=int(role.get("permissions") or 0)
    if perms&ADMINISTRATOR:perms=(1<<53)-1
    checks=[(MANAGE_CHANNELS,"Manage Channels"),(MANAGE_ROLES,"Manage Roles"),(MANAGE_GUILD,"Manage Server"),(MANAGE_MESSAGES,"Manage Messages"),(MODERATE_MEMBERS,"Timeout Members"),(KICK_MEMBERS,"Kick Members"),(BAN_MEMBERS,"Ban Members"),(MOVE_MEMBERS,"Move Members"),(MENTION_EVERYONE,"Mention roles")]
    missing=[label for bit,label in checks if not perms&bit];community="COMMUNITY" in (guild.get("features") or [])
    if require_community and not community:raise RuntimeError("Enable Discord Community mode before bootstrap so Pitmark can create Forum channels.")
    return {"bot_user_id":bot_id,"permissions":perms,"missing_permissions":missing,"community":community}

async def list_roles(guild_id:str)->list[dict[str,Any]]:
    async with httpx.AsyncClient(timeout=20.0) as c:r=await c.get(f"{DISCORD_API}/guilds/{guild_id}/roles",headers=headers());r.raise_for_status();return list(r.json())
async def list_channels(guild_id:str)->list[dict[str,Any]]:
    async with httpx.AsyncClient(timeout=20.0) as c:r=await c.get(f"{DISCORD_API}/guilds/{guild_id}/channels",headers=headers());r.raise_for_status();return list(r.json())

async def ensure_structure(guild_id:str,owner_user_id:str)->dict[str,Any]:
    pf=await preflight(guild_id,True)
    if pf["missing_permissions"]:raise RuntimeError("Missing HQ bot permissions: "+", ".join(pf["missing_permissions"])+". Re-authorize: "+hq_install_url())
    role_map={str(r.get("name")):r for r in await list_roles(guild_id)};role_created=0
    for name,color,perms in ROLE_SPECS:
        role,made=await ensure_role(guild_id,role_map.get(name),name,color,perms);role_map[name]=role;role_created+=int(made)
    await assign_role(guild_id,owner_user_id,str(role_map["Pitmark Owner"]["id"]))
    channels=await list_channels(guild_id);channel_map={};cat_created=0;channel_created=0;bot_id=pf["bot_user_id"]
    for cat_name,children in PUBLIC_CATEGORY_SPECS:
        cat,made=await ensure_category(guild_id,channels,cat_name,[overwrite(bot_id,1,allow=VIEW_CHANNEL|SEND_MESSAGES|READ_MESSAGE_HISTORY|EMBED_LINKS|ATTACH_FILES|CONNECT|SPEAK)]);cat_created+=int(made);channels=await list_channels(guild_id)
        for name,typ,topic,access,tags in children:
            ch,made_ch=await ensure_channel(guild_id,channels,cat,name,typ,topic,channel_overwrites(guild_id,role_map,bot_id,access),tags);channel_map[name]=ch;channel_created+=int(made_ch)
            if made_ch:await seed_channel(ch)
            channels=await list_channels(guild_id)
    for cat_name,audience,children in PRIVATE_CATEGORY_SPECS:
        cat,made=await ensure_category(guild_id,channels,cat_name,private_overwrites(guild_id,role_map,bot_id,audience));cat_created+=int(made);channels=await list_channels(guild_id)
        for name,typ,topic in children:
            ch,made_ch=await ensure_channel(guild_id,channels,cat,name,typ,topic,[],None);channel_map[name]=ch;channel_created+=int(made_ch);channels=await list_channels(guild_id)
    return {"roles_created":role_created,"categories_created":cat_created,"channels_created":channel_created,"role_map":role_map,"channel_map":channel_map,"bot_user_id":bot_id}

async def ensure_role(guild_id:str,existing:dict[str,Any]|None,name:str,color:int,perms:int)->tuple[dict[str,Any],bool]:
    payload={"name":name,"color":color,"permissions":str(perms),"hoist":name.startswith("Pitmark ") and name!="Pitmark Developer","mentionable":False}
    async with httpx.AsyncClient(timeout=20.0) as c:
        if existing:r=await c.patch(f"{DISCORD_API}/guilds/{guild_id}/roles/{existing['id']}",headers=headers("Pitmark HQ role sync"),json=payload);r.raise_for_status();return r.json(),False
        r=await c.post(f"{DISCORD_API}/guilds/{guild_id}/roles",headers=headers("Pitmark HQ bootstrap"),json=payload);r.raise_for_status();return r.json(),True
async def assign_role(guild_id:str,user_id:str,role_id:str)->None:
    async with httpx.AsyncClient(timeout=20.0) as c:r=await c.put(f"{DISCORD_API}/guilds/{guild_id}/members/{user_id}/roles/{role_id}",headers=headers("Assign Pitmark Owner role"));r.raise_for_status() if r.status_code not in {200,204} else None
async def ensure_category(guild_id:str,channels:list[dict[str,Any]],name:str,overwrites:list[dict[str,Any]])->tuple[dict[str,Any],bool]:
    existing=next((x for x in channels if x.get("type")==4 and x.get("name")==name),None)
    async with httpx.AsyncClient(timeout=20.0) as c:
        if existing:r=await c.patch(f"{DISCORD_API}/channels/{existing['id']}",headers=headers("Pitmark HQ category sync"),json={"permission_overwrites":overwrites});r.raise_for_status();return r.json(),False
        r=await c.post(f"{DISCORD_API}/guilds/{guild_id}/channels",headers=headers("Pitmark HQ bootstrap"),json={"name":name,"type":4,"permission_overwrites":overwrites});r.raise_for_status();return r.json(),True
async def ensure_channel(guild_id:str,channels:list[dict[str,Any]],cat:dict[str,Any],name:str,typ:int,topic:str|None,overwrites:list[dict[str,Any]],tags:list[str]|None)->tuple[dict[str,Any],bool]:
    existing=next((x for x in channels if x.get("type")==typ and x.get("name")==name and str(x.get("parent_id") or "")==str(cat["id"])),None);payload:dict[str,Any]={"name":name,"type":typ,"parent_id":str(cat["id"])}
    if topic and typ in {0,5,15}:payload["topic"]=topic
    if overwrites:payload["permission_overwrites"]=overwrites
    if typ==15:payload.update({"default_auto_archive_duration":1440,"available_tags":[{"name":x,"moderated":False} for x in (tags or [])[:20]]})
    if typ==2:payload["bitrate"]=64000
    async with httpx.AsyncClient(timeout=20.0) as c:
        if existing:r=await c.patch(f"{DISCORD_API}/channels/{existing['id']}",headers=headers("Pitmark HQ channel sync"),json={k:v for k,v in payload.items() if k!="type"});r.raise_for_status();return r.json(),False
        r=await c.post(f"{DISCORD_API}/guilds/{guild_id}/channels",headers=headers("Pitmark HQ bootstrap"),json=payload);r.raise_for_status();return r.json(),True

async def seed_channel(channel:dict[str,Any])->None:
    if int(channel.get("type") or 0) not in {0,5}:return
    msgs={"welcome":"🏁 **Welcome to Pitmark Racing Co.**\nThis is the live community and support hub for Pitmark Racing Tools, Pitmark services, racing leagues, partners and the racing community. **Leave Your Mark.**","rules":"📜 **Pitmark Community Rules**\n1. Respect other members.\n2. No harassment, hate speech, threats, scams, piracy or spam.\n3. Keep content in the appropriate channel.\n4. Never post passwords, license keys, order details, addresses, email addresses or other sensitive information publicly.\n5. Staff decisions and Discord Terms of Service apply.","pitmark-links":"🔗 **Pitmark Racing Co.**\nWebsite & Store: https://pitmarkracing.com\nPitmark Racing Tools: https://prt.pitmarkracing.com\nNeed help? Use the Support Center below.","service-status":"🟢 **Pitmark services operational**\nThis channel is used for official service-status and incident updates.","common-questions":"❓ **Common Questions**\nFor account, setup, product, order or technical help, open a private ticket in **support-start-here**. Never post sensitive account or order information in public channels.","become-a-partner":"🤝 **Become a Pitmark Partner**\nInterested in partnering as a driver, league, track, creator or racing organization? Visit https://pitmarkracing.com or open a Partnership ticket in the Support Center.","prt-announcements":"🏎️ **Pitmark Racing Tools**\nRelease notes, service notices and major Racing Tools updates will be posted here."}
    if channel.get("name") in msgs:await send_message(str(channel["id"]),{"content":msgs[str(channel["name"])]})
async def send_message(channel_id:str,payload:dict[str,Any])->dict[str,Any]:
    async with httpx.AsyncClient(timeout=20.0) as c:r=await c.post(f"{DISCORD_API}/channels/{channel_id}/messages",headers=headers(),json=payload);r.raise_for_status();return r.json()
async def upsert_panel(channel_id:str,title:str,payload:dict[str,Any])->None:
    async with httpx.AsyncClient(timeout=20.0) as c:
        r=await c.get(f"{DISCORD_API}/channels/{channel_id}/messages",headers=headers(),params={"limit":50});r.raise_for_status();existing=next((m for m in r.json() if (m.get("embeds") or []) and str(m["embeds"][0].get("title") or "")==title),None)
        u=await(c.patch(f"{DISCORD_API}/channels/{channel_id}/messages/{existing['id']}",headers=headers(),json=payload) if existing else c.post(f"{DISCORD_API}/channels/{channel_id}/messages",headers=headers(),json=payload));u.raise_for_status()
async def log_named(guild_id:str,name:str,text:str)->None:
    ch=next((x for x in await list_channels(guild_id) if x.get("name")==name and x.get("type")==0),None)
    if ch:await send_message(str(ch["id"]),{"content":text})
async def edit_original(payload:dict[str,Any],content:str)->None:
    app_id=str(payload.get("application_id") or settings.discord_client_id or "");token=str(payload.get("token") or "")
    if not app_id or not token:return
    try:
        async with httpx.AsyncClient(timeout=20.0) as c:r=await c.patch(f"{DISCORD_API}/webhooks/{app_id}/{token}/messages/@original",json={"content":content[:1900]});r.raise_for_status()
    except Exception:log.exception("Failed to edit deferred Discord response")
