(function(){
  const $v6=(selector,root=document)=>(root||document).querySelector(selector);
  const escV6=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));

  function initials(value){
    return String(value||'RC').trim().split(/\s+/).map(part=>part[0]||'').join('').slice(0,2).toUpperCase()||'RC';
  }

  function setAvatar(host,profile,display){
    if(!host)return;
    const fallback=initials(display);
    const url=profile&&profile.photo_url?String(profile.photo_url):'';
    host.textContent=fallback;
    host.classList.remove('has-profile-photo');
    if(!url)return;
    const img=new Image();
    img.alt=String(display||'Race Center profile');
    img.loading='lazy';
    img.decoding='async';
    img.onload=function(){
      host.innerHTML='';
      host.appendChild(img);
      host.classList.add('has-profile-photo');
    };
    img.onerror=function(){
      host.textContent=fallback;
      host.classList.remove('has-profile-photo');
    };
    img.src=url+(url.includes('?')?'&':'?')+'v=6';
  }

  function renderAccountIdentity(){
    if(typeof state==='undefined')return;
    const account=state.account||{};
    const profile=account.profile||{};
    const authed=Boolean(account.authenticated);
    const display=authed?(account.display_name||profile.handle||'Racer'):'My Race Center';

    setAvatar($v6('#socialProfileAvatar'),profile,display);
    setAvatar($v6('#composerAvatar'),profile,display);

    const copy=$v6('.social-profile-copy');
    if(copy){
      let badge=$v6('#socialStaffBadge');
      const staff=profile.staff||{};
      if(staff.label){
        if(!badge){
          badge=document.createElement('span');
          badge.id='socialStaffBadge';
          badge.className='social-staff-badge';
          copy.appendChild(badge);
        }
        badge.innerHTML='<img src="/prt-logo.png" alt=""><span><b>'+escV6(staff.label)+'</b><small>'+escV6(staff.title||'Pitmark Racing Co.')+'</small></span>';
        badge.hidden=false;
      }else if(badge){
        badge.hidden=true;
      }
    }
  }

  function seriesRows(){
    try{return typeof seriesDirectoryRows==='function'?seriesDirectoryRows():[];}catch(_error){return [];}
  }

  function driverRows(){
    try{return typeof driverDirectoryRows==='function'?driverDirectoryRows():[];}catch(_error){return [];}
  }

  function scheduleRows(){
    if(typeof state==='undefined')return [];
    return (state.payload&&state.payload.events&&state.payload.events.catalog)||[];
  }

  function searchItems(query){
    const q=String(query||'').trim().toLowerCase();
    if(q.length<2)return [];
    const results=[];

    seriesRows().forEach(series=>{
      const hay=[series.series_name,series.short_name,series.group,series.source_name].filter(Boolean).join(' ').toLowerCase();
      if(!hay.includes(q))return;
      results.push({
        kind:'Series',
        title:series.series_name||series.short_name||'Racing series',
        meta:[series.group,series.entries&&series.entries[0]?'Leader: '+series.entries[0].name:''].filter(Boolean).join(' · '),
        href:'/race-center/series/'+encodeURIComponent(String(series.series_key||'')),
        priority:hay.startsWith(q)?100:70
      });
    });

    driverRows().forEach(driver=>{
      const number=String(driver.number||'');
      const hay=[driver.name,number,'#'+number,driver.team,driver.manufacturer,driver.series_name,driver.series_short].filter(Boolean).join(' ').toLowerCase();
      if(!hay.includes(q))return;
      results.push({
        kind:'Driver',
        title:driver.name||'Driver',
        meta:[number?'#'+number:'',driver.team||driver.manufacturer,driver.series_short||driver.series_name].filter(Boolean).join(' · '),
        href:'/race-center/driver/'+encodeURIComponent(String(driver.series_key||''))+'/'+encodeURIComponent(String(driver.name||'')),
        priority:String(driver.name||'').toLowerCase().startsWith(q)?110:(number&&('#'+number===q||number===q)?105:75)
      });
    });

    scheduleRows().forEach(item=>{
      const event=item.event||{};
      const hay=[item.series_name,item.group,event.name,event.venue,event.location,item.watch_name].filter(Boolean).join(' ').toLowerCase();
      if(!hay.includes(q))return;
      results.push({
        kind:'Event',
        title:event.name||item.series_name||'Race event',
        meta:[item.series_name,event.start&&typeof eventTime==='function'?eventTime(event):''].filter(Boolean).join(' · '),
        href:'/race-center/schedules?search='+encodeURIComponent(q),
        priority:60
      });
    });

    const seen=new Set();
    return results.sort((a,b)=>b.priority-a.priority||a.title.localeCompare(b.title)).filter(item=>{
      const key=item.kind+'|'+item.href+'|'+item.title;
      if(seen.has(key))return false;
      seen.add(key);
      return true;
    }).slice(0,12);
  }

  function renderSearch(){
    const input=$v6('#raceSearchInput');
    const host=$v6('#raceSearchResults');
    if(!input||!host)return;
    const q=String(input.value||'').trim();
    if(q.length<2){
      host.hidden=true;
      host.innerHTML='';
      return;
    }
    const results=searchItems(q);
    host.innerHTML=results.length?results.map(item=>
      '<a class="race-search-result" href="'+escV6(item.href)+'">'+
        '<span class="race-search-kind">'+escV6(item.kind)+'</span>'+
        '<span class="race-search-copy"><strong>'+escV6(item.title)+'</strong><small>'+escV6(item.meta||'Open in Race Center')+'</small></span>'+
        '<b>→</b>'+
      '</a>'
    ).join(''):'<div class="race-search-empty"><strong>No exact match yet.</strong><span>Try a driver surname, car number, series, team, or event.</span></div>';
    host.hidden=false;
  }

  function wireSearch(){
    const input=$v6('#raceSearchInput');
    const host=$v6('#raceSearchResults');
    if(!input||input.dataset.v6Wired==='1')return;
    input.dataset.v6Wired='1';
    input.addEventListener('input',renderSearch);
    input.addEventListener('focus',renderSearch);
    input.addEventListener('keydown',event=>{
      if(event.key==='Escape'){
        input.value='';
        renderSearch();
        input.blur();
      }
      if(event.key==='Enter'){
        const first=$v6('.race-search-result',host);
        if(first){
          event.preventDefault();
          location.href=first.href;
        }
      }
    });
    document.addEventListener('keydown',event=>{
      if(event.key==='/'&&!event.ctrlKey&&!event.metaKey&&!event.altKey){
        const target=event.target;
        const tag=String(target&&target.tagName||'').toLowerCase();
        if(!['input','textarea','select'].includes(tag)&&!target?.isContentEditable){
          event.preventDefault();
          input.focus();
        }
      }
    });
    document.addEventListener('click',event=>{
      if(host&&!host.hidden&&!event.target.closest('#raceSearchDock'))host.hidden=true;
    });
  }

  function enhanceFeedLinks(){
    document.querySelectorAll('.network-object[data-key]').forEach(card=>{
      if(card.dataset.v6Wired==='1')return;
      card.dataset.v6Wired='1';
      card.tabIndex=0;
      const go=()=>{
        const driverHref=String(card.dataset.driverHref||'');
        if(driverHref){
          location.href=driverHref;
          return;
        }
        const key=String(card.dataset.key||'');
        if(key)location.href='/race-center/series/'+encodeURIComponent(key);
      };
      card.addEventListener('click',event=>{
        if(event.target.closest('a,button,input,select,textarea'))return;
        go();
      });
      card.addEventListener('keydown',event=>{
        if(event.key==='Enter'||event.key===' '){event.preventDefault();go();}
      });
    });
  }

  function enhance(){
    renderAccountIdentity();
    wireSearch();
    enhanceFeedLinks();
  }

  function init(){
    try{
      if(typeof render==='function'){
        const baseRender=render;
        render=function(){
          baseRender();
          requestAnimationFrame(enhance);
        };
      }
      if(typeof renderAccount==='function'){
        const baseRenderAccount=renderAccount;
        renderAccount=function(){
          baseRenderAccount();
          requestAnimationFrame(enhance);
        };
      }
    }catch(error){
      console.error('Race Center V6 hooks failed',error);
    }

    const feedObserver=new MutationObserver(()=>enhanceFeedLinks());
    const feed=$v6('#raceFeedList');
    if(feed)feedObserver.observe(feed,{childList:true,subtree:true});

    enhance();
    setTimeout(enhance,250);
    setTimeout(enhance,1200);
    // V5's live/social renderer refreshes independently. Re-apply the V6
    // identity/photo layer so those refreshes can never downgrade the profile UI.
    setInterval(enhance,10000);
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});
  else init();
})();