from pathlib import Path

path = Path("api/early_access_admin.py")
source = path.read_text(encoding="utf-8")

old_import = "from services.prt_applications import list_applications"
new_import = "from services.prt_applications import application_role_from_placement, list_applications"
if old_import not in source and new_import not in source:
    raise SystemExit("Expected prt_applications import not found")
source = source.replace(old_import, new_import, 1)

start = source.index("def _acceptance_message(")
end = source.index("\n\ndef _application_by_id", start)

new_function = '''def _acceptance_message(name: str, code: str, placement: str = "quick-apply") -> str:
    first = (name or "there").strip().split()[0]
    role = application_role_from_placement(placement)

    if role == "Driver":
        return f"""Hey {first},

You’ve been accepted into Pitmark Racing Tools Early Access.

PRT is still actively being developed, and that’s exactly why we want real iRacing drivers involved now. You’ll be helping us test features in actual race conditions, find bugs, and shape what PRT becomes before the public release.

Get started:
{PRT_URL}

Your Early Access code:
{code}

Install the latest PRT Early Access build from the link above, open PRT, go to Settings → Access & Licensing → PRT Early Access, paste the code, and choose ACTIVATE EARLY ACCESS. Your code is personal and binds to your PRT device when activated.

Once you’re installed, get some laps in and use PRT like you normally would during practice, qualifying, and races. We especially want feedback on:

• Overlay accuracy and responsiveness
• Radar / nearby-car behavior
• RPM, inputs, steering and telemetry
• Standings and race information
• Setup/install problems
• Anything confusing, broken, laggy, or just annoying
• Features you wish were there

Don’t worry about giving us polished feedback. Screenshots, quick messages, bug reports, or even “this feels weird” are useful.

Early Access is meant to be collaborative. Things may change quickly between builds as feedback comes in, and testers are directly influencing those changes.

After you activate PRT, we’ll also automatically send you your personal Founder’s Race Hub. That gives you your referral link, standings, milestones, and everything you need if you want to recruit other racers into Early Access.

Thanks for getting involved this early. We’re building PRT around actual racers instead of guessing what racers want.

Welcome aboard.

--
Justin Olson
Founder & Owner | Pitmark Racing Co.

🏁 Leave your mark.
{PRT_URL}
"""

    if role == "Broadcaster":
        intro = (
            "PRT is still actively being developed, and that’s exactly why we want broadcasters and production teams involved now. "
            "You’ll be helping us test PRT in real spectator, replay, and production workflows, find bugs, and shape what the broadcast side becomes before public release.\n\n"
            "Broadcast Studio is in development. Current Early Access lets you pressure-test the PRT foundation around overlays, race information, telemetry, spectator/replay behavior, and production reliability while helping us build Broadcast Studio around real broadcast needs."
        )
        use_copy = "Once you’re installed, use PRT in the same spectator, replay, and live-session workflows you actually broadcast. We especially want feedback on:"
        feedback = """• Spectator and replay behavior\n• Overlay accuracy, readability, and responsiveness\n• Standings, race information, and useful broadcast context\n• Performance while streaming or recording\n• Setup or production-workflow friction\n• Controls, graphics, data, or automation you wish Broadcast Studio had\n• Anything confusing, broken, laggy, or just annoying"""
        closing = "Thanks for getting involved this early. We’re building the broadcast side with real production teams instead of guessing what broadcasters need."
    elif role == "League / Club":
        intro = (
            "PRT is still actively being developed, and that’s exactly why we want league and club operators involved now. "
            "You’ll be helping us test PRT in real race-night and admin workflows, find friction, and shape what the league side becomes before public release."
        )
        use_copy = "Once you’re installed, use PRT around a normal league or club race night and evaluate it from the admin side. We especially want feedback on:"
        feedback = """• Race-night setup and admin workflow\n• Overlays, standings, race information, and race cards\n• What helps or gets in the way for drivers and officials\n• Setup/install problems\n• Missing league or steward tools that would save real time\n• Anything confusing, broken, laggy, or just annoying\n• Features you wish were there"""
        closing = "Thanks for getting involved this early. We’re building the league side with people who actually run race nights instead of guessing what admins need."
    else:
        intro = (
            "PRT is still actively being developed, and that’s exactly why we want media and developers involved now. "
            "You’ll be helping us inspect PRT in real review, evaluation, and development workflows, challenge assumptions, and shape what earns a place in the wider iRacing ecosystem."
        )
        use_copy = "Once you’re installed, inspect PRT the way you normally would when reviewing, evaluating, or building around a sim-racing tool. We especially want feedback on:"
        feedback = """• Setup, onboarding, and product clarity\n• Accuracy and usefulness of the information PRT presents\n• Workflow or interoperability assumptions that do not hold up\n• Performance, reliability, and rough edges\n• Missing context, controls, or capabilities\n• Anything confusing, broken, or misleading\n• Features or integration ideas worth discussing"""
        closing = "Thanks for getting involved this early. We’d rather have candid inspection and useful criticism than favorable coverage or polite feedback."

    return f"""Hey {first},

You’ve been accepted into Pitmark Racing Tools Early Access.

{intro}

Get started:
{PRT_URL}

Your Early Access code:
{code}

Install the latest PRT Early Access build from the link above, open PRT, go to Settings → Access & Licensing → PRT Early Access, paste the code, and choose ACTIVATE EARLY ACCESS. Your code is personal and binds to your PRT device when activated.

{use_copy}

{feedback}

Don’t worry about giving us polished feedback. Screenshots, quick messages, bug reports, clips, or a rough list are all useful.

Early Access is meant to be collaborative. Things may change quickly between builds as feedback comes in, and testers are directly influencing those changes.

After you activate PRT, we’ll also automatically send you your personal Founder’s Race Hub. That gives you your referral link, standings, milestones, and everything you need if you want to recruit other testers into Early Access.

{closing}

Welcome aboard.

--
Justin Olson
Founder & Owner | Pitmark Racing Co.

🏁 Leave your mark.
{PRT_URL}
"""
'''

source = source[:start] + new_function + source[end:]

old_call = '_acceptance_message(name, invite["code"])'
new_call = '_acceptance_message(name, invite["code"], row.get("placement") or "quick-apply")'
if old_call not in source and new_call not in source:
    raise SystemExit("Expected acceptance-message call not found")
source = source.replace(old_call, new_call, 1)

path.write_text(source, encoding="utf-8")
print("Applied role-aware PRT acceptance email patch")
