from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"Expected source text not found in {path}: {old[:120]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# Route each audience card into the same application with its role preselected.
for role, placement in (
    ("driver", "audience-driver-apply"),
    ("league", "audience-league-apply"),
    ("broadcaster", "audience-broadcast-apply"),
):
    replace_once(
        "api/prt.html",
        f'href="/prt/apply" data-prt-funnel-link="{placement}"',
        f'href="/prt/apply?role={role}" data-prt-funnel-link="{placement}"',
    )
replace_once(
    "api/prt.html",
    'href="/prt/support" data-prt-funnel-link="audience-media-contact">TALK TO PITMARK →</a>',
    'href="/prt/apply?role=media" data-prt-funnel-link="audience-media-contact">INSPECT PRT / JOIN EARLY ACCESS →</a>',
)

# Add a role selector and addressable labels while retaining the existing driver fields.
replace_once(
    "api/prt-apply.html",
    '<form id="quickApplyForm" class="apply-form" novalidate>\n        <div class="field-grid">',
    '''<form id="quickApplyForm" class="apply-form" novalidate>\n        <fieldset style="border:0;padding:0;margin:0">\n          <legend class="field-label">I’M HERE AS</legend>\n          <div class="choice-grid" role="radiogroup" aria-label="PRT applicant role">\n            <label class="choice-pill"><input type="radio" name="applicant_role" value="driver" checked> Driver</label>\n            <label class="choice-pill"><input type="radio" name="applicant_role" value="league"> League or Club</label>\n            <label class="choice-pill"><input type="radio" name="applicant_role" value="broadcaster"> Broadcaster</label>\n            <label class="choice-pill"><input type="radio" name="applicant_role" value="media"> Media or Developer</label>\n          </div>\n        </fieldset>\n\n        <div class="field-grid">''',
)
replace_once(
    "api/prt-apply.html",
    '<label>iRACING DISPLAY NAME<input name="iracing_name" type="text" maxlength="120" autocomplete="off" required></label>',
    '<label><span id="iracingNameLabel">iRACING DISPLAY NAME</span><input name="iracing_name" type="text" maxlength="120" autocomplete="off" required></label>',
)
replace_once(
    "api/prt-apply.html",
    '<fieldset style="border:0;padding:0;margin:0">\n          <legend class="field-label">WHAT DO YOU RACE ON iRACING?',
    '<fieldset id="disciplinesFieldset" style="border:0;padding:0;margin:0">\n          <legend class="field-label">WHAT DO YOU RACE ON iRACING?',
)
replace_once(
    "api/prt-apply.html",
    '<label>HOW OFTEN DO YOU RACE?\n            <select name="race_frequency" required>',
    '<label><span id="raceFrequencyLabel">HOW OFTEN DO YOU RACE?</span>\n            <select name="race_frequency" required>',
)
replace_once(
    "api/prt-apply.html",
    '<label>CURRENT RACING TOOLS <span style="color:#737a7a;font-weight:700">(OPTIONAL)</span><input name="current_tools" type="text" maxlength="320" placeholder="RaceLab, iOverlay, Crew Chief, Garage61…"></label>',
    '<label><span id="currentToolsLabel">CURRENT RACING TOOLS</span> <span style="color:#737a7a;font-weight:700">(OPTIONAL)</span><input name="current_tools" type="text" maxlength="320" placeholder="RaceLab, iOverlay, Crew Chief, Garage61…"></label>',
)
replace_once(
    "api/prt-apply.html",
    '<label>WHAT WOULD MAKE PRT GENUINELY USEFUL TO YOU? <span style="color:#737a7a;font-weight:700">(OPTIONAL)</span>',
    '<label><span id="goalsLabel">WHAT WOULD MAKE PRT GENUINELY USEFUL TO YOU?</span> <span style="color:#737a7a;font-weight:700">(OPTIONAL)</span>',
)
replace_once(
    "api/prt-apply.html",
    'I can test PRT in real iRacing sessions and send honest bug/feature feedback. I understand Early Access is active development,',
    '<span id="testerAgreementCopy">I can test PRT in real iRacing sessions and send honest bug/feature feedback.</span> I understand Early Access is active development,',
)
replace_once(
    "api/prt-apply.html",
    '<script src="/prt-apply.js?v=02148" defer></script>',
    '<script src="/prt-apply.js?v=02150" defer></script>',
)

# Replace the application behavior with role-aware labels, requirements, and placement tracking.
Path("api/prt-apply.js").write_text(r'''(() => {
  const form = document.getElementById('quickApplyForm');
  const submit = document.getElementById('applySubmit');
  const status = document.getElementById('applyStatus');
  if (!form || !submit || !status) return;

  const allowedSources = new Set(['facebook','tiktok','instagram','x','discord','league','creator']);
  const allowedAssets = new Set(['race','feedback','invite']);
  const allowedRoles = new Set(['driver','league','broadcaster','media']);
  const params = new URL(location.href).searchParams;
  const campaignRaw = params.get('utm_campaign') || '';
  const sourceRaw = params.get('utm_source') || '';
  const assetRaw = params.get('utm_content') || '';
  const campaign = campaignRaw === 'prt_raceproof_202609' && allowedSources.has(sourceRaw) && allowedAssets.has(assetRaw)
    ? campaignRaw : '';
  const source = campaign ? sourceRaw : 'website';
  const asset = campaign ? assetRaw : '';

  const nonDriverIdentityLabel = 'Organization / league / outlet / project';
  const roleConfig = {
    driver: {
      placement: 'quick-apply-driver',
      identityLabel: 'iRACING DISPLAY NAME',
      identityPlaceholder: '',
      frequencyLabel: 'HOW OFTEN DO YOU RACE?',
      toolsLabel: 'CURRENT RACING TOOLS',
      toolsPlaceholder: 'RaceLab, iOverlay, Crew Chief, Garage61…',
      goalsLabel: 'WHAT WOULD MAKE PRT GENUINELY USEFUL TO YOU?',
      agreement: 'I can test PRT in real iRacing sessions and send honest bug/feature feedback.',
      discipline: '',
    },
    league: {
      placement: 'quick-apply-league',
      identityLabel: 'LEAGUE / CLUB NAME',
      identityPlaceholder: nonDriverIdentityLabel,
      frequencyLabel: 'HOW OFTEN DOES YOUR LEAGUE USE iRACING?',
      toolsLabel: 'CURRENT LEAGUE / ADMIN TOOLS',
      toolsPlaceholder: 'Race control, league admin, overlays, Discord tools…',
      goalsLabel: 'WHAT WOULD MAKE PRT USEFUL TO YOUR LEAGUE OR CLUB?',
      agreement: 'I can test or review PRT in a real workflow and send honest feedback.',
      discipline: 'League / Club',
    },
    broadcaster: {
      placement: 'quick-apply-broadcaster',
      identityLabel: 'BROADCAST / PRODUCTION NAME',
      identityPlaceholder: nonDriverIdentityLabel,
      frequencyLabel: 'HOW OFTEN DO YOU PRODUCE iRACING BROADCASTS?',
      toolsLabel: 'CURRENT BROADCAST / PRODUCTION TOOLS',
      toolsPlaceholder: 'OBS, ATVO, SDK tools, graphics, timing systems…',
      goalsLabel: 'WHAT WOULD A USEFUL PRT BROADCAST WORKFLOW NEED?',
      agreement: 'I can test or review PRT in a real workflow and send honest feedback.',
      discipline: 'Broadcaster / Production',
    },
    media: {
      placement: 'quick-apply-media',
      identityLabel: 'OUTLET / PROJECT / COMPANY',
      identityPlaceholder: nonDriverIdentityLabel,
      frequencyLabel: 'HOW OFTEN DO YOU WORK WITH iRACING OR SIM RACING?',
      toolsLabel: 'CURRENT TOOLS / WORKFLOW',
      toolsPlaceholder: 'Editorial, developer, telemetry, API, review or community tools…',
      goalsLabel: 'WHAT WOULD YOU LIKE TO INSPECT, TEST, OR DISCUSS?',
      agreement: 'I can test or review PRT in a real workflow and send honest feedback.',
      discipline: 'Media / Developer',
    },
  };

  const identityInput = form.elements.iracing_name;
  const frequencySelect = form.elements.race_frequency;
  const toolsInput = form.elements.current_tools;
  const goalsInput = form.elements.goals;
  const disciplinesFieldset = document.getElementById('disciplinesFieldset');
  const iracingNameLabel = document.getElementById('iracingNameLabel');
  const raceFrequencyLabel = document.getElementById('raceFrequencyLabel');
  const currentToolsLabel = document.getElementById('currentToolsLabel');
  const goalsLabel = document.getElementById('goalsLabel');
  const testerAgreementCopy = document.getElementById('testerAgreementCopy');
  const roleRadios = [...form.querySelectorAll('input[name="applicant_role"]')];
  const disciplineBoxes = [...form.querySelectorAll('input[name="disciplines"]')];

  const driverFrequencyOptions = [
    ['', 'Choose one'],
    ['Almost every day', 'Almost every day'],
    ['3–5 days per week', '3–5 days per week'],
    ['1–2 days per week', '1–2 days per week'],
    ['A few times per month', 'A few times per month'],
    ['Less often / special events', 'Less often / special events'],
  ];
  const nonDriverFrequencyOptions = [
    ['', 'Choose one'],
    ['Every week', 'Every week'],
    ['A few times per month', 'A few times per month'],
    ['Occasionally / special events', 'Occasionally / special events'],
    ['Not currently — reviewing or building workflows', 'Not currently — reviewing or building workflows'],
  ];

  const currentRole = () => {
    const selected = roleRadios.find(input => input.checked)?.value || 'driver';
    return allowedRoles.has(selected) ? selected : 'driver';
  };

  const setFrequencyOptions = role => {
    const prior = frequencySelect.value;
    const options = role === 'driver' ? driverFrequencyOptions : nonDriverFrequencyOptions;
    frequencySelect.replaceChildren(...options.map(([value, label]) => {
      const option = document.createElement('option');
      option.value = value;
      option.textContent = label;
      return option;
    }));
    if ([...frequencySelect.options].some(option => option.value === prior)) frequencySelect.value = prior;
  };

  const applyRole = role => {
    role = allowedRoles.has(role) ? role : 'driver';
    const config = roleConfig[role];
    roleRadios.forEach(input => { input.checked = input.value === role; });
    iracingNameLabel.textContent = config.identityLabel;
    identityInput.placeholder = config.identityPlaceholder;
    raceFrequencyLabel.textContent = config.frequencyLabel;
    currentToolsLabel.textContent = config.toolsLabel;
    toolsInput.placeholder = config.toolsPlaceholder;
    goalsLabel.textContent = config.goalsLabel;
    testerAgreementCopy.textContent = config.agreement;
    disciplinesFieldset.hidden = role !== 'driver';
    disciplineBoxes.forEach(box => { box.disabled = role !== 'driver'; });
    setFrequencyOptions(role);
  };

  const requestedRole = params.get('role') || 'driver';
  applyRole(allowedRoles.has(requestedRole) ? requestedRole : 'driver');
  roleRadios.forEach(input => input.addEventListener('change', () => applyRole(input.value)));

  form.addEventListener('submit', async event => {
    event.preventDefault();
    status.className = 'form-status';
    status.textContent = '';

    if (!form.reportValidity()) return;

    const data = new FormData(form);
    const role = currentRole();
    const config = roleConfig[role];
    const disciplines = role === 'driver'
      ? data.getAll('disciplines').map(String).filter(Boolean)
      : [config.discipline];
    if (role === 'driver' && !disciplines.length) {
      status.className = 'form-status error';
      status.textContent = 'Choose at least one iRacing discipline.';
      return;
    }

    const agreed = data.get('tester_agreement') === 'on';
    const payload = {
      full_name: String(data.get('full_name') || ''),
      email: String(data.get('email') || ''),
      discord_username: String(data.get('discord_username') || ''),
      iracing_name: String(data.get('iracing_name') || ''),
      disciplines,
      race_frequency: String(data.get('race_frequency') || ''),
      current_tools: String(data.get('current_tools') || ''),
      goals: String(data.get('goals') || ''),
      can_test: agreed,
      bug_reports: agreed,
      honest_feedback: agreed,
      expectations_agreed: agreed,
      company_website: String(data.get('company_website') || ''),
      campaign,
      source,
      asset,
      placement: config.placement
    };

    submit.disabled = true;
    submit.textContent = 'SENDING APPLICATION…';
    try {
      const response = await fetch('/api/prt/apply', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        credentials: 'same-origin',
        body: JSON.stringify(payload)
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.detail || 'Application could not be submitted.');

      form.reset();
      applyRole(role);
      status.className = 'form-status success';
      status.innerHTML = result.duplicate
        ? 'We already have a recent application for that email. No need to submit again — watch your email/Discord for Pitmark follow-up.'
        : 'Application received. If accepted, Pitmark will send your Early Access activation code and setup instructions. <a href="https://discord.gg/jP6fQuW7dr" target="_blank" rel="noopener noreferrer">Join the PRT Discord</a> while you wait.';
      submit.textContent = 'APPLICATION RECEIVED';
    } catch (error) {
      status.className = 'form-status error';
      status.textContent = error?.message || 'Application could not be submitted. Try again or use the legacy Google Form below.';
      submit.disabled = false;
      submit.textContent = 'APPLY FOR FREE EARLY ACCESS';
    }
  });
})();
''', encoding="utf-8")

# Make notification and validation wording role-aware without changing the DB schema.
backend = Path("services/prt_applications.py")
text = backend.read_text(encoding="utf-8")
needle = '''def _notification_recipient() -> str:\n    return (os.getenv("PRT_APPLICATION_NOTIFY_TO") or "justin@pitmarkracing.com").strip()\n\n\ndef _notify_new_application(row: PrtEarlyAccessApplication) -> bool:\n'''
replacement = '''def _notification_recipient() -> str:\n    return (os.getenv("PRT_APPLICATION_NOTIFY_TO") or "justin@pitmarkracing.com").strip()\n\n\ndef application_role_from_placement(placement: str | None) -> str:\n    role = (placement or "").strip().lower().removeprefix("quick-apply-")\n    return {\n        "league": "League / Club",\n        "broadcaster": "Broadcaster",\n        "media": "Media / Developer",\n        "driver": "Driver",\n    }.get(role, "Driver")\n\n\ndef _notify_new_application(row: PrtEarlyAccessApplication) -> bool:\n'''
if needle not in text:
    raise SystemExit("Could not find notification helper insertion point")
text = text.replace(needle, replacement, 1)
old_notify = '''    subject = f"[PRT Early Access] New application — {row.full_name}"\n    text = (\n        "A new PRT Early Access Quick Apply was submitted.\\n\\n"\n        f"Applicant: {row.full_name}\\n"\n        f"Email: {row.email}\\n"\n        f"iRacing: {row.iracing_name}\\n"\n        f"Discord: {row.discord_username or 'Not provided'}\\n"\n        f"Disciplines: {row.disciplines}\\n"\n'''
new_notify = '''    applicant_role = application_role_from_placement(row.placement)\n    is_driver = applicant_role == "Driver"\n    subject = f"[PRT Early Access] New {applicant_role} application — {row.full_name}"\n    text = (\n        "A new PRT Early Access Quick Apply was submitted.\\n\\n"\n        f"Applicant: {row.full_name}\\n"\n        f"Email: {row.email}\\n"\n        f"{'iRacing' if is_driver else 'Organization / outlet'}: {row.iracing_name}\\n"\n        f"Discord: {row.discord_username or 'Not provided'}\\n"\n        f"{'Disciplines' if is_driver else 'Applicant role'}: {row.disciplines}\\n"\n'''
if old_notify not in text:
    raise SystemExit("Could not find notification body")
text = text.replace(old_notify, new_notify, 1)
old_validation = '''    if len(clean_iracing) < 2:\n        raise ValueError("Enter your iRacing display name.")\n    if not clean_disciplines:\n        raise ValueError("Choose at least one iRacing discipline.")\n'''
new_validation = '''    applicant_role = application_role_from_placement(placement)\n    is_driver = applicant_role == "Driver"\n    if len(clean_iracing) < 2:\n        raise ValueError("Enter your iRacing display name." if is_driver else "Enter your organization / outlet / project name.")\n    if not clean_disciplines:\n        raise ValueError("Choose at least one iRacing discipline." if is_driver else "Choose your PRT applicant role.")\n'''
if old_validation not in text:
    raise SystemExit("Could not find application validation block")
text = text.replace(old_validation, new_validation, 1)
backend.write_text(text, encoding="utf-8")

print("Applied role-aware PRT application change")
