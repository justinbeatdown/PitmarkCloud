(function(){
  'use strict';

  const PREF_KEY='pitmark-race-center-consumer-v1';
  const LEGACY_PREF_KEY='pitmark-race-center-v5';
  const RECENT_SEARCH_KEY='pitmark-race-center-recent-searches';
  const $=(selector,root=document)=>(root||document).querySelector(selector);
  const $$=(selector,root=document)=>Array.from((root||document).querySelectorAll(selector));
  const esc=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const view=String(document.body.dataset.view||'hub');
  let graphCache=null;
  let graphPromise=null;

  function readPrefs(){
    try{
      const raw=JSON.parse(localStorage.getItem(PREF_KEY)||'{}');
      return {
        complete:Boolean(raw.complete),
        interests:Array.isArray(raw.interests)?raw.interests.map(String):[],
        region:String(raw.region||'').trim(),
        updatedAt:Number(raw.updatedAt||0)
      };
    }catch(_error){
      return {complete:false,interests:[],region:'',updatedAt:0};
    }
  }

  function writePrefs(next){
    try{localStorage.setItem(PREF_KEY,JSON.stringify({...next,updatedAt:Date.now()}));}catch(_error){}
  }

  function legacyPrefs(){
    try{
      const raw=JSON.parse(localStorage.getItem(LEGACY_PREF_KEY)||'{}');
      return {
        favorites:Array.isArray(raw.favorites)?raw.favorites.map(String):[],
        drivers:Array.isArray(raw.drivers)?raw.drivers.map(String):[],
        lastSeries:String(raw.lastSeries||'')
      };
    }catch(_error){return {favorites:[],drivers:[],lastSeries:''};}
  }

  function writeLegacyPrefs(next){
    try{localStorage.setItem(LEGACY_PREF_KEY,JSON.stringify(next));}catch(_error){}
  }

  async function getJson(url){
    const response=await fetch(url,{credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json'}});
    if(!response.ok)throw new Error('Race Center data unavailable');
    return response.json();
  }

  function graph(){
    if(graphCache)return Promise.resolve(graphCache);
    if(graphPromise)return graphPromise;
    graphPromise=getJson('/api/public/race-center/graph?v=consumer-launch')
      .then(data=>{graphCache=data;return data;})
      .finally(()=>{graphPromise=null;});
    return graphPromise;
  }

  function raceDay(){
    if(window.__pitmarkRaceDayPromise)return window.__pitmarkRaceDayPromise;
    const promise=getJson('/api/public/race-center/race-day?v=home-shared');
    window.__pitmarkRaceDayPromise=promise;
    const clear=()=>setTimeout(()=>{
      if(window.__pitmarkRaceDayPromise===promise)delete window.__pitmarkRaceDayPromise;
    },1500);
    promise.then(clear,clear);
    return promise;
  }

  function href(type,item){
    if(type==='driver'){
      const series=(item.series&&item.series[0]&&item.series[0].series_key)||(item.grassroots?'grassroots':'');
      return '/race-center/driver/'+encodeURIComponent(series)+'/'+encodeURIComponent(String(item.name||''));
    }
    if(type==='series')return '/race-center/series/'+encodeURIComponent(String(item.series_key||item.key||''));
    return '/race-center/'+type+'/'+encodeURIComponent(String(item.key||''));
  }

  function eventWhen(value){
    if(!value)return '';
    const date=new Date(value);
    if(Number.isNaN(date.getTime()))return '';
    return new Intl.DateTimeFormat(undefined,{weekday:'short',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}).format(date);
  }

  function consumerMedia(url,title){
    const src=String(url||'').trim();
    if(!src)return '<span class="consumer-media consumer-media-fallback" aria-hidden="true"><b>RACE</b><i>CENTER</i></span>';
    return '<span class="consumer-media"><img src="'+esc(src)+'" alt="" loading="lazy" decoding="async"><span class="consumer-media-shade"></span></span>';
  }

  function consumerCard(kicker,title,body,url,mediaUrl='',extra=''){
    return '<a class="consumer-card '+(mediaUrl?'has-media':'')+'" href="'+esc(url||'#')+'">'+
      consumerMedia(mediaUrl,title)+
      '<span class="consumer-card-copy"><span class="consumer-kicker">'+esc(kicker)+'</span>'+
      '<strong>'+esc(title||'Racing')+'</strong>'+
      '<p>'+esc(body||'')+'</p>'+extra+
      '<b>Open →</b></span></a>';
  }

  function seriesMedia(seriesByKey,key){
    const item=seriesByKey.get(String(key||''));
    return String(item?.logo_url||'').trim();
  }

  function trackMedia(track,seriesByKey){
    const rows=Array.isArray(track?.series)?track.series:[];
    for(const raw of rows){
      const key=typeof raw==='string'?raw:(raw?.series_key||raw?.key);
      const media=seriesMedia(seriesByKey,key);
      if(media)return media;
    }
    return '';
  }

  function emptyState(title,body,actionHref='',action=''){
    const control=actionHref==='#'
      ?'<button class="button consumer-customize" type="button">'+esc(action||'Customize My Racing')+'</button>'
      :(actionHref?'<a class="button" href="'+esc(actionHref)+'">'+esc(action||'Explore racing')+'</a>':'');
    return '<div class="consumer-empty"><span class="consumer-empty-mark">P</span><div><strong>'+esc(title)+'</strong><p>'+esc(body)+'</p>'+control+'</div></div>';
  }

  function interestMatches(series,interest){
    const hay=[series.series_name,series.name,series.short_name,series.group].filter(Boolean).join(' ').toLowerCase();
    const map={
      dirt:['dirt','sprint','late model','modified','midget'],
      sprint:['sprint','410','360','305','ascs','outlaws','high limit'],
      latemodel:['late model','super late','lucas oil'],
      nascar:['nascar','arca','cars tour','asa'],
      openwheel:['indycar','formula','f1','usac','midget','sprint'],
      sportscar:['imsa','wec','gt','sports car','sportscar'],
      drag:['nhra','drag'],
      local:['local','regional','grassroots','dirtcar','imca']
    };
    return (map[interest]||[]).some(token=>hay.includes(token));
  }

  async function saveOnboarding(){
    const dialog=$('#consumerOnboarding');
    if(!dialog)return;
    const interests=$$('input[name="consumerInterest"]:checked',dialog).map(input=>String(input.value));
    const region=String($('#consumerRegion',dialog)?.value||'').trim();
    const next={complete:true,interests,region};
    writePrefs(next);

    try{
      const data=await graph();
      const legacy=legacyPrefs();
      const current=new Set(legacy.favorites||[]);
      const candidates=(data.series||[]).filter(series=>interests.some(interest=>interestMatches(series,interest))).slice(0,8);
      candidates.forEach(series=>{
        const key=String(series.series_key||series.key||'').trim();
        if(key)current.add(key);
      });
      writeLegacyPrefs({...legacy,favorites:[...current]});

      const account=await fetch('/api/public/race-center/account',{credentials:'same-origin',cache:'no-store'})
        .then(response=>response.ok?response.json():null).catch(()=>null);
      if(account?.authenticated){
        await Promise.allSettled(candidates.map(series=>{
          const key=String(series.series_key||series.key||'').trim();
          if(!key)return Promise.resolve();
          return fetch('/api/public/race-center/follows',{
            method:'PUT',
            credentials:'same-origin',
            headers:{'Content-Type':'application/json',Accept:'application/json'},
            body:JSON.stringify({kind:'series',key,label:series.name||series.series_name||key,series_key:key})
          });
        }));
      }
    }catch(_error){}

    dialog.close();
    location.reload();
  }

  function openOnboarding(force=false){
    const dialog=$('#consumerOnboarding');
    if(!dialog)return;
    const prefs=readPrefs();
    if(!force&&prefs.complete)return;
    if(!force){
      const legacy=legacyPrefs();
      if((legacy.favorites||[]).length||(legacy.drivers||[]).length){
        writePrefs({...prefs,complete:true});
        return;
      }
    }
    if(prefs.region&&$('#consumerRegion',dialog))$('#consumerRegion',dialog).value=prefs.region;
    prefs.interests.forEach(key=>{
      const input=$('input[name="consumerInterest"][value="'+CSS.escape(key)+'"]',dialog);
      if(input)input.checked=true;
    });
    dialog.showModal();
  }

  function wireOnboarding(){
    const dialog=$('#consumerOnboarding');
    if(!dialog)return;
    $('#consumerOnboardingSave',dialog)?.addEventListener('click',saveOnboarding);
    $('#consumerOnboardingSkip',dialog)?.addEventListener('click',()=>{
      writePrefs({...readPrefs(),complete:true});
      dialog.close();
    });
    if(view==='hub')setTimeout(()=>openOnboarding(false),700);
  }

  function selectedRegion(){
    return readPrefs().region.toLowerCase();
  }

  function regionMatches(item,region){
    if(!region)return false;
    const hay=[item.location,item.name].filter(Boolean).join(' ').toLowerCase();
    const cleaned=String(region||'').toLowerCase().replace(/\b(western|eastern|northern|southern|central|greater)\b/g,' ').replace(/[^a-z0-9]+/g,' ').trim();
    const aliases={
      pa:'pennsylvania',oh:'ohio',wv:'west virginia',ny:'new york',nj:'new jersey',
      md:'maryland',va:'virginia',nc:'north carolina',sc:'south carolina',
      tn:'tennessee',ga:'georgia',fl:'florida',tx:'texas',ca:'california',
      in:'indiana',il:'illinois',mi:'michigan',wi:'wisconsin',mn:'minnesota',
      ia:'iowa',mo:'missouri',ks:'kansas',ok:'oklahoma',ne:'nebraska'
    };
    const tokens=cleaned.split(/\s+/).filter(Boolean);
    const candidates=new Set([cleaned]);
    tokens.forEach(token=>{
      candidates.add(token);
      if(aliases[token])candidates.add(aliases[token]);
    });
    return [...candidates].some(value=>value.length>=2&&hay.includes(value));
  }

  async function renderConsumerHome(){
    if(view!=='hub')return;
    const today=$('#consumerTodayGrid');
    const following=$('#consumerFollowingGrid');
    const local=$('#consumerLocalGrid');
    const results=$('#consumerResultsGrid');
    if(!today||!following||!local||!results)return;

    try{
      const [data,raceDayData]=await Promise.all([
        graph(),
        raceDay().catch(()=>({live:[],upcoming:[],movement:[]}))
      ]);
      const seriesByKey=new Map((data.series||[]).map(item=>[String(item.series_key||item.key||''),item]));

      const live=(raceDayData.live||[]).slice(0,3);
      const fallbackUpcoming=(data.events||[])
        .filter(item=>['next','schedule'].includes(String(item?.state||'').toLowerCase()))
        .filter(item=>{
          const when=new Date(item?.start||'');
          return Number.isNaN(when.getTime())||when.getTime()>=Date.now()-2*60*60*1000;
        })
        .sort((a,b)=>String(a?.start||'').localeCompare(String(b?.start||'')));
      const upcoming=((raceDayData.upcoming||[]).length?(raceDayData.upcoming||[]):fallbackUpcoming).slice(0,6);
      const todayRows=[
        ...live.map(item=>consumerCard(
          'LIVE NOW',item.name,[item.series_name,item.venue].filter(Boolean).join(' · '),
          '/race-center/event/'+encodeURIComponent(item.key),
          seriesMedia(seriesByKey,item.series_key),
          '<span class="consumer-live-dot">LIVE</span>'
        )),
        ...upcoming.slice(0,Math.max(0,6-live.length)).map(item=>consumerCard(
          'UP NEXT',item.name,[eventWhen(item.start),item.series_name,item.venue].filter(Boolean).join(' · '),
          '/race-center/event/'+encodeURIComponent(item.key),
          seriesMedia(seriesByKey,item.series_key)
        ))
      ];
      today.innerHTML=todayRows.length?todayRows.join(''):emptyState('Quiet right now','No tracked race is live and no future event has loaded yet. Open Live + Next for the full schedule.','/race-center/live','See upcoming races');

      const legacy=legacyPrefs();
      const favoriteSet=new Set(legacy.favorites||[]);
      const driverSet=new Set(legacy.drivers||[]);
      const series=(data.series||[]).filter(item=>favoriteSet.has(String(item.series_key||item.key))).slice(0,5);
      const drivers=(data.drivers||[]).filter(item=>{
        const name=String(item.name||'').trim().toLowerCase();
        return [...driverSet].some(key=>String(key).toLowerCase().endsWith(':'+name));
      }).slice(0,4);
      const followRows=[
        ...series.map(item=>consumerCard(
          'MY SERIES',item.name||item.series_name,'Championship, schedule and drivers',
          '/race-center/series/'+encodeURIComponent(item.series_key||item.key),
          item.logo_url
        )),
        ...drivers.map(item=>consumerCard(
          'MY DRIVER',(item.number?'#'+item.number+' · ':'')+item.name,
          [item.team,(item.series||[])[0]?.series_name].filter(Boolean).join(' · '),
          href('driver',item),
          item.photo_url
        ))
      ];
      following.innerHTML=followRows.length?followRows.join(''):emptyState('Make Race Center yours','Follow a few drivers, series or tracks and this becomes your personal racing front page.','#','Customize My Racing');

      const region=selectedRegion();
      const grassrootsTracks=(data.tracks||[]).filter(item=>item.grassroots||((item.provenance?.source_names||[]).join(' ').toLowerCase().includes('grassroots')));
      const regional=region?grassrootsTracks.filter(item=>regionMatches(item,region)):[];
      const localRows=(region&&regional.length?regional:grassrootsTracks).slice(0,5);
      const localKicker=region&&regional.length?'NEAR YOUR REGION':'GRASSROOTS DISCOVERY';
      const localCards=localRows.map(item=>consumerCard(
        localKicker,item.name,item.location||'Grassroots racing venue',
        '/race-center/track/'+encodeURIComponent(item.key),
        trackMedia(item,seriesByKey)
      ));
      localCards.push(consumerCard(
        'SERIES DIRECTORS','Not in Race Center yet?','Send us your official roster, schedule, standings, results and media.',
        '/submit-series',''
      ));
      local.innerHTML=localCards.length?localCards.join(''):emptyState('Help us map grassroots racing','Series and promoters can submit their official sources directly to Race Center.','/submit-series','Submit your series');

      const resultEvents=(data.events||[]).filter(item=>Array.isArray(item.results)&&item.results.length).sort((a,b)=>new Date(b.start||0)-new Date(a.start||0)).slice(0,6);
      results.innerHTML=resultEvents.length?resultEvents.map(item=>{
        const winner=(item.results||[]).find(row=>String(row.position||'')==='1')||(item.results||[])[0]||{};
        return consumerCard(
          'RESULT',item.name,
          [winner.name||winner.driver?('Winner: '+(winner.name||winner.driver)):'',item.series_name,item.venue].filter(Boolean).join(' · '),
          '/race-center/event/'+encodeURIComponent(item.key),
          seriesMedia(seriesByKey,item.series_key)
        );
      }).join(''):emptyState('Results are filling in','Verified connected results will appear here as Race Center receives them.','/race-center/events','Browse events');

      const regionLabel=$('#consumerRegionLabel');
      if(regionLabel)regionLabel.textContent=readPrefs().region||'Set your region';
    }catch(_error){
      [today,following,local,results].forEach(host=>{if(host)host.innerHTML=emptyState('Race Center is refreshing','The racing graph is updating. Try again in a moment.');});
    }
  }

  function recentSearches(){
    try{
      const rows=JSON.parse(localStorage.getItem(RECENT_SEARCH_KEY)||'[]');
      return Array.isArray(rows)?rows.map(String).filter(Boolean).slice(0,6):[];
    }catch(_error){return [];}
  }

  function rememberSearch(value){
    const q=String(value||'').trim();
    if(q.length<2)return;
    const rows=[q,...recentSearches().filter(item=>item.toLowerCase()!==q.toLowerCase())].slice(0,6);
    try{localStorage.setItem(RECENT_SEARCH_KEY,JSON.stringify(rows));}catch(_error){}
  }

  function renderSearchShortcuts(){
    const input=$('#raceSearchInput');
    const host=$('#raceSearchResults');
    if(!input||!host||String(input.value||'').trim())return;
    const recent=recentSearches();
    const shortcuts=['Sprint cars','Late models','NASCAR','Local racing'];
    host.innerHTML='<div class="consumer-search-shortcuts">'+
      (recent.length?'<section><span>RECENT</span><div>'+recent.map(q=>'<button type="button" data-consumer-search-query="'+esc(q)+'">'+esc(q)+'</button>').join('')+'</div></section>':'')+
      '<section><span>EXPLORE</span><div>'+shortcuts.map(q=>'<button type="button" data-consumer-search-query="'+esc(q)+'">'+esc(q)+'</button>').join('')+'</div></section>'+
      '</div>';
    host.hidden=false;
  }

  function wireSearchUX(){
    const input=$('#raceSearchInput');
    const host=$('#raceSearchResults');
    if(!input||!host)return;
    input.addEventListener('focus',renderSearchShortcuts);
    input.addEventListener('keydown',event=>{
      if(event.key==='Enter')rememberSearch(input.value);
      if(event.key==='Escape'){host.hidden=true;input.blur();}
    });
    host.addEventListener('click',event=>{
      const quick=event.target.closest('[data-consumer-search-query]');
      if(quick){
        event.preventDefault();
        input.value=quick.dataset.consumerSearchQuery||'';
        input.dispatchEvent(new Event('input',{bubbles:true}));
        rememberSearch(input.value);
        input.focus();
        return;
      }
      const result=event.target.closest('.race-search-result');
      if(result)rememberSearch(input.value);
    });
    document.addEventListener('click',event=>{
      if(!event.target.closest('#raceSearchDock')&&!event.target.closest('[data-consumer-action="search"]'))host.hidden=true;
    });
  }

  function wireMobileDock(){
    $$('[data-consumer-action="search"]').forEach(button=>button.addEventListener('click',event=>{
      event.preventDefault();
      const input=$('#raceSearchInput');
      input?.scrollIntoView({behavior:'smooth',block:'center'});
      setTimeout(()=>{input?.focus();renderSearchShortcuts();},280);
    }));
    $$('[data-consumer-action="profile"]').forEach(button=>button.addEventListener('click',event=>{
      event.preventDefault();
      $('#accountButton')?.click();
    }));

    const path=location.pathname.replace(/\/+$/,'')||'/race-center';
    $$('.consumer-mobile-dock a').forEach(link=>{
      const target=String(link.getAttribute('href')||'').replace(/\/+$/,'');
      const active=target&&target===path;
      link.classList.toggle('active',active);
      if(active)link.setAttribute('aria-current','page');
    });
  }

  function wireAlertDeepLink(){
    if(view!=='myracing'||location.hash!=='#alerts')return;
    setTimeout(()=>$('#v7AlertsButton')?.click(),700);
  }

  function enhanceTrustCopy(){
    Array.from(document.querySelectorAll('.loading-card')).forEach(card=>{
      if(card.dataset.consumerEnhanced)return;
      card.dataset.consumerEnhanced='1';
      card.setAttribute('aria-live','polite');
    });
  }

  function wireSeriesSubmission(){
    if(view!=='submitseries')return;
    document.body.classList.add('series-submit-view');
    document.title='Submit Your Series — Pitmark Race Center';
    Array.from(document.querySelectorAll('main > section')).forEach(section=>{section.hidden=!section.classList.contains('series-submit-page');});
    const form=$('#seriesSubmissionForm');
    const message=$('#seriesSubmissionMessage');
    if(!form)return;
    form.addEventListener('submit',async event=>{
      event.preventDefault();
      const button=form.querySelector('button[type="submit"]');
      if(button){button.disabled=true;button.textContent='Submitting…';}
      if(message){message.className='series-submit-message';message.textContent='Sending your series to Pitmark…';}
      const raw=Object.fromEntries(new FormData(form).entries());
      const payload={
        ...raw,
        classes:String(raw.classes||'').split(',').map(value=>value.trim()).filter(Boolean)
      };
      try{
        const response=await fetch('/api/public/race-center/series-submissions',{
          method:'POST',
          credentials:'same-origin',
          headers:{'Content-Type':'application/json',Accept:'application/json'},
          body:JSON.stringify(payload)
        });
        const data=await response.json().catch(()=>({}));
        if(!response.ok)throw new Error(data.detail||'Unable to submit this series.');
        form.reset();
        if(message){
          message.className='series-submit-message success';
          message.innerHTML='<strong>Got it.</strong> Submission #'+esc(data.id)+' is in the Pitmark review queue. We’ll verify the sources before anything is published.';
        }
      }catch(error){
        if(message){
          message.className='series-submit-message error';
          message.textContent=error?.message||'Unable to submit this series right now.';
        }
      }finally{
        if(button){button.disabled=false;button.textContent='Submit Series to Race Center';}
      }
    });
  }

  function init(){
    document.body.classList.add('consumer-launch');
    wireOnboarding();
    document.addEventListener('click',event=>{
      const customize=event.target.closest('.consumer-customize');
      if(customize){event.preventDefault();openOnboarding(true);}
    });
    renderConsumerHome();
    wireSeriesSubmission();
    wireSearchUX();
    wireMobileDock();
    wireAlertDeepLink();
    enhanceTrustCopy();
    const observer=new MutationObserver(enhanceTrustCopy);
    observer.observe(document.body,{childList:true,subtree:true});
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});
  else init();
})();