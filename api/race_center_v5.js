(function(){
  let v5People=[];
  function v5YoutubeEmbed(raw){
    try{
      const url=new URL(String(raw||''),location.origin);
      const host=url.hostname.replace(/^www\./,'').toLowerCase();
      let id='';
      if(host==='youtu.be')id=url.pathname.split('/').filter(Boolean)[0]||'';
      else if(host==='youtube.com'||host==='m.youtube.com'){
        if(url.pathname==='/watch')id=url.searchParams.get('v')||'';
        else{
          const parts=url.pathname.split('/').filter(Boolean);
          if(['live','embed','shorts'].includes(parts[0]))id=parts[1]||'';
        }
      }
      return /^[A-Za-z0-9_-]{6,20}$/.test(id)
        ?'https://www.youtube-nocookie.com/embed/'+encodeURIComponent(id)+'?autoplay=1&mute=1&rel=0'
        :'';
    }catch(_error){return '';}
  }

  function v5NextEvent(){
    const items=(state.payload&&state.payload.events&&state.payload.events.next)||[];
    return items
      .filter(function(item){return item&&item.event&&item.event.start;})
      .map(function(item){return Object.assign({},item,{_time:new Date(item.event.start).getTime()});})
      .filter(function(item){return Number.isFinite(item._time);})
      .sort(function(a,b){return a._time-b._time;})[0]||null;
  }

  function v5SeriesForItem(item){
    if(!item||!state.payload)return null;
    return (state.payload.series||[]).find(function(series){
      return String(series.series_key)===String(item.series_key||'');
    })||null;
  }

  function v5BroadcastGraphic(item,event,live){
    const series=v5SeriesForItem(item);
    const logoUrl=series&&String(series.series_logo||series.series_logo_direct||'').trim();
    const logo=logoUrl
      ?'<img class="broadcast-series-logo" src="'+esc(logoUrl)+'" alt="'+esc(item.series_name||'Series')+' logo">'
      :'<div class="broadcast-series-mark">'+esc(String(item.series_name||'RACING').slice(0,22))+'</div>';
    const source=series&&series.series_logo_source_url
      ?'<a class="broadcast-source" href="'+esc(series.series_logo_source_url)+'" target="_blank" rel="noopener">Series identity source ↗</a>'
      :'';
    return '<div class="broadcast-identity-bg"><div class="broadcast-speed-lines"></div><div class="broadcast-logo-wrap">'+logo+'</div><div class="broadcast-copy"><span>'+(live?'LIVE RACE':'NEXT GREEN FLAG')+'</span><strong>'+esc(event.name||item.series_name||'Race weekend')+'</strong><small>'+(item.watch_url?'Official viewing is available through the broadcaster/series link.':'No official embeddable broadcast source is available yet.')+'</small>'+source+'</div></div>';
  }

  function v5RenderLive(){
    const stage=$('#liveStage');
    if(!stage||!state.payload)return;
    const events=state.payload.events||{};
    const live=(events.live||[])[0]||null;
    const next=v5NextEvent();
    const item=live||next;
    const media=$('#liveStageMedia');
    const actions=$('#liveStageActions');
    stage.classList.toggle('is-live',Boolean(live));

    if(!item){
      $('#liveStageKicker').textContent='RACE DAY';
      $('#liveStageTitle').textContent='Your racing home is quiet. For now.';
      $('#liveStageText').textContent='No tracked event has a start time on the board right now. Standings, follows, and the Pit Wall are still live.';
      if(actions)actions.innerHTML='<a class="button" href="/race-center/schedules">Browse schedules</a>';
      if(media)media.innerHTML='<div class="broadcast-identity-bg empty"><div class="broadcast-speed-lines"></div><div class="broadcast-series-mark">PITMARK</div><div class="broadcast-copy"><span>LIVE BOARD</span><strong>No race is live right now.</strong><small>Official viewing appears here only when Pitmark has a source it can surface safely.</small></div></div>';
      return;
    }

    const event=item.event||{};
    $('#liveStageKicker').textContent=live?'LIVE NOW':'NEXT GREEN FLAG';
    $('#liveStageTitle').textContent=live
      ?String(item.series_name||'Racing')+' is live.'
      :'Next up: '+String(item.series_name||'Racing')+'.';
    $('#liveStageText').textContent=live
      ?String(event.name||'Live event')+(item.watch_name?' · '+item.watch_name:'')
      :String(event.name||'Next event')+(event.start?' · '+eventWhen(event):'')+(item.watch_name?' · '+item.watch_name:'');
    if(actions){
      let html='';
      if(item.watch_url)html+='<a class="button primary" href="'+esc(item.watch_url)+'" target="_blank" rel="noopener">Official watch info ↗</a>';
      if(item.schedule_url)html+='<a class="button" href="'+esc(item.schedule_url)+'" target="_blank" rel="noopener">Official schedule ↗</a>';
      if(item.series_key)html+='<button class="button" type="button" data-v5-open-series="'+esc(item.series_key)+'">Open standings</button>';
      actions.innerHTML=html;
    }

    const embed=live?v5YoutubeEmbed(item.watch_url):'';
    if(media){
      if(embed){
        media.innerHTML='<iframe src="'+esc(embed)+'" title="'+esc(item.series_name||'Official live race broadcast')+'" allow="autoplay; encrypted-media; picture-in-picture" allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe>';
      }else{
        media.innerHTML=v5BroadcastGraphic(item,event,live);
      }
    }
  }

  function v5DriverFromKey(key){
    const raw=String(key||'');
    const idx=raw.indexOf(':');
    const seriesKey=idx>=0?raw.slice(0,idx):'';
    const driverName=idx>=0?raw.slice(idx+1):raw;
    const series=(state.payload&&state.payload.series||[]).find(function(item){return String(item.series_key)===seriesKey;});
    const row=(series&&series.entries||[]).find(function(item){return String(item.name||'').trim().toLowerCase()===driverName;});
    return {series:series,row:row};
  }

  function v5RenderPersonal(){
    const host=$('#personalFeed');
    if(!host||!state.payload)return;
    const cards=[];
    const followedSeries=(state.payload.series||[]).filter(function(series){return state.favorites.has(String(series.series_key));});

    followedSeries.forEach(function(series){
      const leader=series.entries&&series.entries[0];
      if(series.event_state==='live'){
        cards.push({icon:'●',title:String(series.short_name||series.series_name)+' is live',body:String(series.current_event&&series.current_event.name||'Race in progress'),cta:'Open',key:series.series_key,priority:100});
      }else if(series.current_event&&series.current_event.start){
        cards.push({icon:'◷',title:'Next: '+String(series.short_name||series.series_name),body:String(series.current_event.name||'Event')+' · '+eventTime(series.current_event),cta:'Details',key:series.series_key,priority:70});
      }
      if(leader){
        cards.push({icon:'1',title:String(leader.name||'Leader')+' leads '+String(series.short_name||series.series_name),body:points(leader.points)+' pts'+(identityText(leader)?' · '+identityText(leader):''),cta:'Standings',key:series.series_key,priority:35});
      }
    });

    state.drivers.forEach(function(key){
      const result=v5DriverFromKey(key);
      const series=result.series;
      const row=result.row;
      if(!series||!row)return;
      const movement=Number(row.movement||0);
      cards.push({
        icon:movement>0?'▲':movement<0?'▼':'#',
        title:String(row.name)+' · P'+String(row.position==null?'—':row.position),
        body:String(series.short_name||series.series_name)+' · '+points(row.points)+' pts'+(movement?' · '+(movement>0?'up ':'down ')+Math.abs(movement):''),
        cta:'Track',
        key:series.series_key,
        priority:movement?85:45
      });
    });

    cards.sort(function(a,b){return b.priority-a.priority;});
    const limited=cards.slice(0,10);
    const count=state.favorites.size+state.drivers.size;
    const status=$('#personalStatus');
    if(status)status.textContent=count
      ?String(state.favorites.size)+' series · '+String(state.drivers.size)+' drivers followed'
      :'Follow drivers and series to build your feed.';

    host.innerHTML=limited.length
      ?limited.map(function(item){
        return '<article class="personal-card" data-key="'+esc(item.key)+'" role="button" tabindex="0"><span class="personal-card-icon">'+esc(item.icon)+'</span><div><strong>'+esc(item.title)+'</strong><p>'+esc(item.body)+'</p></div><b>'+esc(item.cta)+' →</b></article>';
      }).join('')
      :'<div class="personal-empty">Your feed gets interesting the second you follow a series or driver. Star something on the standings board and Race Center will build around it.</div>';
  }

  function v5PopulateSeries(){
    const select=$('#pitWallSeries');
    if(!select||!state.payload)return;
    const current=select.value;
    const followed=(state.payload.series||[]).filter(function(item){return state.favorites.has(String(item.series_key));});
    const others=(state.payload.series||[]).filter(function(item){return !state.favorites.has(String(item.series_key));});
    const options=followed.concat(others).slice(0,80);
    select.innerHTML='<option value="">General racing</option>'+options.map(function(item){
      return '<option value="'+esc(item.series_key)+'">'+esc(item.short_name||item.series_name)+'</option>';
    }).join('');
    if(Array.from(select.options).some(function(option){return option.value===current;}))select.value=current;
  }

  function v5Time(iso){
    if(!iso)return '';
    const ms=Date.now()-new Date(iso).getTime();
    if(!Number.isFinite(ms)||ms<0)return 'now';
    const min=Math.floor(ms/60000);
    if(min<1)return 'now';
    if(min<60)return String(min)+'m';
    const hours=Math.floor(min/60);
    if(hours<24)return String(hours)+'h';
    return String(Math.floor(hours/24))+'d';
  }

  function v5WallPost(post){
    const handle=post.author&&post.author.handle?'@'+post.author.handle:'Racer';
    const display=post.author&&post.author.display_name||handle;
    const initials=String(display||'R').split(/\s+/).map(function(x){return x[0]||'';}).join('').slice(0,2).toUpperCase()||'R';

    function reaction(name,symbol){
      const count=Number(post.reactions&&post.reactions[name]||0);
      const active=(post.viewer_reactions||[]).includes(name);
      return '<button class="wall-action '+(active?'active':'')+'" type="button" data-v5-reaction="'+esc(name)+'" data-v5-post="'+String(post.id)+'">'+symbol+(count?' '+String(count):'')+'</button>';
    }

    const comments=(post.comments||[]).map(function(item){
      const author=item.author&&item.author.handle?'@'+item.author.handle:(item.author&&item.author.display_name||'Racer');
      return '<div class="wall-comment"><strong>'+esc(author)+'</strong> '+esc(item.body)+'</div>';
    }).join('');

    let context='';
    if(post.series_key){
      const series=(state.payload&&state.payload.series||[]).find(function(x){return String(x.series_key)===String(post.series_key);});
      context='<span class="wall-context"># '+esc(series&&series.short_name||post.series_key)+'</span>';
    }

    let actions=reaction('checkered','🏁')+reaction('fire','🔥')+reaction('eyes','👀');
    actions+='<button class="wall-action" type="button" data-v5-focus-comment="'+String(post.id)+'">Reply '+(post.comment_count?String(post.comment_count):'')+'</button>';
    if(post.owner)actions+='<button class="wall-action wall-delete" type="button" data-v5-delete="'+String(post.id)+'">Delete</button>';

    let commentForm='';
    if(state.account&&state.account.authenticated){
      commentForm='<div class="wall-comment-form"><input id="v5-comment-'+String(post.id)+'" maxlength="280" placeholder="Reply to the Pit Wall…"><button type="button" data-v5-comment="'+String(post.id)+'">Reply</button></div>';
    }

    return '<article class="wall-post"><div class="wall-post-head"><div class="wall-author"><span class="wall-avatar">'+esc(initials)+'</span><div><strong>'+esc(display)+'</strong><small>'+esc(handle)+'</small></div></div><span class="wall-post-time">'+esc(v5Time(post.created_at))+'</span></div><p class="wall-body">'+esc(post.body)+'</p>'+context+'<div class="wall-actions">'+actions+'</div>'+(comments?'<div class="wall-comments">'+comments+'</div>':'')+commentForm+'</article>';
  }

  function v5RenderPitWall(){
    const host=$('#pitWallFeed');
    if(!host)return;
    host.innerHTML=state.socialPosts.length
      ?state.socialPosts.map(v5WallPost).join('')
      :'<div class="personal-empty">The Pit Wall is quiet. Somebody has to be first over the wall.</div>';
  }

  async function v5LoadFeed(){
    try{
      const payload=await apiJson('/api/public/race-center/feed?limit=40',{method:'GET'});
      state.socialPosts=payload.posts||[];
    }catch(_error){
      state.socialPosts=[];
    }
    v5RenderPitWall();
  }

  function v5RenderProfile(){
    const authed=Boolean(state.account&&state.account.authenticated);
    const profile=state.account&&state.account.profile||{};
    const handle=$('#profileHandle');
    const bio=$('#profileBio');
    const track=$('#profileTrack');
    if(handle&&document.activeElement!==handle)handle.value=profile.handle||'';
    if(bio&&document.activeElement!==bio)bio.value=profile.bio||'';
    if(track&&document.activeElement!==track)track.value=profile.favorite_track||'';
    const note=$('#pitWallComposerNote');
    if(note)note.textContent=authed
      ?'Posting as @'+String(profile.handle||'racer')+'.'
      :'Sign in to post. Everyone can read the public Pit Wall.';
    const peopleClose=$('#peopleDialogClose');
    if(peopleClose)peopleClose.addEventListener('click',function(){$('#peopleDialog')?.close();});

    const postButton=$('#pitWallPost');
    if(postButton)postButton.disabled=!authed;
  }

  function v5RenderAll(){
    if(!state.payload)return;
    v5RenderLive();
    v5RenderPersonal();
    v5PopulateSeries();
    v5RenderProfile();
    v5RenderPitWall();
  }

  async function v5Post(){
    if(!(state.account&&state.account.authenticated)){
      const dialog=$('#accountDialog');
      if(dialog)dialog.showModal();
      return;
    }
    const input=$('#pitWallInput');
    const body=String(input&&input.value||'').trim();
    if(!body)return;
    const seriesKey=String($('#pitWallSeries')&&$('#pitWallSeries').value||'');
    const button=$('#pitWallPost');
    if(button)button.disabled=true;
    try{
      const payload=await apiJson('/api/public/race-center/feed',{
        method:'POST',
        body:JSON.stringify({body:body,series_key:seriesKey,driver_key:''})
      });
      state.socialPosts=payload.posts||[];
      input.value='';
      const counter=$('#pitWallCount');
      if(counter)counter.textContent='0 / 600';
      v5RenderPitWall();
    }catch(error){
      const note=$('#pitWallComposerNote');
      if(note)note.textContent=error.message||'Could not post right now.';
    }finally{
      if(button)button.disabled=false;
    }
  }

  function v5IdentityBadge(identity){
    if(!identity||identity.verification_status!=='verified')return '';
    const label=identity.official_label||identity.account_type||'Official';
    return '<span class="verified-badge" title="'+esc(label)+'">✓</span>';
  }

  function v5RenderPeople(){
    const host=$('#peopleGrid');
    if(!host)return;
    if(!(state.account&&state.account.authenticated)){
      host.innerHTML='<div class="personal-empty">Sign in, follow some racing, and Race Center will connect you with fans who care about the same series and drivers.</div>';
      return;
    }
    if(!v5People.length){
      host.innerHTML='<div class="personal-empty">No strong matches yet. The people graph gets better as more racers and fans join.</div>';
      return;
    }
    host.innerHTML=v5People.map(function(person){
      const initials=String(person.display_name||person.handle||'R').split(/\s+/).map(function(x){return x[0]||'';}).join('').slice(0,2).toUpperCase();
      const shared=Number(person.shared_count||0);
      const identity=v5IdentityBadge(person.identity);
      return '<article class="people-card"><button class="people-main" type="button" data-v5-profile="'+esc(person.handle)+'"><span class="people-avatar">'+esc(initials)+'</span><span><strong>'+esc(person.display_name||person.handle)+identity+'</strong><small>@'+esc(person.handle)+'</small><em>'+esc(shared?shared+' shared follow'+(shared===1?'':'s'):'New to your graph')+'</em></span></button><button class="people-follow" type="button" data-v5-follow-user="'+String(person.id)+'">Follow</button></article>';
    }).join('');
  }

  async function v5LoadPeople(){
    if(!(state.account&&state.account.authenticated)){
      v5People=[];
      v5RenderPeople();
      return;
    }
    try{
      const payload=await apiJson('/api/public/race-center/people/discover?limit=12',{method:'GET'});
      v5People=payload.people||[];
    }catch(_error){
      v5People=[];
    }
    v5RenderPeople();
  }

  async function v5OpenProfile(handle){
    try{
      const profile=await apiJson('/api/public/race-center/people/'+encodeURIComponent(handle),{method:'GET'});
      const identity=profile.identity||{};
      const official=identity.verification_status==='verified'
        ?'<span class="profile-official">✓ '+esc(identity.official_label||identity.account_type||'Verified')+'</span>'
        :'';
      const series=(profile.series||[]).map(function(item){return '<span>'+esc(item.label||item.key)+'</span>';}).join('');
      const drivers=(profile.drivers||[]).slice(0,12).map(function(item){return '<span>'+esc(item.label||item.key)+'</span>';}).join('');
      const action=(state.account&&state.account.authenticated&&state.account.id!==profile.id)
        ?'<button class="button primary" type="button" data-v5-profile-follow="'+String(profile.id)+'" data-v5-profile-following="'+(profile.viewer_follows?'1':'0')+'">'+(profile.viewer_follows?'Following':'Follow')+'</button>'
        :'';
      $('#peopleProfileContent').innerHTML='<div class="profile-hero"><span class="people-avatar large">'+esc(String(profile.display_name||profile.handle).slice(0,2).toUpperCase())+'</span><div><span class="eyebrow">RACE CENTER PROFILE</span><h2 id="peopleDialogTitle">'+esc(profile.display_name||profile.handle)+v5IdentityBadge(identity)+'</h2><p>@'+esc(profile.handle)+'</p>'+official+'</div></div><p class="profile-bio">'+esc(profile.bio||'No bio yet.')+'</p><div class="profile-stats"><div><strong>'+String(profile.followers||0)+'</strong><span>Followers</span></div><div><strong>'+String(profile.following||0)+'</strong><span>Following</span></div><div><strong>'+String((profile.series||[]).length+(profile.drivers||[]).length)+'</strong><span>Racing follows</span></div></div>'+(profile.favorite_track?'<p class="profile-track">Home track: <strong>'+esc(profile.favorite_track)+'</strong></p>':'')+'<div class="profile-action-row">'+action+(identity.external_url?'<a class="button" href="'+esc(identity.external_url)+'" target="_blank" rel="noopener">Official link ↗</a>':'')+'</div>'+(series?'<div class="profile-tags"><strong>Series</strong><div>'+series+'</div></div>':'')+(drivers?'<div class="profile-tags"><strong>Drivers</strong><div>'+drivers+'</div></div>':'');
      $('#peopleDialog')?.showModal();
    }catch(_error){}
  }

  function initV5(){
    try{
      const baseRender=render;
      render=function(){
        baseRender();
        v5RenderAll();
      };
      const baseRenderAccount=renderAccount;
      renderAccount=function(){
        baseRenderAccount();
        v5RenderProfile();
      };
    }catch(error){
      console.error('Race Center V5 render hooks failed',error);
    }

    const postButton=$('#pitWallPost');
    if(postButton)postButton.addEventListener('click',v5Post);

    const input=$('#pitWallInput');
    if(input)input.addEventListener('input',function(){
      const counter=$('#pitWallCount');
      if(counter)counter.textContent=String(input.value.length)+' / 600';
    });

    const profileForm=$('#profileForm');
    if(profileForm)profileForm.addEventListener('submit',async function(event){
      event.preventDefault();
      if(!(state.account&&state.account.authenticated))return;
      const message=$('#profileMessage');
      if(message)message.textContent='Saving…';
      try{
        const payload=await apiJson('/api/public/race-center/profile',{
          method:'PUT',
          body:JSON.stringify({
            handle:String($('#profileHandle')&&$('#profileHandle').value||''),
            bio:String($('#profileBio')&&$('#profileBio').value||''),
            favorite_track:String($('#profileTrack')&&$('#profileTrack').value||'')
          })
        });
        state.account.profile=payload.profile||{};
        v5RenderProfile();
        v5RenderPitWall();
        if(message)message.textContent='Saved.';
      }catch(error){
        if(message)message.textContent=error.message||'Could not save profile.';
      }
    });

    document.addEventListener('click',function(event){
      const openButton=event.target.closest('[data-v5-open-series]');
      if(openButton){
        openSeries(openButton.dataset.v5OpenSeries);
        return;
      }

      const reaction=event.target.closest('[data-v5-reaction]');
      if(reaction){
        if(!(state.account&&state.account.authenticated)){
          const dialog=$('#accountDialog');
          if(dialog)dialog.showModal();
          return;
        }
        const postId=Number(reaction.dataset.v5Post);
        apiJson('/api/public/race-center/feed/'+String(postId)+'/reaction',{
          method:'POST',
          body:JSON.stringify({reaction:String(reaction.dataset.v5Reaction||'')})
        }).then(v5LoadFeed).catch(function(){});
        return;
      }

      const del=event.target.closest('[data-v5-delete]');
      if(del){
        apiJson('/api/public/race-center/feed/'+String(Number(del.dataset.v5Delete)),{method:'DELETE'})
          .then(v5LoadFeed).catch(function(){});
        return;
      }

      const comment=event.target.closest('[data-v5-comment]');
      if(comment){
        const postId=Number(comment.dataset.v5Comment);
        const field=$('#v5-comment-'+String(postId));
        const body=String(field&&field.value||'').trim();
        if(body){
          apiJson('/api/public/race-center/feed/'+String(postId)+'/comments',{
            method:'POST',
            body:JSON.stringify({body:body})
          }).then(v5LoadFeed).catch(function(){});
        }
        return;
      }

      const profileButton=event.target.closest('[data-v5-profile]');
      if(profileButton){
        v5OpenProfile(String(profileButton.dataset.v5Profile||''));
        return;
      }

      const followButton=event.target.closest('[data-v5-follow-user]');
      if(followButton){
        if(!(state.account&&state.account.authenticated)){ $('#accountDialog')?.showModal(); return; }
        const userId=Number(followButton.dataset.v5FollowUser);
        apiJson('/api/public/race-center/people/follow',{method:'PUT',body:JSON.stringify({user_id:userId})})
          .then(function(){return v5LoadPeople();}).catch(function(){});
        return;
      }

      const profileFollow=event.target.closest('[data-v5-profile-follow]');
      if(profileFollow){
        const userId=Number(profileFollow.dataset.v5ProfileFollow);
        const following=profileFollow.dataset.v5ProfileFollowing==='1';
        apiJson('/api/public/race-center/people/follow',{
          method:following?'DELETE':'PUT',
          body:JSON.stringify({user_id:userId})
        }).then(function(){
          profileFollow.dataset.v5ProfileFollowing=following?'0':'1';
          profileFollow.textContent=following?'Follow':'Following';
          v5LoadPeople();
        }).catch(function(){});
        return;
      }

      const focus=event.target.closest('[data-v5-focus-comment]');
      if(focus){
        const field=$('#v5-comment-'+String(focus.dataset.v5FocusComment));
        if(field)field.focus();
      }
    });

    document.addEventListener('submit',function(event){
      if(event.target&&['signupForm','loginForm'].includes(event.target.id)){
        setTimeout(function(){v5RenderProfile();v5LoadFeed();v5LoadPeople();},800);
      }
    });
    const logout=$('#logoutButton');
    if(logout)logout.addEventListener('click',function(){setTimeout(function(){v5RenderProfile();v5LoadFeed();v5LoadPeople();},250);});

    v5LoadFeed();
    v5LoadPeople();
    setTimeout(v5RenderAll,150);
    setTimeout(v5RenderAll,900);
    setInterval(function(){
      if(state.payload)v5RenderAll();
    },30000);
    setInterval(v5LoadFeed,60000);
  }

  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',initV5,{once:true});
  }else{
    initV5();
  }
})();