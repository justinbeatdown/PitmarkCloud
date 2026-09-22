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

  function v5BroadcastPhoto(item){
    const label=String(item&&item.series_name||'').toLowerCase();
    if(label.includes('formula 1')||label.includes('f1')){
      return {
        image:'https://images.pexels.com/photos/10807493/pexels-photo-10807493.jpeg?auto=compress&dpr=1&w=1400',
        source:'https://www.pexels.com/photo/a-formula-1-car-on-a-race-track-10807493/',
        credit:'Rezk Assaf / Pexels'
      };
    }
    return {
      image:'https://images.pexels.com/photos/11488012/pexels-photo-11488012.jpeg?auto=compress&dpr=1&w=1400',
      source:'https://www.pexels.com/photo/car-on-race-track-11488012/',
      credit:'Ruben Noel / Pexels'
    };
  }

  function v5BroadcastGraphic(item,event,live){
    const series=v5SeriesForItem(item);
    const logoUrl=series&&String(series.series_logo||series.series_logo_direct||'').trim();
    const logo=logoUrl
      ?'<img class="broadcast-series-logo compact" src="'+esc(logoUrl)+'" alt="'+esc(item.series_name||'Series')+' logo">'
      :'<div class="broadcast-series-mark compact">'+esc(String(item.series_name||'RACING').slice(0,22))+'</div>';
    const photo=v5BroadcastPhoto(item);
    return '<div class="broadcast-photo-card" style="--race-photo:url(\''+esc(photo.image)+'\')">'+
      '<div class="broadcast-photo-overlay"></div>'+
      '<div class="broadcast-event-top">'+
        '<div class="broadcast-brand-chip">'+logo+'</div>'+
        '<span class="broadcast-event-state">'+(live?'LIVE RACE':'NEXT GREEN FLAG')+'</span>'+
      '</div>'+
      '<div class="broadcast-event-body">'+
        '<small>'+esc(item.series_name||'Racing')+'</small>'+
        '<strong>'+esc(event.name||item.series_name||'Race weekend')+'</strong>'+
        '<p>'+(item.watch_url?'Official viewing is available through the broadcaster/series link.':'No official embeddable broadcast source is available yet.')+'</p>'+
        '<a class="broadcast-photo-credit" href="'+esc(photo.source)+'" target="_blank" rel="noopener">Photo: '+esc(photo.credit)+' ↗</a>'+
      '</div>'+
    '</div>';
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
      if(media){const photo=v5BroadcastPhoto(null);media.innerHTML='<div class="broadcast-photo-card empty" style="--race-photo:url(\''+esc(photo.image)+'\')"><div class="broadcast-photo-overlay"></div><div class="broadcast-event-top"><div class="broadcast-brand-chip"><span class="broadcast-series-mark compact">PITMARK</span></div><span class="broadcast-event-state">LIVE BOARD</span></div><div class="broadcast-event-body"><small>Race Center</small><strong>No race is live right now.</strong><p>Official viewing appears here when Pitmark can legally surface it.</p><a class="broadcast-photo-credit" href="'+esc(photo.source)+'" target="_blank" rel="noopener">Photo: '+esc(photo.credit)+' ↗</a></div></div>';}
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
    const objects=[];
    const followedSeries=(state.payload.series||[]).filter(function(series){
      return state.favorites.has(String(series.series_key));
    });

    followedSeries.forEach(function(series){
      const leaders=(series.entries||[]).slice(0,3);
      const event=series.current_event||null;
      const rows=leaders.map(function(row){
        return '<div class="network-standing-row"><span class="network-pos">'+esc(row.position==null?'—':row.position)+'</span><strong>'+esc(row.name||'Unknown')+'</strong><span>'+points(row.points)+' pts</span>'+move(row.movement,row.comparison_ready!==false)+'</div>';
      }).join('');
      objects.push({
        priority:series.event_state==='live'?120:event?90:55,
        html:'<article class="network-object series-object" data-key="'+esc(series.series_key)+'" role="button" tabindex="0">'+
          '<header><div>'+logo(series)+'<span><small>'+esc(series.group||'RACING')+'</small><strong>'+esc(series.short_name||series.series_name)+'</strong></span></div>'+
          '<button class="network-object-more" type="button" aria-label="Open '+esc(series.series_name)+'">›</button></header>'+
          (event?'<div class="network-event-line"><b>'+(series.event_state==='live'?'LIVE':'NEXT')+'</b><span>'+esc(event.name||'Race event')+(event.start?' · '+esc(eventTime(event)):'')+'</span></div>':'')+
          '<div class="network-standings"><div class="network-object-label">CHAMPIONSHIP</div>'+rows+'</div>'+
          '<footer><span>'+String((series.entries||[]).length)+' classified drivers</span><strong>Open full standings →</strong></footer>'+
        '</article>'
      });
    });

    state.drivers.forEach(function(key){
      const result=v5DriverFromKey(key);
      const series=result.series;
      const row=result.row;
      if(!series||!row)return;
      const movement=Number(row.movement||0);
      objects.push({
        priority:movement?105:65,
        html:'<article class="network-object driver-object" data-key="'+esc(series.series_key)+'" role="button" tabindex="0">'+
          '<header><div><span class="driver-network-avatar">'+esc(String(row.name||'?').split(/\s+/).map(function(x){return x[0]||'';}).join('').slice(0,2).toUpperCase())+'</span><span><small>DRIVER YOU FOLLOW · '+esc(series.short_name||series.series_name)+'</small><strong>'+esc(row.name||'Unknown')+'</strong></span></div><span class="network-rank">P'+esc(row.position==null?'—':row.position)+'</span></header>'+
          '<div class="driver-network-stats"><div><span>Points</span><strong>'+points(row.points)+'</strong></div><div><span>Movement</span><strong>'+move(row.movement,row.comparison_ready!==false)+'</strong></div><div><span>Team</span><strong>'+esc(row.team||row.manufacturer||'—')+'</strong></div></div>'+
          '<footer><span>Following this driver</span><strong>Open championship →</strong></footer>'+
        '</article>'
      });
    });

    objects.sort(function(a,b){return b.priority-a.priority;});
    const status=$('#personalStatus');
    const count=state.favorites.size+state.drivers.size;
    if(status)status.textContent=count
      ?String(state.favorites.size)+' series · '+String(state.drivers.size)+' drivers followed'
      :'Follow drivers and series to build your racing feed.';

    host.innerHTML=objects.length
      ?objects.slice(0,12).map(function(item){return item.html;}).join('')
      :'<div class="personal-empty social-empty"><strong>Your racing feed starts with a follow.</strong><span>Follow a series or driver from Standings and Race Center will turn live schedules, championship positions, movement, and community posts into your home feed.</span><a class="button primary" href="/race-center/standings">Choose your racing</a></div>';
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
      return '<div class="wall-comment" data-v6-comment-id="'+String(item.id||'')+'" data-v6-comment-author="'+String(item.author&&item.author.id||'')+'"><strong>'+esc(author)+'</strong> '+esc(item.body)+'</div>';
    }).join('');

    let context=post.visibility==='friends'?'<span class="wall-context audience">Friends only</span>':'';
    if(post.series_key){
      const series=(state.payload&&state.payload.series||[]).find(function(x){return String(x.series_key)===String(post.series_key);});
      context+='<span class="wall-context"># '+esc(series&&series.short_name||post.series_key)+'</span>';
    }

    let actions=reaction('checkered','🏁')+reaction('fire','🔥')+reaction('eyes','👀');
    actions+='<button class="wall-action" type="button" data-v5-focus-comment="'+String(post.id)+'">Reply '+(post.comment_count?String(post.comment_count):'')+'</button>';
    if(post.owner)actions+='<button class="wall-action wall-delete" type="button" data-v5-delete="'+String(post.id)+'">Delete</button>';

    let commentForm='';
    if(state.account&&state.account.authenticated){
      commentForm='<div class="wall-comment-form"><input id="v5-comment-'+String(post.id)+'" maxlength="280" placeholder="Reply to the Pit Wall…"><button type="button" data-v5-comment="'+String(post.id)+'">Reply</button></div>';
    }

    const avatar=post.author&&post.author.avatar_url
      ?'<span class="wall-avatar image" style="background-image:url(\''+esc(post.author.avatar_url)+'\')"></span>'
      :'<span class="wall-avatar" style="background-color:'+esc(post.author&&post.author.accent_color||'#ff5500')+'">'+esc(initials)+'</span>';
    return '<article class="wall-post"><div class="wall-post-head"><div class="wall-author">'+avatar+'<div><strong>'+esc(display)+'</strong><small>'+esc(handle)+'</small></div></div><span class="wall-post-time">'+esc(v5Time(post.created_at))+'</span></div><p class="wall-body">'+esc(post.body)+'</p>'+context+'<div class="wall-actions">'+actions+'</div>'+(comments?'<div class="wall-comments">'+comments+'</div>':'')+commentForm+'</article>';
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

    const profileOpen=$('#socialProfileOpen');
    if(profileOpen)profileOpen.addEventListener('click',function(){
      if(state.account&&state.account.authenticated){
        $('#accountDialog')?.showModal();
      }else{
        $('#accountDialog')?.showModal();
      }
    });
    const composerAvatar=$('#composerAvatar');
    if(composerAvatar)composerAvatar.addEventListener('click',function(){$('#accountDialog')?.showModal();});
    const findPeople=$('#socialFindPeople');
    if(findPeople)findPeople.addEventListener('click',function(){$('#peopleDiscovery')?.scrollIntoView({behavior:'smooth',block:'center'});});
    const myRacing=$('#socialMyRacing');
    if(myRacing)myRacing.addEventListener('click',function(){$('#personalFeed')?.scrollIntoView({behavior:'smooth',block:'start'});});
    const manageRacing=$('#railManageRacing');
    if(manageRacing)manageRacing.addEventListener('click',function(){location.href='/race-center/standings';});
    const refreshPeople=$('#discoverRefresh');
    if(refreshPeople)refreshPeople.addEventListener('click',v5LoadPeople);

    const postButton=$('#pitWallPost');
    if(postButton)postButton.disabled=!authed;
  }

  function v5RenderAll(){
    if(!state.payload)return;
    v5RenderLive();
    v5RenderPersonal();
    v5PopulateSeries();
    v5RenderProfile();
    v5RenderSocialShell();
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
    const visibility=String($('#pitWallVisibility')&&$('#pitWallVisibility').value||'public');
    const button=$('#pitWallPost');
    if(button)button.disabled=true;
    try{
      const payload=await apiJson('/api/public/race-center/feed',{
        method:'POST',
        body:JSON.stringify({body:body,series_key:seriesKey,driver_key:'',visibility:visibility})
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
      const avatar=person.avatar_url
        ?'<span class="people-avatar image" style="background-image:url(\''+esc(person.avatar_url)+'\')"></span>'
        :'<span class="people-avatar" style="background-color:'+esc(person.accent_color||'#ff5500')+'">'+esc(initials)+'</span>';
      return '<article class="people-card"><button class="people-main" type="button" data-v5-profile="'+esc(person.handle)+'">'+avatar+'<span><strong>'+esc(person.display_name||person.handle)+identity+'</strong><small>@'+esc(person.handle)+'</small><em>'+esc(shared?shared+' shared follow'+(shared===1?'':'s'):'New to your graph')+'</em></span></button><button class="people-follow" type="button" data-v5-follow-user="'+String(person.id)+'">Follow</button></article>';
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

  function v5RenderSocialShell(){
    const account=state.account||{};
    const profile=account.profile||{};
    const authed=Boolean(account.authenticated);
    const display=authed?(account.display_name||profile.handle||'Racer'):'My Race Center';
    const handle=authed?'@'+String(profile.handle||'racer'):'Sign in to personalize';
    const initials=String(display||'RC').split(/\s+/).map(function(x){return x[0]||'';}).join('').slice(0,2).toUpperCase()||'RC';
    if($('#socialProfileAvatar'))$('#socialProfileAvatar').textContent=initials;
    if($('#composerAvatar'))$('#composerAvatar').textContent=initials;
    if($('#socialProfileName'))$('#socialProfileName').textContent=display;
    if($('#socialProfileHandle'))$('#socialProfileHandle').textContent=handle;
    const connections=account.connections||{};
    if($('#socialFollowingCount'))$('#socialFollowingCount').textContent=String(connections.following||0);
    if($('#socialFollowersCount'))$('#socialFollowersCount').textContent=String(connections.followers||0);
    if($('#socialRacingCount'))$('#socialRacingCount').textContent=String(state.favorites.size+state.drivers.size);

    const list=$('#socialMyRacingList');
    if(list&&state.payload){
      const series=(state.payload.series||[]).filter(function(item){return state.favorites.has(String(item.series_key));}).slice(0,5);
      const driverItems=[];
      state.drivers.forEach(function(key){
        const result=v5DriverFromKey(key);
        if(result.series&&result.row&&driverItems.length<4)driverItems.push(result);
      });
      let html=series.map(function(item){
        return '<button class="rail-item" type="button" data-v5-open-series="'+esc(item.series_key)+'">'+logo(item)+'<span><strong>'+esc(item.short_name||item.series_name)+'</strong><small>'+(item.event_state==='live'?'LIVE NOW':item.current_event?'Next '+esc(eventTime(item.current_event)):'Championship')+'</small></span></button>';
      }).join('');
      html+=driverItems.map(function(result){
        return '<button class="rail-item" type="button" data-v5-open-series="'+esc(result.series.series_key)+'"><span class="rail-driver-dot">'+esc(String(result.row.name||'?').slice(0,1))+'</span><span><strong>'+esc(result.row.name||'Driver')+'</strong><small>'+esc(result.series.short_name||result.series.series_name)+' · P'+esc(result.row.position==null?'—':result.row.position)+'</small></span></button>';
      }).join('');
      list.innerHTML=html||'<p>Follow a series or driver and it will live here.</p>';
    }
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
        v5RenderSocialShell();
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

  window.PitmarkRaceCenterV5={
    loadFeed:v5LoadFeed,
    loadPeople:v5LoadPeople,
    renderPitWall:v5RenderPitWall,
    renderPeople:v5RenderPeople,
    renderAll:v5RenderAll
  };

  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',initV5,{once:true});
  }else{
    initV5();
  }
})();