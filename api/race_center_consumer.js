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
    return getJson('/api/public/race-center/graph?v=consumer-launch')
      .then(data=>{graphCache=data;return data;});
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

  function consumerCard(kicker,title,body,url,extra=''){
    return '<a class="consumer-card" href="'+esc(url||'#')+'">'+
      '<span class="consumer-kicker">'+esc(kicker)+'</span>'+
      '<strong>'+esc(title||'Racing')+'</strong>'+
      '<p>'+esc(body||'')+'</p>'+extra+
      '<b>Open →</b></a>';
  }

  function emptyState(title,body,actionHref='',action=''){
    return '<div class="consumer-empty"><span class="consumer-empty-mark">P</span><div><strong>'+esc(title)+'</strong><p>'+esc(body)+'</p>'+
      (actionHref?'<a class="button" href="'+esc(actionHref)+'">'+esc(action||'Explore racing')+'</a>':'')+
      '</div></div>';
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
      const candidates=(data.series||[]).filter(series=>interests.some(interest=>interestMatches(series,interest)));
      candidates.slice(0,8).forEach(series=>{
        const key=String(series.series_key||series.key||'').trim();
        if(key)current.add(key);
      });
      writeLegacyPrefs({...legacy,favorites:[...current]});
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
    $$('.consumer-customize').forEach(button=>button.addEventListener('click',event=>{
      event.preventDefault();
      openOnboarding(true);
    }));
    if(view==='hub')setTimeout(()=>openOnboarding(false),700);
  }

  function selectedRegion(){
    return readPrefs().region.toLowerCase();
  }

  function regionMatches(item,region){
    if(!region)return false;
    return [item.location,item.name].filter(Boolean).join(' ').toLowerCase().includes(region);
  }

  async function renderConsumerHome(){
    if(view!=='hub')return;
    const today=$('#consumerTodayGrid');
    const following=$('#consumerFollowingGrid');
    const local=$('#consumerLocalGrid');
    const results=$('#consumerResultsGrid');
    if(!today||!following||!local||!results)return;

    try{
      const [data,raceDay]=await Promise.all([
        graph(),
        getJson('/api/public/race-center/race-day?v=consumer-launch').catch(()=>({live:[],upcoming:[],movement:[]}))
      ]);

      const live=(raceDay.live||[]).slice(0,3);
      const upcoming=(raceDay.upcoming||[]).slice(0,5);
      const todayRows=[
        ...live.map(item=>consumerCard('LIVE NOW',item.name,[item.series_name,item.venue].filter(Boolean).join(' · '),'/race-center/event/'+encodeURIComponent(item.key),'<span class="consumer-live-dot">LIVE</span>')),
        ...upcoming.slice(0,Math.max(0,6-live.length)).map(item=>consumerCard('UP NEXT',item.name,[eventWhen(item.start),item.series_name,item.venue].filter(Boolean).join(' · '),'/race-center/event/'+encodeURIComponent(item.key)))
      ];
      today.innerHTML=todayRows.length?todayRows.join(''):emptyState('Quiet right now','No tracked race is currently live. Open Live + Next to see what is coming up.','/race-center/live','See upcoming races');

      const legacy=legacyPrefs();
      const favoriteSet=new Set(legacy.favorites||[]);
      const driverSet=new Set(legacy.drivers||[]);
      const series=(data.series||[]).filter(item=>favoriteSet.has(String(item.series_key||item.key))).slice(0,5);
      const drivers=(data.drivers||[]).filter(item=>{
        const name=String(item.name||'').trim().toLowerCase();
        return [...driverSet].some(key=>String(key).toLowerCase().endsWith(':'+name));
      }).slice(0,4);
      const followRows=[
        ...series.map(item=>consumerCard('MY SERIES',item.name||item.series_name,'Championship, schedule and drivers','/race-center/series/'+encodeURIComponent(item.series_key||item.key))),
        ...drivers.map(item=>consumerCard('MY DRIVER',(item.number?'#'+item.number+' · ':'')+item.name,[item.team,(item.series||[])[0]?.series_name].filter(Boolean).join(' · '),href('driver',item)))
      ];
      following.innerHTML=followRows.length?followRows.join(''):emptyState('Make Race Center yours','Follow a few drivers, series or tracks and this becomes your personal racing front page.','#','Customize My Racing');

      const region=selectedRegion();
      const grassrootsTracks=(data.tracks||[]).filter(item=>item.grassroots||((item.provenance?.source_names||[]).join(' ').toLowerCase().includes('grassroots')));
      const localMatches=region?grassrootsTracks.filter(item=>regionMatches(item,region)):grassrootsTracks.slice(0,6);
      local.innerHTML=(localMatches.slice(0,6).map(item=>consumerCard(region?'NEAR YOUR REGION':'GRASSROOTS',item.name,item.location||'Grassroots racing venue','/race-center/track/'+encodeURIComponent(item.key))).join(''))||
        emptyState(region?'No regional match yet':'Set your racing region',region?'We are still expanding local track coverage for '+readPrefs().region+'.':'Tell Race Center your state, province or region and local tracks will surface here.','#','Set region');

      const resultEvents=(data.events||[]).filter(item=>Array.isArray(item.results)&&item.results.length).sort((a,b)=>new Date(b.start||0)-new Date(a.start||0)).slice(0,6);
      results.innerHTML=resultEvents.length?resultEvents.map(item=>{
        const winner=(item.results||[]).find(row=>String(row.position||'')==='1')||(item.results||[])[0]||{};
        return consumerCard('RESULT',item.name,[winner.name||winner.driver?('Winner: '+(winner.name||winner.driver)):'',item.series_name,item.venue].filter(Boolean).join(' · '),'/race-center/event/'+encodeURIComponent(item.key));
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
    $$('.loading-card').forEach(card=>{
      if(card.dataset.consumerEnhanced)return;
      card.dataset.consumerEnhanced='1';
      card.setAttribute('aria-live','polite');
    });
  }

  function init(){
    document.body.classList.add('consumer-launch');
    wireOnboarding();
    renderConsumerHome();
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