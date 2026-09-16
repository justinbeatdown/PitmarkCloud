(() => {
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
