(()=>{
'use strict';
const handle=decodeURIComponent(document.body.dataset.profileHandle||'').trim().toLowerCase();
const $=selector=>document.querySelector(selector);
const esc=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const initials=value=>String(value||'?').split(/\s+/).filter(Boolean).map(x=>x[0]||'').join('').slice(0,2).toUpperCase()||'?';
const ago=iso=>{
  if(!iso)return '';
  const diff=Math.max(0,Date.now()-new Date(iso).getTime());
  const mins=Math.floor(diff/60000);
  if(mins<1)return 'now';
  if(mins<60)return mins+'m';
  const hrs=Math.floor(mins/60);
  if(hrs<48)return hrs+'h';
  return Math.floor(hrs/24)+'d';
};
const apiJson=async(url,options={})=>{
  const response=await fetch(url,{credentials:'same-origin',...options,headers:{Accept:'application/json',...(options.body instanceof FormData?{}:{'Content-Type':'application/json'}),...(options.headers||{})}});
  let payload={};
  try{payload=await response.json();}catch(_error){}
  if(!response.ok)throw new Error(payload.detail||payload.message||'Request failed');
  return payload;
};

let account={authenticated:false};
let profile=null;
let wall=[];

function roleLabel(value){
  return ({fan:'RACING FAN',driver:'DRIVER',team:'RACE TEAM',series:'SERIES',track:'TRACK',media:'MEDIA / CREATOR'})[String(value||'fan')]||'RACE CENTER PROFILE';
}

function renderAvatar(){
  const host=$('#publicProfileAvatar');
  if(!host||!profile)return;
  host.innerHTML='';
  const img=document.createElement('img');
  const photoUrl=profile.photo_url||'/api/public/race-center/profile-photo/'+encodeURIComponent(profile.handle);
  img.src=photoUrl;
  img.alt=profile.display_name||profile.handle;
  img.onload=()=>{host.classList.add('has-photo');};
  img.onerror=()=>{host.classList.remove('has-photo');host.textContent=initials(profile.display_name||profile.handle);};
  host.appendChild(img);
}

function renderProfile(){
  if(!profile)return;
  const identity=profile.identity||{};
  const owner=Boolean(account.authenticated&&account.profile&&account.profile.handle===profile.handle);
  $('#publicProfileName').textContent=profile.display_name||profile.handle;
  $('#publicProfileHandle').textContent='@'+profile.handle;
  $('#publicProfileRole').textContent=roleLabel(identity.account_type);
  $('#publicProfileBio').textContent=profile.bio||'No bio yet.';
  $('#publicProfileFollowers').textContent=String(profile.followers||0);
  $('#publicProfileFollowing').textContent=String(profile.following||0);
  $('#publicProfileSeries').textContent=String((profile.series||[]).length);
  const staff=profile.staff||{};
  const staffBadge=$('#pitmarkStaffBadge');
  if(staffBadge){
    staffBadge.hidden=!staff.label;
    if(staff.label){
      const title=staff.title||'Pitmark Racing Co.';
      staffBadge.querySelector('b').textContent=staff.label;
      staffBadge.querySelector('small').textContent=title;
      staffBadge.classList.toggle('is-founder',staff.level==='founder');
    }
  }
  const verified=$('#publicProfileVerified');
  verified.hidden=identity.verification_status!=='verified';
  if(!verified.hidden)verified.textContent='✓ '+(identity.official_label||'Verified');
  const meta=[];
  if(profile.favorite_track)meta.push('<span>Home track <strong>'+esc(profile.favorite_track)+'</strong></span>');
  if(profile.mutual_connections)meta.push('<span><strong>'+String(profile.mutual_connections)+'</strong> mutual connection'+(Number(profile.mutual_connections)===1?'':'s')+'</span>');
  if(profile.shared_racing)meta.push('<span><strong>'+String(profile.shared_racing)+'</strong> shared racing interest'+(Number(profile.shared_racing)===1?'':'s')+'</span>');
  if(identity.external_url)meta.push('<a href="'+esc(identity.external_url)+'" target="_blank" rel="noopener">Official link ↗</a>');
  $('#publicProfileMeta').innerHTML=meta.join('');
  $('#profilePhotoUpload').hidden=!owner;
  $('#profileEditButton').hidden=!owner;
  $('#profileWallComposer').hidden=!owner;
  $('#profileWallTitle').textContent=owner?'Your wall':'Latest posts';

  const follow=$('#profileFollowButton');
  follow.hidden=owner;
  if(!owner){
    follow.textContent=profile.viewer_follows?'Following':'Follow';
    follow.classList.toggle('primary',!profile.viewer_follows);
    follow.dataset.following=profile.viewer_follows?'1':'0';
    if(!account.authenticated)follow.textContent='Sign in to follow';
  }

  const seriesItems=(profile.series||[]).map(x=>
    '<a href="/race-center/series/'+encodeURIComponent(String(x.key||''))+'"><b>Series</b><span>'+esc(x.label||x.key)+'</span><em>→</em></a>'
  );
  const driverItems=(profile.drivers||[]).map(x=>{
    const key=String(x.key||'');
    const fallbackName=key.split(':').slice(1).join(':')||key;
    return '<a href="/race-center/driver/'+encodeURIComponent(String(x.series_key||key.split(':')[0]||''))+'/'+encodeURIComponent(String(x.label||fallbackName))+'"><b>Driver</b><span>'+esc(x.label||fallbackName)+'</span><em>→</em></a>';
  });
  const trackItems=(profile.tracks||[]).map(x=>
    '<a href="/race-center/track/'+encodeURIComponent(String(x.key||''))+'"><b>Track</b><span>'+esc(x.label||x.key)+'</span><em>→</em></a>'
  );
  const teamItems=(profile.teams||[]).map(x=>
    '<a href="/race-center/team/'+encodeURIComponent(String(x.key||''))+'"><b>Team</b><span>'+esc(x.label||x.key)+'</span><em>→</em></a>'
  );
  const racing=[...seriesItems,...driverItems,...trackItems,...teamItems];
  $('#profileFollowedRacing').innerHTML=racing.length?racing.join(''):'<div class="loading-card">No racing follows yet.</div>';
  renderAvatar();
}

function renderWall(){
  const host=$('#profileWallFeed');
  if(!host)return;
  host.innerHTML=wall.length?wall.map(post=>'<article class="profile-wall-post">'+
    '<header><div><strong>'+esc(post.author?.display_name||profile?.display_name||'Racer')+'</strong><span>@'+esc(post.author?.handle||profile?.handle||'')+' · '+esc(ago(post.created_at))+'</span></div></header>'+
    '<p>'+esc(post.body).replace(/\n/g,'<br>')+'</p>'+
    '<footer><span>🏁 '+String(post.reactions?.checkered||0)+'</span><span>🔥 '+String(post.reactions?.fire||0)+'</span><span>💬 '+String(post.comment_count||0)+'</span></footer>'+
  '</article>').join(''):'<div class="loading-card">Nothing posted here yet.</div>';
}

async function prepareProfilePhoto(file){
  if(!file||!String(file.type||'').startsWith('image/')){
    throw new Error('Choose a JPG, PNG, WebP, or other browser-readable image.');
  }

  const decode=async()=>{
    if('createImageBitmap' in window){
      try{return await createImageBitmap(file,{imageOrientation:'from-image'});}catch(_error){}
    }
    return await new Promise((resolve,reject)=>{
      const url=URL.createObjectURL(file);
      const img=new Image();
      img.onload=()=>{URL.revokeObjectURL(url);resolve(img);};
      img.onerror=()=>{URL.revokeObjectURL(url);reject(new Error('That photo could not be opened by your browser.'));};
      img.src=url;
    });
  };

  const image=await decode();
  const sourceWidth=Number(image.width||image.naturalWidth||0);
  const sourceHeight=Number(image.height||image.naturalHeight||0);
  if(!sourceWidth||!sourceHeight){
    image.close?.();
    throw new Error('That photo has invalid dimensions.');
  }

  const size=720;
  const crop=Math.min(sourceWidth,sourceHeight);
  const sx=Math.max(0,(sourceWidth-crop)/2);
  const sy=Math.max(0,(sourceHeight-crop)/2);
  const canvas=document.createElement('canvas');
  canvas.width=size;
  canvas.height=size;
  const context=canvas.getContext('2d',{alpha:false});
  if(!context){
    image.close?.();
    throw new Error('Your browser could not prepare this photo.');
  }
  context.drawImage(image,sx,sy,crop,crop,0,0,size,size);
  image.close?.();

  const makeBlob=(type,quality)=>new Promise(resolve=>canvas.toBlob(resolve,type,quality));
  let blob=await makeBlob('image/webp',0.84);
  let extension='webp';
  if(!blob){
    blob=await makeBlob('image/jpeg',0.86);
    extension='jpg';
  }
  if(!blob)throw new Error('Your browser could not resize this photo.');

  // Keep the multipart request comfortably under Race Center's upload cap.
  if(blob.size>1400*1024){
    blob=await makeBlob('image/jpeg',0.72);
    extension='jpg';
  }
  if(!blob||blob.size>1800*1024){
    throw new Error('That image could not be compressed enough. Try another photo.');
  }

  const base=String(file.name||'profile-photo').replace(/\.[^.]+$/,'').replace(/[^a-z0-9_-]+/gi,'-').slice(0,60)||'profile-photo';
  return new File([blob],base+'.'+extension,{type:blob.type||'image/jpeg'});
}


function prtLapTime(seconds){
  const value=Number(seconds||0);
  if(!Number.isFinite(value)||value<=0)return '—';
  const minutes=Math.floor(value/60);
  const remaining=(value%60).toFixed(3).padStart(6,'0');
  return minutes>0 ? minutes+':'+remaining : remaining+'s';
}

function prtMetric(label,value){
  const card=document.createElement('div');
  card.className='prt-metric';
  const figure=document.createElement('strong');
  figure.textContent=String(value);
  const title=document.createElement('span');
  title.textContent=label;
  card.append(figure,title);
  return card;
}

async function renderPrtOwnerDashboard(){
  const panel=$('#profilePrtPrivateStats');
  const status=$('#profilePrtStatus');
  const metricHost=$('#profilePrtPrivateSummary');
  const recentHost=$('#profilePrtRecentRaces');
  if(!panel||!status||!metricHost||!recentHost)return;
  panel.hidden=false;
  status.textContent='Loading your private PRT race history…';
  metricHost.replaceChildren();
  recentHost.replaceChildren();
  try{
    const [summary,history]=await Promise.all([
      apiJson('/api/public/race-center/prt/my-summary'),
      apiJson('/api/public/race-center/prt/my-sessions')
    ]);
    if(summary.private!==true||history.visibility!=='private')
      throw new Error('The server did not confirm private access to these records.');
    const devices=Number(summary.connected_devices||0);
    const total=Number(summary.sessions||0);
    const dot=document.createElement('span');
    dot.className='prt-status-dot'+(devices>0?' online':'');
    dot.setAttribute('aria-hidden','true');
    const statusText=document.createElement('span');
    statusText.textContent=(devices>0
      ? devices+' connected PRT computer'+(devices===1?'':'s')
      : 'No connected PRT computers')+' · '+total+' private race'+(total===1?'':'s')+' imported';
    status.replaceChildren(dot,statusText);

    const grid=document.createElement('div');
    grid.className='prt-metrics';
    const stats=[
      ['Imported races',total.toLocaleString()],
      ['Laps completed',Number(summary.laps||0).toLocaleString()],
      ['Wins',Number(summary.wins||0).toLocaleString()],
      ['Top-5 finishes',Number(summary.top_fives||0).toLocaleString()],
      ['Fastest recorded lap',prtLapTime(summary.best_lap)],
      ['Connected computers',devices.toLocaleString()]
    ];
    stats.forEach(([label,value])=>grid.appendChild(prtMetric(label,value)));
    metricHost.appendChild(grid);

    const records=Array.isArray(history.sessions)?history.sessions.slice():[];
    records.sort((a,b)=>{
      const left=Date.parse(String(a.date||'')),right=Date.parse(String(b.date||''));
      return (Number.isFinite(right)?right:0)-(Number.isFinite(left)?left:0);
    });
    if(records.length===0){
      const empty=document.createElement('div');
      empty.className='prt-empty';
      const heading=document.createElement('strong');
      heading.textContent='Your Race Center profile is ready. Now bring in your races.';
      const p=document.createElement('p');
      p.textContent=devices>0
        ? 'Pairing a computer only grants access. Open PRT → Profile → Sync Now to upload completed race history. Enable Auto-sync there to keep new races coming in.'
        : 'Open PRT → Profile → Connect to Race Center. Approve your computer, then choose Sync Now to upload completed race history.';
      empty.append(heading,p);
      recentHost.appendChild(empty);
    }else{
      const table=document.createElement('table');
      const thead=document.createElement('thead');
      const hr=document.createElement('tr');
      ['Date','Track / Car','Finish','Laps','Incidents'].forEach(value=>{
        const th=document.createElement('th');th.scope='col';th.textContent=value;hr.appendChild(th);
      });
      thead.appendChild(hr);
      const tbody=document.createElement('tbody');
      records.slice(0,15).forEach(race=>{
        const tr=document.createElement('tr');
        const dt=new Date(race.date||'');
        const dateCell=document.createElement('td');
        dateCell.textContent=Number.isNaN(dt.getTime())?'—':dt.toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric'});
        const trackCell=document.createElement('td');
        trackCell.textContent=String(race.track||'Unknown track');
        const sub=document.createElement('small');
        sub.textContent=[race.car,race.series].filter(Boolean).join(' · ')||'Car not recorded';
        trackCell.appendChild(sub);
        const finishCell=document.createElement('td');
        finishCell.textContent=Number(race.finishing_position)>0?'P'+race.finishing_position:'—';
        const lapsCell=document.createElement('td');lapsCell.textContent=String(Number(race.laps)||0);
        const incidentCell=document.createElement('td');incidentCell.textContent=String(Number(race.incidents)||0);
        tr.append(dateCell,trackCell,finishCell,lapsCell,incidentCell);
        tbody.appendChild(tr);
      });
      table.append(thead,tbody);
      recentHost.appendChild(table);
    }
    if(location.hash==='#prt-history')requestAnimationFrame(()=>panel.scrollIntoView({block:'start'}));
  }catch(error){
    status.textContent='PRT racing history is temporarily unavailable.';
    const errorBox=document.createElement('div');
    errorBox.className='prt-empty';
    const p=document.createElement('p');
    p.textContent=error.message||'Please refresh and try again.';
    errorBox.appendChild(p);
    recentHost.appendChild(errorBox);
  }
}


function prtFormatDate(value){
  const d=new Date(String(value||''));
  return Number.isNaN(d.getTime())?'—':d.toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric'});
}

function prtRenderRaceRows(records,append=false){
  const host=$('#profilePrtRecentRaces');
  if(!host)return;
  let table=host.querySelector('table');
  if(!table||!append){
    host.replaceChildren();
    table=document.createElement('table');
    const head=document.createElement('thead');
    const row=document.createElement('tr');
    ['Date','Track / Car','Start','Finish','Laps','Best lap','Incidents'].forEach(text=>{
      const th=document.createElement('th');th.scope='col';th.textContent=text;row.appendChild(th);
    });
    head.appendChild(row);
    table.append(head,document.createElement('tbody'));
    host.appendChild(table);
  }
  const body=table.querySelector('tbody');
  (records||[]).forEach(race=>{
    const row=document.createElement('tr');
    const date=document.createElement('td');date.textContent=prtFormatDate(race.date);
    const car=document.createElement('td');
    car.textContent=String(race.track||'Unknown track');
    const sub=document.createElement('small');
    sub.textContent=[race.car,race.series].filter(Boolean).join(' · ')||'Car not recorded';
    car.appendChild(sub);
    const start=document.createElement('td');start.textContent=Number(race.starting_position)>0?'P'+race.starting_position:'—';
    const finish=document.createElement('td');finish.textContent=Number(race.finishing_position)>0?'P'+race.finishing_position:'—';
    const laps=document.createElement('td');laps.textContent=String(Number(race.laps)||0);
    const best=document.createElement('td');best.textContent=prtLapTime(race.best_lap);
    const incidents=document.createElement('td');incidents.textContent=String(Number(race.incidents)||0);
    row.append(date,car,start,finish,laps,best,incidents);
    body.appendChild(row);
  });
}

async function renderPrtVisitorDashboard(){
  const panel=$('#profilePrtPrivateStats');
  const status=$('#profilePrtStatus');
  const metrics=$('#profilePrtPrivateSummary');
  const races=$('#profilePrtRecentRaces');
  const more=$('#prtLoadMoreSlot');
  if(!panel||!status||!metrics||!races||!more||!profile)return;
  panel.hidden=true;
  try{
    const endpoint='/api/public/race-center/prt/public/'+encodeURIComponent(profile.handle);
    const first=await apiJson(endpoint+'?limit=25&offset=0');
    if(!first.public)return;
    panel.hidden=false;
    $('#prtHistoryHeading').textContent='PRT racing history';
    $('#prtHistoryDescription').textContent='Recorded iRacing results and performance shared by this driver.';
    $('#prtPrivacyPill').textContent='Shared by driver';
    $('#prtPrivacyPill').classList.add('is-public');
    $('#prtPublicSharingControls').hidden=true;
    $('#prtOwnerActions').hidden=true;
    const summary=first.summary||{};
    status.textContent=Number(summary.sessions||0).toLocaleString()+' races shared from PRT';
    const grid=document.createElement('div');grid.className='prt-metrics';
    const items=[
      ['Races',Number(summary.sessions||0).toLocaleString()],
      ['Laps completed',Number(summary.laps||0).toLocaleString()],
      ['Wins',Number(summary.wins||0).toLocaleString()],
      ['Top-5 finishes',Number(summary.top_fives||0).toLocaleString()],
      ['Fastest recorded lap',prtLapTime(summary.best_lap)]
    ];
    items.forEach(([title,value])=>grid.appendChild(prtMetric(title,value)));
    metrics.replaceChildren(grid);
    if(!Number(summary.sessions||0)){
      races.replaceChildren();
      const empty=document.createElement('div');empty.className='prt-empty';
      empty.textContent='This driver has shared their profile, but has not imported racing results yet.';
      races.appendChild(empty);return;
    }
    prtRenderRaceRows(first.sessions,false);
    let next=first.next_offset;
    const addMore=()=>{
      more.replaceChildren();
      if(next===null||next===undefined)return;
      const button=document.createElement('button');
      button.type='button';button.className='prt-load-more';
      button.textContent='Load more races';
      more.appendChild(button);
      button.addEventListener('click',async()=>{
        button.disabled=true;button.textContent='Loading…';
        try{
          const batch=await apiJson(endpoint+'?limit=25&offset='+encodeURIComponent(String(next)));
          if(!batch.public){
            panel.hidden=true;more.replaceChildren();return;
          }
          prtRenderRaceRows(batch.sessions,true);
          next=batch.next_offset;
          addMore();
        }catch(error){
          button.disabled=false;button.textContent='Try loading again';
        }
      });
    };
    addMore();
  }catch(error){
    // Keep private by default on authorization or network problems.
    panel.hidden=true;
  }
}

async function prtOwnerSharingControls(){
  const controls=$('#prtPublicSharingControls');
  const input=$('#prtPublicSharingChoice');
  const save=$('#prtSaveSharing');
  const message=$('#prtSharingFeedback');
  const pill=$('#prtPrivacyPill');
  if(!controls||!input||!save||!message||!pill)return;
  controls.hidden=false;
  try{
    const data=await apiJson('/api/public/race-center/prt/sharing');
    input.checked=Boolean(data.public);
    pill.textContent=data.public?'Public racing history':'Private to you';
    pill.classList.toggle('is-public',Boolean(data.public));
  }catch(error){
    controls.hidden=true;
    return;
  }
  save.addEventListener('click',async()=>{
    const wasDisabled=save.disabled;
    if(wasDisabled)return;
    save.disabled=true;
    message.textContent='Updating racing-history visibility…';
    message.classList.remove('error');
    try{
      const result=await apiJson('/api/public/race-center/prt/sharing',{
        method:'PUT',body:JSON.stringify({public:Boolean(input.checked)})
      });
      pill.textContent=result.public?'Public racing history':'Private to you';
      pill.classList.toggle('is-public',Boolean(result.public));
      message.textContent=result.public?
        'Your imported races and lap times are now visible to Race Center visitors.':
        'Your imported race history is now private.';
    }catch(error){
      message.textContent=error.message||'Visibility update failed.';
      message.classList.add('error');
    }finally{save.disabled=false;}
  });
}

async function load(){
  try{
    [account,profile]=await Promise.all([
      apiJson('/api/public/race-center/account'),
      apiJson('/api/public/race-center/people/'+encodeURIComponent(handle))
    ]);
    const wallPayload=await apiJson('/api/public/race-center/profile-wall/'+encodeURIComponent(handle));
    wall=wallPayload.posts||[];
    renderProfile();
    renderWall();
    const ownPrt = Boolean(account.authenticated && account.profile && account.profile.handle === profile.handle);
    const box=$('#profilePrtPrivateStats');
    if(box)box.hidden=!ownPrt;
    if(ownPrt){
      await renderPrtOwnerDashboard();
      await prtOwnerSharingControls();
    }else{
      await renderPrtVisitorDashboard();
    }
    $('#profileAccountButton').textContent=account.authenticated?'My Profile':'Sign in';
    $('#profileAccountButton').href=account.authenticated?'/race-center/me':'/race-center?account=1';
    document.title=(profile.display_name||profile.handle)+' — Pitmark Race Center';
  }catch(error){
    $('#publicProfileName').textContent='Profile unavailable';
    $('#publicProfileBio').textContent=error.message||'This Race Center profile could not be loaded.';
    $('#profileFollowedRacing').innerHTML='';
    $('#profileWallFeed').innerHTML='';
  }
}

$('#profilePhotoInput')?.addEventListener('change',async event=>{
  const file=event.target.files&&event.target.files[0];
  if(!file)return;
  const label=$('#profilePhotoUpload span');
  label.textContent='Preparing photo…';
  try{
    const prepared=await prepareProfilePhoto(file);
    label.textContent='Uploading…';
    const data=new FormData();
    data.append('photo',prepared,prepared.name);
    const result=await apiJson('/api/public/race-center/profile/photo',{method:'PUT',body:data});
    if(result.photo_url)profile.photo_url=result.photo_url;
    renderAvatar();
    label.textContent='Change photo';
  }catch(error){
    label.textContent=error.message||'Upload failed';
    setTimeout(()=>{label.textContent='Change photo';},3200);
  }finally{
    event.target.value='';
  }
});

$('#profileFollowButton')?.addEventListener('click',async()=>{
  if(!account.authenticated){location.href='/race-center?account=1';return;}
  if(!profile)return;
  const button=$('#profileFollowButton');
  if(button.disabled)return;
  const following=button.dataset.following==='1';
  const status=$('#profileFollowFeedback');
  button.disabled=true;
  if(status)status.textContent=following?'Unfollowing…':'Following…';
  try{
    await apiJson('/api/public/race-center/people/follow',{
      method:following?'DELETE':'PUT',
      body:JSON.stringify({user_id:profile.id})
    });
    // Refresh from the server rather than guessing the updated count.
    profile=await apiJson('/api/public/race-center/people/'+encodeURIComponent(handle));
    renderProfile();
    if(status)status.textContent=following?'Unfollowed.':'Following.';
  }catch(error){
    if(status)status.textContent=error.message||'Could not update follow. Try again.';
  }finally{
    button.disabled=false;
  }
});

$('#profilePostInput')?.addEventListener('input',event=>{
  $('#profilePostCount').textContent=String(event.target.value.length)+' / 600';
});
$('#profilePostButton')?.addEventListener('click',async()=>{
  const input=$('#profilePostInput');
  const body=String(input.value||'').trim();
  if(!body)return;
  const button=$('#profilePostButton');
  button.disabled=true;
  try{
    const payload=await apiJson('/api/public/race-center/feed',{method:'POST',body:JSON.stringify({body,series_key:'',driver_key:''})});
    input.value='';
    $('#profilePostCount').textContent='0 / 600';
    const wallPayload=await apiJson('/api/public/race-center/profile-wall/'+encodeURIComponent(handle));
    wall=wallPayload.posts||[];
    renderWall();
  }catch(_error){}finally{button.disabled=false;}
});

load();
})();
