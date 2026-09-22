(function(){
  let activeSafetyTarget=null;
  let activeProfile=null;

  function initials(name){
    return String(name||'RC').split(/\s+/).map(function(x){return x[0]||'';}).join('').slice(0,2).toUpperCase()||'RC';
  }

  function showAccountTab(name){
    $$('.account-tabs [data-account-tab]').forEach(function(btn){
      btn.classList.toggle('active',btn.dataset.accountTab===name);
    });
    $$('[data-account-panel]').forEach(function(panel){
      panel.classList.toggle('active',panel.dataset.accountPanel===name);
    });
  }

  function v6RenderProfile(){
    if(!(state.account&&state.account.authenticated))return;
    const base=state.account.profile||{};
    const extra=state.account.profile_v6||{};
    const display=extra.display_name||state.account.display_name||base.handle||'Racer';
    const avatar=$('#profilePreviewAvatar');
    const cover=$('#profilePreviewCover');
    if(avatar){
      avatar.textContent=extra.avatar_url?'':initials(display);
      avatar.style.backgroundImage=extra.avatar_url?'url("'+String(extra.avatar_url).replace(/"/g,'')+'")':'';
      avatar.style.backgroundColor=extra.accent_color||'#ff5500';
    }
    if(cover){
      cover.style.backgroundImage=extra.cover_url?'linear-gradient(180deg,rgba(0,0,0,.12),rgba(0,0,0,.5)),url("'+String(extra.cover_url).replace(/"/g,'')+'")':'';
      cover.style.backgroundColor=extra.accent_color||'#161b21';
    }
    if($('#profilePreviewName'))$('#profilePreviewName').textContent=display;
    if($('#profilePreviewHandle'))$('#profilePreviewHandle').textContent='@'+String(base.handle||'racer');

    const map={
      profileDisplayName:display,
      profileAvatarUrl:extra.avatar_url||'',
      profileCoverUrl:extra.cover_url||'',
      profileHometown:extra.hometown||'',
      profileWebsite:extra.website_url||'',
      profileAccent:extra.accent_color||'#ff5500',
      profileVisibility:extra.profile_visibility||'public'
    };
    Object.keys(map).forEach(function(id){
      const el=$('#'+id);
      if(el&&document.activeElement!==el)el.value=map[id];
    });

    if($('#socialProfileAvatar')){
      $('#socialProfileAvatar').textContent=extra.avatar_url?'':initials(display);
      $('#socialProfileAvatar').style.backgroundImage=extra.avatar_url?'url("'+String(extra.avatar_url).replace(/"/g,'')+'")':'';
      $('#socialProfileAvatar').style.backgroundColor=extra.accent_color||'#ff5500';
    }
    if($('#composerAvatar')){
      $('#composerAvatar').textContent=extra.avatar_url?'':initials(display);
      $('#composerAvatar').style.backgroundImage=extra.avatar_url?'url("'+String(extra.avatar_url).replace(/"/g,'')+'")':'';
      $('#composerAvatar').style.backgroundColor=extra.accent_color||'#ff5500';
    }
  }

  function personRow(person,actions){
    if(!person||!person.id)return '';
    const extra=person.profile_v6||person;
    const avatar=extra.avatar_url
      ?'<span class="account-person-avatar image" style="background-image:url(\''+esc(extra.avatar_url)+'\')"></span>'
      :'<span class="account-person-avatar">'+esc(initials(person.display_name||person.handle))+'</span>';
    return '<div class="account-person-row">'+
      avatar+
      '<button class="account-person-main" type="button" data-v6-open-handle="'+esc(person.handle||'')+'"><strong>'+esc(person.display_name||person.handle||'Racer')+'</strong><small>@'+esc(person.handle||'racer')+'</small></button>'+
      '<div class="account-person-actions">'+actions+'</div>'+
    '</div>';
  }

  function v6RenderFriends(){
    if(!(state.account&&state.account.authenticated))return;
    const dashboard=state.account.friends||{friends:[],incoming:[],outgoing:[],blocked:[]};
    const incoming=$('#incomingFriends'), friends=$('#friendsList'), outgoing=$('#outgoingFriends'), blocked=$('#blockedList');
    if(incoming)incoming.innerHTML=dashboard.incoming.length
      ?dashboard.incoming.map(function(p){return personRow(p,'<button class="mini-action primary" data-v6-friend-accept="'+p.id+'">Accept</button><button class="mini-action" data-v6-friend-decline="'+p.id+'">Decline</button>');}).join('')
      :'<p class="empty-account-list">No pending requests.</p>';
    if(friends)friends.innerHTML=dashboard.friends.length
      ?dashboard.friends.map(function(p){return personRow(p,'<button class="mini-action" data-v6-friend-remove="'+p.id+'">Remove</button>');}).join('')
      :'<p class="empty-account-list">No friends yet. Open a racer profile and send a request.</p>';
    if(outgoing)outgoing.innerHTML=dashboard.outgoing.length
      ?dashboard.outgoing.map(function(p){return personRow(p,'<span class="request-pending">Pending</span>');}).join('')
      :'<p class="empty-account-list">No sent requests.</p>';
    if(blocked)blocked.innerHTML=dashboard.blocked.length
      ?dashboard.blocked.map(function(p){return personRow(p,'<button class="mini-action" data-v6-unblock="'+p.id+'">Unblock</button>');}).join('')
      :'<p class="empty-account-list">You have not blocked anyone.</p>';
    const count=dashboard.incoming.length;
    if($('#friendRequestBadge'))$('#friendRequestBadge').textContent=count?String(count):'';
  }

  function notificationRow(item){
    const actor=item.actor||{};
    const label=actor.display_name||actor.handle||'Race Center';
    return '<button class="notification-row '+(item.read?'':'unread')+'" type="button" data-v6-notification="'+item.id+'" data-v6-open-handle="'+esc(actor.handle||'')+'">'+
      '<span class="notification-dot"></span><span><strong>'+esc(label)+'</strong> '+esc(item.text||'')+'<small>'+esc(item.kind||'update')+'</small></span>'+
    '</button>';
  }

  function v6RenderNotifications(){
    const list=(state.account&&state.account.notifications)||[];
    const host=$('#notificationList');
    if(host)host.innerHTML=list.length?list.map(notificationRow).join(''):'<p class="empty-account-list">No notifications yet.</p>';
    const unread=list.filter(function(x){return !x.read;}).length;
    const badge=$('#notificationBadge');
    if(badge){badge.hidden=!unread;badge.textContent=String(unread);}
    if($('#accountNotificationBadge'))$('#accountNotificationBadge').textContent=unread?String(unread):'';
  }

  async function v6RefreshAccount(){
    try{
      state.account=await apiJson('/api/public/race-center/account',{method:'GET'});
      if(typeof mergeAccountFollows==='function')mergeAccountFollows();
      if(typeof renderAccount==='function')renderAccount();
      v6RenderProfile();
      v6RenderFriends();
      v6RenderNotifications();
    }catch(_error){}
  }


  async function uploadProfileImage(kind,file){
    if(!file)return;
    if(file.size>6*1024*1024)throw new Error('Image must be 6 MB or smaller.');
    if(!['image/jpeg','image/png','image/webp'].includes(file.type))throw new Error('Use a JPG, PNG, or WebP image.');
    const message=$('#profileMessage');
    if(message)message.textContent='Uploading '+kind+'…';
    const response=await fetch('/api/public/race-center/profile/image?kind='+encodeURIComponent(kind),{
      method:'POST',
      credentials:'same-origin',
      headers:{'Content-Type':file.type,'X-Pitmark-Filename':file.name||('profile-'+kind)},
      body:file
    });
    let payload={};
    try{payload=await response.json();}catch(_error){}
    if(!response.ok)throw new Error(payload.detail||'Could not upload image.');
    const target=kind==='avatar'?'#profileAvatarUrl':'#profileCoverUrl';
    if($(target))$(target).value=payload.url||'';
    if(!state.account.profile_v6)state.account.profile_v6={};
    state.account.profile_v6[kind+'_url']=payload.url||'';
    v6RenderProfile();
    if(message)message.textContent=kind.charAt(0).toUpperCase()+kind.slice(1)+' uploaded. Save profile to keep your changes.';
  }

  async function saveProfileV6(){
    const message=$('#profileMessage');
    if(message)message.textContent='Saving…';
    try{
      const legacy=await apiJson('/api/public/race-center/profile',{
        method:'PUT',
        body:JSON.stringify({
          handle:String($('#profileHandle')?.value||''),
          bio:String($('#profileBio')?.value||''),
          favorite_track:String($('#profileTrack')?.value||'')
        })
      });
      state.account.profile=legacy.profile||state.account.profile;
      const payload=await apiJson('/api/public/race-center/profile/v6',{
        method:'PUT',
        body:JSON.stringify({
          display_name:String($('#profileDisplayName')?.value||''),
          avatar_url:String($('#profileAvatarUrl')?.value||''),
          cover_url:String($('#profileCoverUrl')?.value||''),
          accent_color:String($('#profileAccent')?.value||'#ff5500'),
          hometown:String($('#profileHometown')?.value||''),
          website_url:String($('#profileWebsite')?.value||''),
          profile_visibility:String($('#profileVisibility')?.value||'public')
        })
      });
      state.account.profile_v6=payload.profile_v6||{};
      state.account.display_name=state.account.profile_v6.display_name||state.account.display_name;
      v6RenderProfile();
      if(message)message.textContent='Saved.';
    }catch(error){
      if(message)message.textContent=error.message||'Could not save profile.';
    }
  }

  async function friendRequest(userId){
    await apiJson('/api/public/race-center/friends/request',{method:'POST',body:JSON.stringify({user_id:Number(userId)})});
    await v6RefreshAccount();
    if(activeProfile&&activeProfile.id===Number(userId))openProfileV6(activeProfile.handle);
  }

  async function friendRespond(userId,accept){
    await apiJson('/api/public/race-center/friends/respond',{method:'POST',body:JSON.stringify({user_id:Number(userId),accept:Boolean(accept)})});
    await v6RefreshAccount();
  }

  async function removeFriend(userId){
    await apiJson('/api/public/race-center/friends/'+String(Number(userId)),{method:'DELETE'});
    await v6RefreshAccount();
  }

  async function blockUser(userId){
    await apiJson('/api/public/race-center/blocks',{method:'PUT',body:JSON.stringify({user_id:Number(userId)})});
    $('#safetyDialog')?.close();
    $('#peopleDialog')?.close();
    await v6RefreshAccount();
    if(typeof v5LoadFeed==='function')v5LoadFeed();
    if(typeof v5LoadPeople==='function')v5LoadPeople();
  }

  async function unblockUser(userId){
    await apiJson('/api/public/race-center/blocks',{method:'DELETE',body:JSON.stringify({user_id:Number(userId)})});
    await v6RefreshAccount();
  }

  function openSafety(kind,id,label,userId){
    activeSafetyTarget={kind:String(kind),id:String(id),label:String(label||kind),userId:Number(userId||0)};
    $('#reportTargetKind').value=activeSafetyTarget.kind;
    $('#reportTargetId').value=activeSafetyTarget.id;
    $('#safetyTargetLabel').textContent='Reporting '+activeSafetyTarget.label+'. Reports go to Pitmark moderation.';
    $('#reportReason').value='';
    $('#reportDetails').value='';
    $('#reportMessage').textContent='';
    const block=$('#safetyBlockButton');
    if(block){block.hidden=!activeSafetyTarget.userId;block.dataset.userId=String(activeSafetyTarget.userId||'');}
    $('#safetyDialog')?.showModal();
  }

  async function submitReport(){
    const msg=$('#reportMessage');
    if(msg)msg.textContent='Submitting…';
    try{
      const payload=await apiJson('/api/public/race-center/reports',{
        method:'POST',
        body:JSON.stringify({
          target_kind:String($('#reportTargetKind').value||''),
          target_id:String($('#reportTargetId').value||''),
          reason:String($('#reportReason').value||''),
          details:String($('#reportDetails').value||'')
        })
      });
      if(msg)msg.textContent='Report submitted. Reference #'+String(payload.report_id||'')+'.';
    }catch(error){
      if(msg)msg.textContent=error.message||'Could not submit report.';
    }
  }

  async function openProfileV6(handle){
    if(!handle)return;
    try{
      const profile=await apiJson('/api/public/race-center/people/'+encodeURIComponent(handle),{method:'GET'});
      activeProfile=profile;
      const host=$('#peopleProfileContent');
      if(!host)return;
      const extra=profile.profile_v6||{};
      const identity=profile.identity||{};
      const verified=identity.verification_status==='verified'?'<span class="profile-official">✓ '+esc(identity.official_label||identity.account_type||'Verified')+'</span>':'';
      const avatar=extra.avatar_url
        ?'<span class="people-avatar large image" style="background-image:url(\''+esc(extra.avatar_url)+'\')"></span>'
        :'<span class="people-avatar large">'+esc(initials(profile.display_name||profile.handle))+'</span>';
      const friendship=profile.friend_state||'none';
      let friendButton='';
      if(state.account&&state.account.authenticated&&state.account.id!==profile.id){
        if(friendship==='none')friendButton='<button class="button primary" type="button" data-v6-friend-request="'+profile.id+'">Add friend</button>';
        else if(friendship==='outgoing')friendButton='<button class="button" type="button" disabled>Request sent</button>';
        else if(friendship==='incoming')friendButton='<button class="button primary" type="button" data-v6-friend-accept="'+profile.id+'">Accept friend</button>';
        else if(friendship==='friends')friendButton='<button class="button" type="button" data-v6-friend-remove="'+profile.id+'">Friends ✓</button>';
      }
      const followButton=(state.account&&state.account.authenticated&&state.account.id!==profile.id)
        ?'<button class="button" type="button" data-v6-follow-profile="'+profile.id+'" data-following="'+(profile.viewer_follows?'1':'0')+'">'+(profile.viewer_follows?'Following':'Follow')+'</button>'
        :'';
      const safety=(state.account&&state.account.authenticated&&state.account.id!==profile.id)
        ?'<button class="button danger-outline" type="button" data-v6-safety-user="'+profile.id+'" data-v6-safety-label="@'+esc(profile.handle)+'">Report / block</button>'
        :'';
      const series=(profile.series||[]).map(function(x){return '<span>'+esc(x.label||x.key)+'</span>';}).join('');
      const drivers=(profile.drivers||[]).map(function(x){return '<span>'+esc(x.label||x.key)+'</span>';}).join('');
      host.innerHTML='<div class="v6-public-profile">'+
        '<div class="v6-cover" style="'+(extra.cover_url?'background-image:linear-gradient(180deg,transparent,rgba(0,0,0,.58)),url(\''+esc(extra.cover_url)+'\');':'background-color:'+(extra.accent_color||'#161b21')+';')+'"></div>'+
        '<div class="v6-profile-top">'+avatar+'<div><span class="eyebrow">RACE CENTER PROFILE</span><h2 id="peopleDialogTitle">'+esc(profile.display_name||profile.handle)+verified+'</h2><p>@'+esc(profile.handle)+'</p></div></div>'+
        '<p class="profile-bio">'+esc(profile.bio||'No bio yet.')+'</p>'+
        '<div class="profile-stats"><div><strong>'+String(profile.followers||0)+'</strong><span>Followers</span></div><div><strong>'+String(profile.following||0)+'</strong><span>Following</span></div><div><strong>'+String((profile.series||[]).length+(profile.drivers||[]).length)+'</strong><span>Racing follows</span></div></div>'+
        (extra.hometown?'<p class="profile-track">From <strong>'+esc(extra.hometown)+'</strong></p>':'')+
        (profile.favorite_track?'<p class="profile-track">Favorite track <strong>'+esc(profile.favorite_track)+'</strong></p>':'')+
        '<div class="profile-action-row">'+friendButton+followButton+safety+(extra.website_url?'<a class="button" href="'+esc(extra.website_url)+'" target="_blank" rel="noopener">Website ↗</a>':'')+'</div>'+
        (series?'<div class="profile-tags"><strong>Series</strong><div>'+series+'</div></div>':'')+
        (drivers?'<div class="profile-tags"><strong>Drivers</strong><div>'+drivers+'</div></div>':'')+
      '</div>';
      $('#peopleDialog')?.showModal();
    }catch(_error){}
  }

  function decoratePosts(){
    $$('.wall-post').forEach(function(postEl){
      if(postEl.querySelector('[data-v6-post-safety]'))return;
      const reaction=postEl.querySelector('[data-v5-post]');
      if(!reaction)return;
      const postId=Number(reaction.dataset.v5Post||0);
      const post=(state.socialPosts||[]).find(function(x){return Number(x.id)===postId;});
      if(!post||post.owner)return;
      const actions=postEl.querySelector('.wall-actions');
      if(!actions)return;
      const btn=document.createElement('button');
      btn.type='button';
      btn.className='wall-action wall-safety';
      btn.dataset.v6PostSafety=String(postId);
      btn.textContent='•••';
      btn.setAttribute('aria-label','Post safety options');
      actions.appendChild(btn);
    });
  }

  function init(){
    const avatarFile=$('#profileAvatarFile');
    if(avatarFile)avatarFile.addEventListener('change',function(){
      const file=avatarFile.files&&avatarFile.files[0];
      if(file)uploadProfileImage('avatar',file).catch(function(error){if($('#profileMessage'))$('#profileMessage').textContent=error.message;});
    });
    const coverFile=$('#profileCoverFile');
    if(coverFile)coverFile.addEventListener('change',function(){
      const file=coverFile.files&&coverFile.files[0];
      if(file)uploadProfileImage('cover',file).catch(function(error){if($('#profileMessage'))$('#profileMessage').textContent=error.message;});
    });

    const form=$('#profileForm');
    if(form)form.addEventListener('submit',function(event){
      event.preventDefault();
      event.stopImmediatePropagation();
      saveProfileV6();
    },true);

    $$('.account-tabs [data-account-tab]').forEach(function(btn){
      btn.addEventListener('click',function(){showAccountTab(btn.dataset.accountTab);});
    });

    $('#socialFriends')?.addEventListener('click',function(){
      showAccountTab('friends');
      $('#accountDialog')?.showModal();
    });
    $('#notificationButton')?.addEventListener('click',function(){
      showAccountTab('notifications');
      $('#accountDialog')?.showModal();
    });
    $('#markNotificationsRead')?.addEventListener('click',async function(){
      await apiJson('/api/public/race-center/notifications/read',{method:'POST'});
      await v6RefreshAccount();
    });
    $('#safetyDialogClose')?.addEventListener('click',function(){$('#safetyDialog')?.close();});
    $('#reportForm')?.addEventListener('submit',function(event){event.preventDefault();submitReport();});
    $('#safetyBlockButton')?.addEventListener('click',function(){
      const id=Number(this.dataset.userId||0); if(id)blockUser(id);
    });

    document.addEventListener('click',function(event){
      const open=event.target.closest('[data-v6-open-handle]');
      if(open&&open.dataset.v6OpenHandle){openProfileV6(open.dataset.v6OpenHandle);return;}
      const existingProfile=event.target.closest('[data-v5-profile]');
      if(existingProfile){setTimeout(function(){openProfileV6(existingProfile.dataset.v5Profile);},0);return;}
      const req=event.target.closest('[data-v6-friend-request]');
      if(req){friendRequest(req.dataset.v6FriendRequest).catch(function(){});return;}
      const accept=event.target.closest('[data-v6-friend-accept]');
      if(accept){friendRespond(accept.dataset.v6FriendAccept,true).catch(function(){});return;}
      const decline=event.target.closest('[data-v6-friend-decline]');
      if(decline){friendRespond(decline.dataset.v6FriendDecline,false).catch(function(){});return;}
      const remove=event.target.closest('[data-v6-friend-remove]');
      if(remove){removeFriend(remove.dataset.v6FriendRemove).catch(function(){});return;}
      const unblock=event.target.closest('[data-v6-unblock]');
      if(unblock){unblockUser(unblock.dataset.v6Unblock).catch(function(){});return;}
      const safeUser=event.target.closest('[data-v6-safety-user]');
      if(safeUser){openSafety('user',safeUser.dataset.v6SafetyUser,safeUser.dataset.v6SafetyLabel,safeUser.dataset.v6SafetyUser);return;}
      const postSafe=event.target.closest('[data-v6-post-safety]');
      if(postSafe){
        const post=(state.socialPosts||[]).find(function(x){return Number(x.id)===Number(postSafe.dataset.v6PostSafety);});
        if(post)openSafety('post',post.id,'post by @'+String(post.author&&post.author.handle||'racer'),post.author&&post.author.id);
        return;
      }
      const follow=event.target.closest('[data-v6-follow-profile]');
      if(follow){
        const id=Number(follow.dataset.v6FollowProfile);
        const following=follow.dataset.following==='1';
        apiJson('/api/public/race-center/people/follow',{method:following?'DELETE':'PUT',body:JSON.stringify({user_id:id})})
          .then(function(){if(activeProfile)openProfileV6(activeProfile.handle);}).catch(function(){});
      }
    });

    const feed=$('#pitWallFeed');
    if(feed){
      new MutationObserver(decoratePosts).observe(feed,{childList:true,subtree:true});
      decoratePosts();
    }

    setTimeout(v6RefreshAccount,250);
    setInterval(function(){
      if(state.account&&state.account.authenticated)v6RefreshAccount();
    },60000);
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});
  else init();
})();