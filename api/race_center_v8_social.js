(function(){
'use strict';
var view=String(document.body.dataset.view||'hub');
var $=function(s,r){return (r||document).querySelector(s);};
var $$=function(s,r){return Array.from((r||document).querySelectorAll(s));};
var esc=function(v){return String(v==null?'':v).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});};
function initials(v){return String(v||'RC').split(/\s+/).filter(Boolean).map(function(p){return p.charAt(0);}).join('').slice(0,2).toUpperCase()||'RC';}
function json(url,options){
  options=options||{};
  return fetch(url,Object.assign({credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json'}},options)).then(function(r){
    if(!r.ok)return r.json().catch(function(){return {};}).then(function(p){throw new Error(p.detail||'Race Center request failed');});
    return r.json();
  });
}
function me(){
  if(window.__pitmarkRaceAccountData)return Promise.resolve(window.__pitmarkRaceAccountData);
  if(window.__pitmarkRaceAccountPromise)return window.__pitmarkRaceAccountPromise;
  window.__pitmarkRaceAccountPromise=json('/api/public/race-center/account').then(function(d){window.__pitmarkRaceAccountData=d;return d;}).catch(function(){return {authenticated:false};}).finally(function(){delete window.__pitmarkRaceAccountPromise;});
  return window.__pitmarkRaceAccountPromise;
}
function searchPeople(q,limit){
  return json('/api/public/race-center/community-search?q='+encodeURIComponent(String(q||''))+'&limit='+(limit||24));
}
function avatar(person){
  var src=String(person.photo_url||'').trim();
  return '<span class="v8-person-avatar"><span>'+esc(initials(person.display_name||person.handle))+'</span>'+(src?'<img src="'+esc(src)+'" alt="" loading="lazy" decoding="async" onerror="this.remove()">':'')+'</span>';
}
function role(person){
  var identity=person.identity||{},staff=person.staff||{};
  return staff.label||identity.official_label||identity.account_type||'fan';
}
function card(person){
  return '<article class="v8-person-card" data-person-id="'+esc(person.id)+'">'+
    '<a class="v8-person-main" href="/race-center/u/'+encodeURIComponent(String(person.handle||''))+'">'+
      avatar(person)+
      '<span class="v8-person-copy"><small>'+esc(String(role(person)).toUpperCase())+'</small><strong>'+esc(person.display_name||person.handle||'Race Center member')+'</strong><em>@'+esc(person.handle||'')+'</em><p>'+esc(person.bio||person.favorite_track||'Race Center member')+'</p></span>'+
    '</a>'+
    '<footer><span>'+String(person.followers||0)+' follower'+(Number(person.followers||0)===1?'':'s')+'</span><button class="v8-follow-button'+(person.viewer_follows?' is-following':'')+'" type="button" data-user-id="'+esc(person.id)+'" data-following="'+(person.viewer_follows?'1':'0')+'">'+(person.viewer_follows?'Following':'Follow')+'</button></footer>'+
  '</article>';
}
function wireFollow(root){
  $$('.v8-follow-button',root||document).forEach(function(button){
    if(button.dataset.v8Wired==='1')return;
    button.dataset.v8Wired='1';
    button.addEventListener('click',function(event){
      event.preventDefault();event.stopPropagation();
      me().then(function(account){
        if(!account.authenticated){
          var opener=$('#accountButton');
          if(opener)opener.click();
          return;
        }
        var following=button.dataset.following==='1';
        button.disabled=true;
        return json('/api/public/race-center/people/follow',{
          method:following?'DELETE':'PUT',
          headers:{'Content-Type':'application/json',Accept:'application/json'},
          body:JSON.stringify({user_id:Number(button.dataset.userId)})
        }).then(function(){
          button.dataset.following=following?'0':'1';
          button.textContent=following?'Follow':'Following';
          button.classList.toggle('is-following',!following);
        }).catch(function(){}).finally(function(){button.disabled=false;});
      });
    });
  });
}
function ownerUpdatesPreview(){
  if(view!=='hub'||$('#v8OwnerUpdates'))return;
  var expansion=$('.v8-home-expansion');if(!expansion)return;
  var section=document.createElement('section');
  section.className='v8-community-preview content-section';
  section.id='v8OwnerUpdates';
  section.innerHTML='<div class="section-head"><div><span class="eyebrow">FROM YOUR RACING</span><h2>Trackside updates</h2></div><a class="section-link" href="/race-center/my-racing">My Racing →</a></div><div class="v8-story-grid" id="v8OwnerUpdatesGrid"><div class="loading-card">Loading updates from racers you follow…</div></div>';
  expansion.appendChild(section);
  me().then(function(account){
    if(!account.authenticated){
      $('#v8OwnerUpdatesGrid').innerHTML='<div class="v8-empty"><strong>Follow racers to build this feed.</strong><span>Sign in, follow drivers and teams, and their owner-posted updates will show up here.</span><button class="button primary" type="button" data-v8-open-account>Open My Race Center</button></div>';
      return;
    }
    return json('/api/public/race-center/following-updates?limit=12').then(function(payload){
      var rows=payload.updates||[],host=$('#v8OwnerUpdatesGrid');
      host.innerHTML=rows.length?rows.map(function(x){
        return '<article class="v8-person-card"><div class="v8-person-main"><span class="v8-person-copy"><small>'+esc(String(x.entity_type||'racing').toUpperCase())+'</small><strong>'+esc(x.entity_name||'Racer')+'</strong><p>'+esc(x.body||'')+'</p>'+(x.media_url?'<img src="'+esc(x.media_url)+'" alt="" loading="lazy" decoding="async" class="rc-follow-update-image">':'')+'</span></div></article>';
      }).join(''):'<div class="v8-empty"><strong>No new trackside updates yet.</strong><span>When drivers and teams you follow post from their verified profiles, they’ll appear here.</span></div>';
    });
  }).catch(function(){var host=$('#v8OwnerUpdatesGrid');if(host)host.innerHTML='<div class="v8-empty"><strong>Updates are refreshing.</strong></div>';});
}

function ensureHomePreview(){
  if(view!=='hub'||$('#v8CommunityPreview'))return;
  var expansion=$('.v8-home-expansion');
  var anchor=$('#v7RaceDay');
  var section=document.createElement('section');
  section.className='v8-community-preview content-section';
  section.id='v8CommunityPreview';
  section.innerHTML='<div class="section-head"><div><span class="eyebrow">RACE CENTER COMMUNITY</span><h2>Find people, not just data</h2></div><a class="section-link" href="/race-center/community">Open community →</a></div><div class="v8-people-grid" id="v8PeoplePreview"><div class="loading-card">Finding Race Center profiles…</div></div>';
  if(expansion)expansion.appendChild(section);
  else if(anchor)anchor.parentNode.insertBefore(section,anchor);
}
function renderHomePreview(){
  var host=$('#v8PeoplePreview');if(!host)return;
  searchPeople('',8).then(function(payload){
    var rows=payload.people||[];
    host.innerHTML=rows.length?rows.map(card).join(''):'<div class="v8-empty"><strong>The community starts with the first few racers.</strong><span>Create a Race Center profile and become discoverable here.</span><button class="button primary" type="button" data-v8-open-account>Open My Race Center</button></div>';
    wireFollow(host);
  }).catch(function(){host.innerHTML='<div class="v8-empty"><strong>Community profiles are refreshing.</strong></div>';});
}
function communityPage(){
  if(view!=='community')return;
  var main=$('main');if(!main)return;
  var section=document.createElement('section');
  section.className='v8-community-page content-section';
  section.id='v8CommunityPage';
  section.innerHTML='<div class="v8-community-hero"><div><span class="eyebrow">RACE CENTER COMMUNITY</span><h1>Find the people in racing.</h1><p>Drivers, teams, tracks, series, media and fans can all have an identity here. Search profiles, follow people, and connect the racing data back to the humans.</p></div><a class="button" href="/race-center">Back to Race Center</a></div>'+
    '<label class="v8-community-search"><span>Search profiles</span><div><b>⌕</b><input id="v8CommunitySearch" type="search" autocomplete="off" placeholder="Name, handle, role, home track…"></div></label>'+
    '<div class="v8-community-meta" id="v8CommunityMeta">Loading Race Center profiles…</div>'+
    '<div class="v8-people-grid v8-community-grid" id="v8CommunityGrid"><div class="loading-card">Loading profiles…</div></div>';
  main.appendChild(section);
  var input=$('#v8CommunitySearch'),timer=null;
  function load(){
    var q=String(input.value||'').trim(),host=$('#v8CommunityGrid');
    searchPeople(q,48).then(function(payload){
      var rows=payload.people||[];
      $('#v8CommunityMeta').textContent=rows.length+(rows.length===1?' profile':' profiles')+(q?' matching “'+q+'”':' to discover');
      host.innerHTML=rows.length?rows.map(card).join(''):'<div class="v8-empty"><strong>No profile matched that search.</strong><span>Try a name, handle, role or home track.</span></div>';
      wireFollow(host);
    }).catch(function(){host.innerHTML='<div class="v8-empty"><strong>Profiles are refreshing.</strong></div>';});
  }
  input.addEventListener('input',function(){clearTimeout(timer);timer=setTimeout(load,180);});
  load();
  document.title='Community — Pitmark Race Center';
}
function wireOpeners(){
  document.addEventListener('click',function(event){
    var button=event.target.closest('[data-v8-open-account]');
    if(!button)return;
    event.preventDefault();
    var opener=$('#accountButton');if(opener)opener.click();
  });
}
function nav(){
  var header=$('.site-header nav');if(!header)return;
  if(view==='community'){
    $$('a.active',header).forEach(function(a){a.classList.remove('active');a.removeAttribute('aria-current');});
    var link=header.querySelector('a[href="/race-center/community"]');
    if(link){link.classList.add('active');link.setAttribute('aria-current','page');}
  }
}
function init(){
  ensureHomePreview();
  if(view==='hub'){renderHomePreview();ownerUpdatesPreview();}
  communityPage();
  wireOpeners();
  nav();
  new MutationObserver(function(){wireFollow(document);}).observe(document.body,{childList:true,subtree:true});
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();