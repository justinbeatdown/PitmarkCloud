from pathlib import Path

HTML_MARKER = '  <section class="tester-proof" aria-label="PRT tester feedback">'
SECTION = '''  <section class="audience-fit" aria-label="PRT audience fit">
    <div class="section-head audience-head">
      <p class="eyebrow">BUILT WITH THE PEOPLE WHO USE RACE NIGHT</p>
      <h2>Where do you fit?</h2>
      <p>PRT Early Access is not only a driver test. We want the people who race, run leagues, produce broadcasts, cover sim racing, and build around iRacing to help shape what earns a place on race night.</p>
    </div>
    <div class="audience-grid">
      <article class="audience-card">
        <span class="audience-status">USE IT NOW</span>
        <h3>Drivers</h3>
        <p>Race with live overlays, telemetry, standings, proximity tools, track context, and race-night utilities in real iRacing sessions.</p>
        <small>Advanced coaching and Driver DNA are in development.</small>
        <a href="/prt/apply" data-prt-funnel-link="audience-driver-apply">APPLY AS A TESTER →</a>
      </article>
      <article class="audience-card">
        <span class="audience-status">RUN A SMALL TEST</span>
        <h3>Leagues &amp; Clubs</h3>
        <p>Put PRT through an ordinary league night and tell us where setup, overlays, race cards, support, or admin workflow creates friction.</p>
        <small>No league-wide rollout or purchase commitment required.</small>
        <a href="/prt/apply" data-prt-funnel-link="audience-league-apply">TEST WITH YOUR LEAGUE →</a>
      </article>
      <article class="audience-card">
        <span class="audience-status">SHAPE WHAT'S NEXT</span>
        <h3>Broadcasters</h3>
        <p>Pressure-test the overlay and production assumptions behind PRT and tell us what a real broadcast workflow needs before we call it ready.</p>
        <small>Broadcast Studio is in development; current Early Access helps us build it around real production needs.</small>
        <a href="/prt/apply" data-prt-funnel-link="audience-broadcast-apply">JOIN EARLY ACCESS →</a>
      </article>
      <article class="audience-card">
        <span class="audience-status">INSPECT + CHALLENGE</span>
        <h3>Media / Developers</h3>
        <p>Inspect PRT independently, challenge the product, and talk through responsible interoperability or ecosystem overlap where it makes sense.</p>
        <small>No favorable coverage, endorsement, or closed-door access expected.</small>
        <a href="/prt/support" data-prt-funnel-link="audience-media-contact">TALK TO PITMARK →</a>
      </article>
    </div>
  </section>'''

AUDIENCE_CSS = '''
/* PRT audience fit */
.audience-fit{padding:0 0 78px;border-bottom:1px solid #252929}.audience-head{max-width:920px;margin-bottom:30px}.audience-head p:last-child{max-width:850px;color:#929999;line-height:1.6}.audience-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.audience-card{display:flex;flex-direction:column;min-height:310px;padding:24px;border:1px solid #303535;background:linear-gradient(180deg,#111414,#0a0c0c);transition:border-color .16s ease,transform .16s ease}.audience-card:hover{border-color:#6d351f;transform:translateY(-2px)}.audience-status{display:inline-flex;align-self:flex-start;padding:6px 8px;border:1px solid #4c3328;background:#16110f;color:#ff7838;font-size:9px;font-weight:950;letter-spacing:.85px}.audience-card h3{margin:28px 0 10px;font-size:25px;font-style:italic}.audience-card p{margin:0;color:#a0a6a6;font-size:13px;line-height:1.55}.audience-card small{display:block;margin:14px 0 20px;color:#747c7c;font-size:10px;line-height:1.5}.audience-card a{margin-top:auto;color:#ff7431;text-decoration:none;font-size:10px;font-weight:950;letter-spacing:.7px}.audience-card a:hover{text-decoration:underline}@media(max-width:1050px){.audience-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:620px){.audience-fit{padding-bottom:54px}.audience-grid{grid-template-columns:1fr}.audience-card{min-height:0}.audience-card h3{margin-top:22px}}
'''

html_path = Path('api/prt.html')
html = html_path.read_text(encoding='utf-8')
if 'aria-label="PRT audience fit"' not in html:
    if HTML_MARKER not in html:
        raise SystemExit('Could not find tester-proof insertion marker')
    html = html.replace(HTML_MARKER, SECTION + '\n\n' + HTML_MARKER, 1)
html = html.replace('/prt-growth.css?v=02148', '/prt-growth.css?v=02149', 1)
html_path.write_text(html, encoding='utf-8')

css_path = Path('api/prt-growth.css')
css = css_path.read_text(encoding='utf-8')
if '/* PRT audience fit */' not in css:
    css = css.rstrip() + '\n' + AUDIENCE_CSS
css_path.write_text(css, encoding='utf-8')

print('Applied PRT audience-fit landing section')
