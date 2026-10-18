(() => {
'use strict';
const $=id=>document.getElementById(id);
const api=async(path,options={})=>{
  const response=await fetch(path,{credentials:'same-origin',cache:'no-store',
    ...options,headers:{Accept:'application/json',...(options.body instanceof FormData?{}:
      options.body?{'Content-Type':'application/json'}:{}),...(options.headers||{})}});
  const payload=await response.json().catch(()=>({}));
  if(!response.ok)throw new Error(typeof payload.detail==='string'?payload.detail:'Race Center request failed.');
  return payload;
};
const base='/api/public/race-center';
let me={authenticated:false,follows:[]},mode='following',currentPosts=[],nextOffset=null,requestGeneration=0,reportTarget=null,notificationPoll=null;
const make=(tag,cls,text)=>{
  const e=document.createElement(tag);
  if(cls)e.className=cls;
  if(text!==undefined)e.textContent=String(text);
  return e;
};
function initials(name){return String(name||'R').split(/\s+/).filter(Boolean).slice(0,2).map(x=>x[0]).join('').toUpperCase();}
function avatar(person){
  const wrapper=make('span','rc-avatar',initials(person?.name||person?.display_name||'Racer'));
  const handle=String(person?.handle||'');
  if(handle){
    const img=make('img');
    img.alt='';img.loading='eager';
    img.addEventListener('load',()=>{if(img.naturalWidth)wrapper.classList.add('has-photo');});
    img.addEventListener('error',()=>img.remove());
    wrapper.appendChild(img);
    img.src=base+'/profile-photo/'+encodeURIComponent(handle);
  }
  return wrapper;
}
function authorLink(person){
  const a=make('a','rc-author');
  a.href='/race-center/u/'+encodeURIComponent(String(person?.handle||''));
  a.append(avatar(person),make('span','rc-author-name',person?.display_name||person?.name||person?.handle||'Race Center member'));
  const handle=make('small','', '@'+String(person?.handle||''));
  a.lastChild.appendChild(handle);
  return a;
}
function timeAgo(date){
  const t=new Date(date).getTime();
  if(!Number.isFinite(t))return '';
  const seconds=Math.max(0,Math.floor((Date.now()-t)/1000));
  if(seconds<60)return 'just now';
  if(seconds<3600)return Math.floor(seconds/60)+'m ago';
  if(seconds<86400)return Math.floor(seconds/3600)+'h ago';
  return new Date(t).toLocaleDateString();
}
function empty(message,linkUrl='',label=''){
  const node=make('div','rc-feed-empty',message);
  if(linkUrl){
    const a=make('a','',label);
    a.href=linkUrl;node.appendChild(a);
  }
  return node;
}
function currentFeedURL(offset=0){
  return base+'/social/timeline?mode='+mode+'&limit=25&offset='+offset;
}
function sectionSeries(activities){
  const section=$('followingActivity'),host=$('followingActivityCards');
  section.hidden=mode!=='following'||!activities.length;
  host.replaceChildren();
  activities.forEach(item=>{
    const a=make('a','rc-race-activity');
    a.href=String(item.url||'/race-center/my-racing');
    const tag=make('small','',item.kind==='live'?'LIVE EVENT':item.kind==='movement'?'STANDINGS UPDATE':'UPCOMING RACE');
    const title=make('strong','',item.title||'Racing update');
    const body=make('span','',item.description||'From your followed series');
    a.append(tag,title,body);
    host.appendChild(a);
  });
}
async function loadFeed(append=false){
  const gen=++requestGeneration;
  const host=$('socialFeed'),pager=$('feedMore');
  if(!append){host.replaceChildren(empty('Loading '+mode+' updates…'));pager.replaceChildren();}
  try{
    const payload=await api(currentFeedURL(append?nextOffset:0));
    if(gen!==requestGeneration)return;
    const posts=Array.isArray(payload.posts)?payload.posts:[];
    const updates=Array.isArray(payload.updates)?payload.updates:[];
    currentPosts=append?currentPosts.concat(posts):posts;
    nextOffset=payload.next_offset;
    if(!append)host.replaceChildren();
    if(!currentPosts.length&&!updates.length){
      host.appendChild(mode==='following'?
        empty('No posts from your racing follows yet. Follow drivers, teams or series, or share the first update.','/race-center/community','Find racers to follow →'):
        empty('No racing posts yet. Be the first to share something from the paddock.'));
    }else{
      const combined=[
        ...posts.map(post=>({type:'person',date:post.created_at,record:post})),
        ...updates.map(update=>({type:'entity',date:update.created_at,record:update}))
      ].sort((left,right)=>(Date.parse(right.date||'')||0)-(Date.parse(left.date||'')||0));
      combined.forEach(item=>host.appendChild(item.type==='person'?
        renderPost(item.record):renderEntityUpdate(item.record)));
    }
    if(!append)sectionSeries(Array.isArray(payload.activities)?payload.activities:[]);
    pager.replaceChildren();
    if(nextOffset!==null&&nextOffset!==undefined){
      const button=make('button','rc-outline','Load more posts');
      button.type='button';
      button.addEventListener('click',async()=>{button.disabled=true;await loadFeed(true);button.disabled=false;});
      pager.appendChild(button);
    }
    if(payload.follows&&mode==='following'){
      $('followMetrics').textContent=
        payload.follows.people+' people · '+payload.follows.drivers+' drivers · '+payload.follows.series+' series followed';
    }
    const requestedPost=new URLSearchParams(location.search).get('post');
    if(requestedPost&&!append){
      const target=host.querySelector('[data-post-id="'+CSS.escape(requestedPost)+'"]');
      if(target)target.scrollIntoView({block:'center',behavior:'smooth'});
    }
  }catch(err){
    if(gen!==requestGeneration)return;
    if(!append){host.replaceChildren(empty(err.message||'Could not load feed.'));sectionSeries([]);}
    else{pager.replaceChildren(empty('Could not load more posts. Try refreshing.'));}
  }
}
function renderEntityUpdate(item){
  const card=make('article','rc-post rc-entity-update');
  const heading=make('header','rc-post-head');
  const name=make('div','rc-entity-identity');
  name.append(make('small','rc-kicker',String(item.entity_type||'RACING').toUpperCase()+' UPDATE'),
              make('strong','',item.entity_name||'Race Center racing'));
  const stamp=make('span','rc-time',timeAgo(item.created_at));
  heading.append(name,stamp);
  card.append(heading,make('p','rc-post-body',item.body||''));
  if(item.media_url){
    const picture=make('img','rc-post-media');
    picture.src=String(item.media_url);picture.alt='Photo shared with this racing update';
    picture.loading='lazy';
    card.appendChild(picture);
  }
  const type=String(item.entity_type||'');
  const route=type==='series'?'/race-center/series/':
    type==='team'?'/race-center/team/':type==='track'?'/race-center/track/':
    type==='event'?'/race-center/event/':'/race-center/drivers';
  const link=make('a','rc-entity-open','View racing profile →');
  link.href=type==='driver'?route:route+encodeURIComponent(String(item.entity_key||''));
  card.appendChild(link);
  return card;
}
function reportButton(type,id){
  const button=make('button','rc-text-button','Report');
  button.type='button';
  button.addEventListener('click',()=>{
    if(!me.authenticated){location.href='/race-center?account=1';return;}
    reportTarget={target_type:type,target_id:id};
    $('socialReportFeedback').textContent='';
    $('socialReportDialog').showModal();
  });
  return button;
}
function commentCard(post,comment,details,replyInput,replyNote){
  const item=make('article','rc-comment'+(comment.parent_comment_id?' is-reply':''));
  const heading=make('div','rc-comment-head');
  heading.append(authorLink(comment.author||{}),make('span','rc-time',timeAgo(comment.created_at)));
  const body=make('p','',comment.body||'');
  const actions=make('div','rc-comment-actions');
  const reply=make('button','rc-text-button','Reply');
  reply.type='button';
  reply.addEventListener('click',()=>{
    if(!me.authenticated){location.href='/race-center?account=1';return;}
    details.open=true;
    replyInput.dataset.replyTo=String(comment.id);
    replyNote.textContent='Replying to '+String(comment.author?.display_name||comment.author?.handle||'racer');
    replyInput.focus();
  });
  actions.append(reply,reportButton('comment',comment.id));
  item.append(heading,body,actions);
  return item;
}
function renderPost(post){
  const card=make('article','rc-post');
  card.dataset.postId=String(post.id);
  const header=make('header','rc-post-head');
  const top=make('div','rc-post-head-main');
  top.append(authorLink(post.author||{}),make('span','rc-time',timeAgo(post.created_at)));
  header.appendChild(top);
  const opts=make('div','rc-post-head-actions');
  if(post.series_key){
    const tag=make('a','rc-post-topic','#'+post.series_key);
    tag.href='/race-center/series/'+encodeURIComponent(post.series_key);
    opts.appendChild(tag);
  }
  if(post.driver_key)opts.appendChild(make('span','rc-post-topic','Driver: '+post.driver_key));
  opts.appendChild(reportButton('post',post.id));
  if(post.owner){
    const del=make('button','rc-text-button','Delete');
    del.addEventListener('click',async()=>{
      if(!confirm('Delete your Race Center post?'))return;
      del.disabled=true;
      try{await api(base+'/feed/'+post.id,{method:'DELETE'});await loadFeed();}
      catch(err){del.disabled=false;alert(err.message);}
    });
    opts.appendChild(del);
  }
  header.appendChild(opts);
  card.append(header,make('p','rc-post-body',post.body||''));
  if(post.media?.url){
    const media=post.media.type==='video'?make('video','rc-post-media'):make('img','rc-post-media');
    media.src=String(post.media.url);
    if(post.media.type==='video'){media.controls=true;media.preload='metadata';media.playsInline=true;}
    else{media.loading='lazy';media.alt='Photo shared with this racing post';}
    card.appendChild(media);
  }
  const actions=make('div','rc-post-actions');
  for(const [key,title] of [['checkered','🏁'],['fire','🔥']]){
    const active=(post.viewer_reactions||[]).includes(key);
    const b=make('button','rc-reaction'+(active?' is-active':''),title+' '+Number(post.reactions?.[key]||0));
    b.type='button';b.setAttribute('aria-pressed',String(active));
    b.setAttribute('aria-label',title+' reaction');
    b.addEventListener('click',async()=>{
      if(!me.authenticated){location.href='/race-center?account=1';return;}
      b.disabled=true;
      try{await api(base+'/feed/'+post.id+'/reaction',{method:'POST',body:JSON.stringify({reaction:key})});await loadFeed();}
      catch(err){b.disabled=false;alert(err.message);}
    });
    actions.appendChild(b);
  }
  card.appendChild(actions);
  const comments=make('details','rc-post-comments');
  const summary=make('summary','', '💬 '+Number(post.comment_count||0)+' comments');
  comments.appendChild(summary);
  const thread=make('div','rc-comment-thread');
  const items=Array.isArray(post.comments)?post.comments:[];
  const replyInput=make('textarea','rc-comment-input');
  replyInput.rows=2;replyInput.maxLength=600;replyInput.placeholder='Add a comment…';
  const replyNote=make('span','rc-reply-note','');
  if(!items.length)thread.appendChild(empty('Be the first to comment.'));
  items.forEach(c=>thread.appendChild(commentCard(post,c,comments,replyInput,replyNote)));
  comments.appendChild(thread);
  const form=make('form','rc-comment-form');
  const submit=make('button','rc-primary','Post comment');submit.type='submit';
  const clear=make('button','rc-outline','Cancel reply');clear.type='button';
  clear.addEventListener('click',()=>{delete replyInput.dataset.replyTo;replyNote.textContent='';});
  const feedback=make('span','rc-feedback','');
  form.append(replyNote,replyInput,clear,submit,feedback);
  form.addEventListener('submit',async event=>{
    event.preventDefault();
    if(!me.authenticated){location.href='/race-center?account=1';return;}
    const body=replyInput.value.trim();
    if(!body)return;
    submit.disabled=true;feedback.textContent='Posting…';
    try{
      const opts={body};
      if(replyInput.dataset.replyTo)opts.parent_comment_id=Number(replyInput.dataset.replyTo);
      await api(base+'/feed/'+post.id+'/comments',{method:'POST',body:JSON.stringify(opts)});
      await loadFeed();const found=$('socialFeed').querySelector('[data-post-id="'+post.id+'"] .rc-post-comments');
      if(found)found.open=true;
    }catch(err){feedback.textContent=err.message;submit.disabled=false;}
  });
  comments.appendChild(form);card.appendChild(comments);
  return card;
}
function selectFeed(target){
  mode=target;
  $('followingTab').setAttribute('aria-selected',String(mode==='following'));
  $('discoverTab').setAttribute('aria-selected',String(mode==='discover'));
  $('feedKicker').textContent=mode==='following'?'PERSONAL TIMELINE':'OPEN PADDOCK';
  $('feedHeading').textContent=mode==='following'?'From your racing':'Discover Race Center';
  document.title=(mode==='following'?'Following':'Discover')+' · Pitmark Race Center';
  const u=new URL(location.href);u.searchParams.set('feed',mode);
  history.replaceState(null,'',u);
  if(mode==='following'&&!me.authenticated){
    $('socialAuthNote').hidden=false;
    $('socialFeed').replaceChildren(empty('Sign in to build your Following feed.'));
    $('followingActivity').hidden=true;$('feedMore').replaceChildren();return;
  }
  $('socialAuthNote').hidden=true;
  loadFeed();
}
function buildTopics(){
  const select=$('socialTopic');
  select.replaceChildren(new Option('General post',''));
  (me.follows||[]).filter(f=>['series','driver'].includes(f.kind)).forEach(f=>{
    const name=(f.kind==='series'?'Series':'Driver')+': '+(f.label||f.key);
    select.appendChild(new Option(name,f.kind+':'+f.key));
  });
}
async function publish(event){
  event.preventDefault();
  const body=$('socialBody').value.trim();
  const media=$('socialMediaInput').files[0];
  if(!body&&!media){$('socialComposeStatus').textContent='Write an update or select a photo/video.';return;}
  if(media){
    const max=media.type.startsWith('video/')?12*1024*1024:5*1024*1024;
    if(media.size>max){$('socialComposeStatus').textContent='File exceeds the allowed size.';return;}
  }
  const btn=$('publishSocialPost');
  btn.disabled=true;$('socialComposeStatus').textContent='Publishing…';
  const value=$('socialTopic').value||'';
  const bodyData={body:body||(media?.type.startsWith('video/')?'Shared a racing video':'Shared a racing photo')};
  if(value.startsWith('series:'))bodyData.series_key=value.slice(7);
  if(value.startsWith('driver:'))bodyData.driver_key=value.slice(7);
  try{
    const created=await api(base+'/feed',{method:'POST',body:JSON.stringify(bodyData)});
    let mediaWarning='';
    if(media){
      const form=new FormData();form.append('media',media);
      try{await api(base+'/feed/'+created.id+'/media',{method:'POST',body:form});}
      catch(err){mediaWarning=' Post published, but media upload failed: '+err.message;}
    }
    $('socialBody').value='';$('socialMediaInput').value='';
    $('composerMediaPreview').hidden=true;$('composerMediaPreview').replaceChildren();
    $('socialComposeStatus').textContent=mediaWarning||'Your update is live.';
    selectFeed(mode);
  }catch(err){$('socialComposeStatus').textContent=err.message;}
  finally{btn.disabled=false;}
}
async function loadNotifications(){
  const list=$('notificationsList');
  if(!me.authenticated){list.replaceChildren(empty('Sign in to get follower and reply notifications.'));return;}
  try{
    const result=await api(base+'/social/notifications');
    $('notificationCount').hidden=!result.unread;
    $('notificationCount').textContent=String(result.unread||0);
    list.replaceChildren();
    if(!result.notifications.length){list.appendChild(empty('All caught up. New followers and replies will appear here.'));return;}
    result.notifications.forEach(notice=>{
      const a=make('a','rc-notice'+(notice.read?'':' is-unread'));
      a.href=String(notice.url||'/race-center');
      a.append(avatar(notice.actor||{}));
      const info=make('span','rc-notice-text');
      const message=notice.kind==='new_follower'?'followed you':
        notice.kind==='reply'?'replied to your comment':'commented on your post';
      info.append(make('strong','',(notice.actor?.name||'A racer')+' '+message),
                  make('small','',timeAgo(notice.created_at)));
      a.appendChild(info);list.appendChild(a);
    });
  }catch(err){list.replaceChildren(empty('Notifications are temporarily unavailable.'));}
}
async function boot(){
  try{me=await api(base+'/account');}catch{me={authenticated:false,follows:[]};}
  $('socialComposer').hidden=!me.authenticated;
  $('notificationBell').hidden=!me.authenticated;
  $('socialProfileLink').textContent=me.authenticated?'My Profile':'Sign in';
  $('socialProfileLink').href=me.authenticated?'/race-center/me':'/race-center?account=1';
  if(me.authenticated){
    buildTopics();
    $('followMetrics').textContent='Personalized from your followed racers and series.';
  }
  selectFeed(new URLSearchParams(location.search).get('feed')==='discover'?'discover':'following');
  if(me.authenticated){
    loadNotifications();
    if(new URLSearchParams(location.search).get('notifications')==='1'){
      $('socialNotifications').showModal();
    }
  }
}
$('followingTab').addEventListener('click',()=>selectFeed('following'));
$('discoverTab').addEventListener('click',()=>selectFeed('discover'));
$('refreshFeed').addEventListener('click',()=>selectFeed(mode));
$('socialComposer').addEventListener('submit',publish);
$('socialMediaInput').addEventListener('change',()=>{
  const file=$('socialMediaInput').files[0];
  const host=$('composerMediaPreview');
  host.replaceChildren();host.hidden=!file;
  if(file)host.appendChild(make('span','',file.name+' · '+(file.size/1024/1024).toFixed(1)+' MB'));
});
$('notificationBell').addEventListener('click',()=>{$('socialNotifications').showModal();loadNotifications();});
$('closeNotifications').addEventListener('click',()=>$('socialNotifications').close());
$('markNotificationsRead').addEventListener('click',async()=>{
  try{await api(base+'/social/notifications/read',{method:'POST',body:JSON.stringify({})});await loadNotifications();}
  catch(err){$('notificationsList').prepend(empty(err.message));}
});
$('closeSocialReport').addEventListener('click',()=>$('socialReportDialog').close());
$('socialReportForm').addEventListener('submit',async event=>{
  event.preventDefault();if(!reportTarget)return;
  const button=$('sendSocialReport');button.disabled=true;
  const fields=new FormData(event.target);
  try{
    const result=await api(base+'/social/report',{method:'POST',body:JSON.stringify({
      ...reportTarget,reason:String(fields.get('reason')),details:String(fields.get('details')||'')
    })});
    $('socialReportFeedback').textContent=result.already_reported?'Already reported. Thank you.':'Report sent to Pitmark moderators.';
  }catch(err){$('socialReportFeedback').textContent=err.message;}
  finally{button.disabled=false;}
});
boot();
})();