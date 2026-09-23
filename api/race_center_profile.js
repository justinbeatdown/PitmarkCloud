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
  img.src=photoUrl+(photoUrl.includes('?')?'&':'?')+'v='+Date.now();
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
    $('#profileAccountButton').textContent=account.authenticated?(account.display_name||account.email||'My Race Center'):'My Race Center';
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
  if(!account.authenticated){location.href='/race-center';return;}
  if(!profile)return;
  const following=$('#profileFollowButton').dataset.following==='1';
  try{
    const payload=await apiJson('/api/public/race-center/people/follow',{method:following?'DELETE':'POST',body:JSON.stringify({user_id:profile.id})});
    profile.viewer_follows=!following;
    profile.followers=Math.max(0,Number(profile.followers||0)+(following?-1:1));
    renderProfile();
  }catch(_error){}
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
