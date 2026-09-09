(() => {
  const form = document.getElementById('quickApplyForm');
  const submit = document.getElementById('applySubmit');
  const status = document.getElementById('applyStatus');
  if (!form || !submit || !status) return;

  const allowedSources = new Set(['facebook','tiktok','instagram','x','discord','league','creator']);
  const allowedAssets = new Set(['race','feedback','invite']);
  const params = new URL(location.href).searchParams;
  const campaignRaw = params.get('utm_campaign') || '';
  const sourceRaw = params.get('utm_source') || '';
  const assetRaw = params.get('utm_content') || '';
  const campaign = campaignRaw === 'prt_raceproof_202609' && allowedSources.has(sourceRaw) && allowedAssets.has(assetRaw)
    ? campaignRaw : '';
  const source = campaign ? sourceRaw : 'website';
  const asset = campaign ? assetRaw : '';

  form.addEventListener('submit', async event => {
    event.preventDefault();
    status.className = 'form-status';
    status.textContent = '';

    if (!form.reportValidity()) return;

    const data = new FormData(form);
    const disciplines = data.getAll('disciplines').map(String).filter(Boolean);
    if (!disciplines.length) {
      status.className = 'form-status error';
      status.textContent = 'Choose at least one iRacing discipline.';
      return;
    }

    const payload = {
      full_name: String(data.get('full_name') || ''),
      email: String(data.get('email') || ''),
      discord_username: String(data.get('discord_username') || ''),
      iracing_name: String(data.get('iracing_name') || ''),
      disciplines,
      race_frequency: String(data.get('race_frequency') || ''),
      current_tools: String(data.get('current_tools') || ''),
      goals: String(data.get('goals') || ''),
      can_test: data.get('can_test') === 'on',
      bug_reports: data.get('bug_reports') === 'on',
      honest_feedback: data.get('honest_feedback') === 'on',
      expectations_agreed: data.get('expectations_agreed') === 'on',
      company_website: String(data.get('company_website') || ''),
      campaign,
      source,
      asset,
      placement: 'quick-apply'
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
      status.className = 'form-status success';
      status.innerHTML = result.duplicate
        ? 'We already have a recent application for that email. No need to submit again — watch your email/Discord for Pitmark follow-up.'
        : 'Application received. If accepted, Pitmark will send your Early Access activation code and setup instructions. <a href="https://discord.gg/jP6fQuW7dr" target="_blank" rel="noopener noreferrer">Join the PRT Discord</a> while you wait.';
      submit.textContent = 'APPLICATION RECEIVED';
    } catch (error) {
      status.className = 'form-status error';
      status.textContent = error?.message || 'Application could not be submitted. Try again or use the legacy Google Form below.';
      submit.disabled = false;
      submit.textContent = 'SUBMIT PRT EARLY ACCESS APPLICATION';
    }
  });
})();