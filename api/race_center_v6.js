(function(){
  let activeSafetyTarget=null;
  let activeProfile=null;
  let toastTimer=null;

  function showToast(message,type){
    const toast=$('#v6Toast');
    if(!toast)return;
    clearTimeout(toastTimer);
    toast.textContent=String(message||'');
    toast.className='v6-toast show '+String(type||'');
    toastTimer=setTimeout(function(){toast.className='v6-toast';},3200);
  }

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
    if($('#socialFriendsCount'))$('#socialFriendsCount').textContent=String(dashboard.friends.length);
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
    await saveProfileV6();
    if(message)message.textContent=kind.charAt(0).toUpperCase()+kind.slice(1)+' uploaded and saved.';
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
      showToast('Profile saved.','success');
    }catch(error){
      if(message)message.textContent=error.message||'Could not save profile.';
    }
  }

  async function friendRequest(userId){
    const payload=await apiJson('/api/public/race-center/friends/request',{method:'POST',body:JSON.stringify({user_id:Number(userId)})});
    await v6RefreshAccount();
    showToast(payload.state==='friends'?'You are now friends.':'Friend request sent.','success');
    if(activeProfile&&activeProfile.id===Number(userId))openProfileV6(activeProfile.handle);
  }

  async function friendRespond(userId,accept){
    await apiJson('/api/public/race-center/friends/respond',{method:'POST',body:JSON.stringify({user_id:Number(userId),accept:Boolean(accept)})});
    await v6RefreshAccount();
    showToast(accept?'Friend request accepted.':'Friend request declined.','success');
  }

  async function removeFriend(userId){
    await apiJson('/api/public/race-center/friends/'+String(Number(userId)),{method:'DELETE'});
    await v6RefreshAccount();
    showToast('Friend removed.','success');
  }

  async function blockUser(userId){
    await apiJson('/api/public/race-center/blocks',{method:'PUT',body:JSON.stringify({user_id:Number(userId)})});
    showToast('Account blocked. Their posts and activity are now hidden.','success');
    $('#safetyDialog')?.close();
    $('#peopleDialog')?.close();
    await v6RefreshAccount();
    if(window.PitmarkRaceCenterV5){
      window.PitmarkRaceCenterV5.loadFeed();
      window.PitmarkRaceCenterV5.loadPeople();
    }
  }

  async function unblockUser(userId){
    await apiJson('/api/public/race-center/blocks',{method:'DELETE',body:JSON.stringify({user_id:Number(userId)})});
    await v6RefreshAccount();
    showToast('Account unblocked.','success');
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
      if(msg)msg.textContent=(payload.duplicate?'You already reported this. Reference #':'Report submitted. Reference #')+String(payload.report_id||'')+'.';
      showToast(payload.duplicate?'That report is already in the moderation queue.':'Report submitted to Pitmark moderation.','success');
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
        '<div class="profile-action-row">'+friendButton+followButton+safety+'<a class="button" href="/race-center/u/'+encodeURIComponent(profile.handle)+'">Profile link ↗</a>'+(extra.website_url?'<a class="button" href="'+esc(extra.website_url)+'" target="_blank" rel="noopener">Website ↗</a>':'')+'</div>'+
        (series?'<div class="profile-tags"><strong>Series</strong><div>'+series+'</div></div>':'')+
        (drivers?'<div class="profile-tags"><strong>Drivers</strong><div>'+drivers+'</div></div>':'')+
        '<div class="profile-posts"><strong>Recent posts</strong><div>'+
          ((profile.posts||[]).length?(profile.posts||[]).map(function(post){
            return '<article class="profile-post"><p>'+esc(post.body||'')+'</p><div><span>'+esc(post.visibility==='friends'?'Friends':'Public')+'</span><span>'+esc(post.created_at?new Date(post.created_at).toLocaleString():'')+'</span></div></article>';
          }).join(''):'<p class="profile-post-empty">No visible posts yet.</p>')+
        '</div></div>'+
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

      postEl.querySelectorAll('.wall-comment[data-v6-comment-id]').forEach(function(commentEl){
        if(commentEl.querySelector('[data-v6-comment-safety]'))return;
        const cid=commentEl.dataset.v6CommentId||'';
        const authorId=commentEl.dataset.v6CommentAuthor||'';
        if(!cid)return;
        const safety=document.createElement('button');
        safety.type='button';
        safety.className='comment-safety';
        safety.dataset.v6CommentSafety=cid;
        safety.dataset.v6CommentAuthor=authorId;
        safety.textContent='•••';
        safety.setAttribute('aria-label','Comment safety options');
        commentEl.appendChild(safety);
      });
    });
  }


  function renderPeopleResults(people){
    const host=$('#peopleGrid');
    if(!host)return;
    if(!people.length){
      host.innerHTML='<div class="personal-empty">No matching Race Center people yet.</div>';
      return;
    }
    host.innerHTML=people.map(function(person){
      const avatar=person.avatar_url
        ?'<span class="people-avatar image" style="background-image:url(\''+esc(person.avatar_url)+'\')"></span>'
        :'<span class="people-avatar">'+esc(initials(person.display_name||person.handle))+'</span>';
      const stateLabel=person.friend_state==='friends'?'Friends':person.friend_state==='outgoing'?'Requested':person.friend_state==='incoming'?'Respond':'Add friend';
      const disabled=person.friend_state==='friends'||person.friend_state==='outgoing';
      return '<article class="people-card">'+
        '<button class="people-main" type="button" data-v6-open-handle="'+esc(person.handle||'')+'">'+avatar+'<span><strong>'+esc(person.display_name||person.handle||'Racer')+'</strong><small>@'+esc(person.handle||'racer')+'</small><em>'+(person.hometown?esc(person.hometown):'Race Center member')+'</em></span></button>'+
        '<button class="people-follow" type="button" data-v6-search-friend="'+String(person.id)+'" '+(disabled?'disabled':'')+'>'+esc(stateLabel)+'</button>'+
      '</article>';
    }).join('');
  }

  let peopleSearchTimer=null;
  async function searchPeople(query){
    const q=String(query||'').trim();
    if(q.length<2){
      if(window.PitmarkRaceCenterV5)window.PitmarkRaceCenterV5.loadPeople();
      return;
    }
    try{
      const payload=await apiJson('/api/public/race-center/people/search?q='+encodeURIComponent(q)+'&limit=20',{method:'GET'});
      renderPeopleResults(payload.people||[]);
    }catch(error){
      const host=$('#peopleGrid');
      if(host)host.innerHTML='<div class="personal-empty">'+esc(error.message||'Could not search people.')+'</div>';
    }
  }

  function moderationRow(item){
    const reporter=item.reporter||{};
    return '<article class="moderation-row">'+
      '<div><span class="moderation-reason">'+esc(item.reason||'report')+'</span><strong>'+esc(item.target_kind||'target')+' #'+esc(item.target_id||'')+'</strong><p>'+esc(item.details||'No additional details.')+'</p><small>Reported by '+esc(reporter.display_name||reporter.handle||'Race Center user')+'</small></div>'+
      '<div class="moderation-actions">'+
        (['post','comment'].includes(item.target_kind)?'<button class="mini-action primary" data-v6-moderate="'+item.id+'" data-action="hide_content">Hide content</button>':'')+
        (item.target_kind==='user'?'<button class="mini-action primary" data-v6-moderate="'+item.id+'" data-action="suspend_user">Suspend</button><button class="mini-action danger-mini" data-v6-moderate="'+item.id+'" data-action="ban_user">Ban</button>':'')+
        '<button class="mini-action" data-v6-moderate="'+item.id+'" data-action="resolve">Resolve</button>'+
        '<button class="mini-action" data-v6-moderate="'+item.id+'" data-action="dismiss">Dismiss</button>'+
      '</div>'+
    '</article>';
  }

  function moderatedUserRow(item){
    return '<article class="moderation-row moderated-user-row">'+
      '<div><span class="moderation-reason">'+esc(item.moderation_status||'moderated')+'</span><strong>'+esc(item.display_name||item.handle||'Race Center user')+'</strong><p>@'+esc(item.handle||'racer')+(item.moderation_reason?' · '+esc(item.moderation_reason):'')+'</p></div>'+
      '<div class="moderation-actions"><button class="mini-action primary" data-v6-restore-user="'+String(item.id)+'">Restore account</button></div>'+
    '</article>';
  }

  async function loadModeration(){
    try{
      const payload=await apiJson('/api/control/race-center/moderation/reports?status=open&limit=100',{method:'GET'});
      const reports=payload.reports||[];
      const tab=$('#moderationTabButton');
      if(tab)tab.hidden=false;
      if($('#moderationBadge'))$('#moderationBadge').textContent=reports.length?String(reports.length):'';
      const host=$('#moderationList');
      if(host)host.innerHTML=reports.length?reports.map(moderationRow).join(''):'<p class="empty-account-list">No open reports.</p>';
      try{
        const userPayload=await apiJson('/api/control/race-center/moderation/users?limit=100',{method:'GET'});
        const moderated=userPayload.users||[];
        const usersHost=$('#moderatedUsersList');
        if(usersHost)usersHost.innerHTML=moderated.length?moderated.map(moderatedUserRow).join(''):'<p class="empty-account-list">No suspended or banned accounts.</p>';
      }catch(_error){}
    }catch(_error){
      const tab=$('#moderationTabButton');
      if(tab)tab.hidden=true;
    }
  }

  async function moderate(reportId,action){
    await apiJson('/api/control/race-center/moderation/reports/'+String(reportId),{
      method:'POST',
      body:JSON.stringify({status:String(action),note:''})
    });
    await loadModeration();
    showToast('Moderation action applied.','success');
    if(window.PitmarkRaceCenterV5)window.PitmarkRaceCenterV5.loadFeed();
  }


  async function restoreModeratedUser(userId){
    await apiJson('/api/control/race-center/moderation/users/'+String(Number(userId)),{
      method:'POST',
      body:JSON.stringify({status:'active',reason:'Restored by Pitmark moderation'})
    });
    showToast('Race Center account restored.','success');
    await loadModeration();
  }


  async function changePassword(){
    const message=$('#passwordMessage');
    if(message)message.textContent='Updating…';
    try{
      await apiJson('/api/public/race-center/account/password',{
        method:'POST',
        body:JSON.stringify({
          current_password:String($('#currentPassword')?.value||''),
          new_password:String($('#newPassword')?.value||'')
        })
      });
      if($('#currentPassword'))$('#currentPassword').value='';
      if($('#newPassword'))$('#newPassword').value='';
      await v6RefreshAccount();
      if(message)message.textContent='Password updated. Other sessions were signed out.';
      showToast('Password updated.','success');
    }catch(error){
      if(message)message.textContent=error.message||'Could not update password.';
    }
  }

  async function deleteAccount(){
    const message=$('#deleteAccountMessage');
    if(message)message.textContent='Deleting…';
    try{
      await apiJson('/api/public/race-center/account/delete',{
        method:'POST',
        body:JSON.stringify({
          password:String($('#deletePassword')?.value||''),
          confirmation:String($('#deleteConfirmation')?.value||'')
        })
      });
      location.href='/race-center';
    }catch(error){
      if(message)message.textContent=error.message||'Could not delete account.';
    }
  }


  function openDeepSeries(seriesKey,attempt){
    const key=String(seriesKey||'').trim();
    if(!key)return;
    if(state.payload){
      openSeries(key);
      return;
    }
    if((attempt||0)<20)setTimeout(function(){openDeepSeries(key,(attempt||0)+1);},200);
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
    const peopleSearch=$('#peopleSearchInput');
    if(peopleSearch)peopleSearch.addEventListener('input',function(){
      clearTimeout(peopleSearchTimer);
      peopleSearchTimer=setTimeout(function(){searchPeople(peopleSearch.value);},180);
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
      const searchFriend=event.target.closest('[data-v6-search-friend]');
      if(searchFriend){friendRequest(searchFriend.dataset.v6SearchFriend).then(function(){searchPeople($('#peopleSearchInput')?.value||'');}).catch(function(error){showToast(error.message||'That action could not be completed.','error');});return;}
      const req=event.target.closest('[data-v6-friend-request]');
      if(req){friendRequest(req.dataset.v6FriendRequest).catch(function(error){showToast(error.message||'That action could not be completed.','error');});return;}
      const accept=event.target.closest('[data-v6-friend-accept]');
      if(accept){friendRespond(accept.dataset.v6FriendAccept,true).catch(function(error){showToast(error.message||'That action could not be completed.','error');});return;}
      const decline=event.target.closest('[data-v6-friend-decline]');
      if(decline){friendRespond(decline.dataset.v6FriendDecline,false).catch(function(error){showToast(error.message||'That action could not be completed.','error');});return;}
      const remove=event.target.closest('[data-v6-friend-remove]');
      if(remove){removeFriend(remove.dataset.v6FriendRemove).catch(function(error){showToast(error.message||'That action could not be completed.','error');});return;}
      const unblock=event.target.closest('[data-v6-unblock]');
      if(unblock){unblockUser(unblock.dataset.v6Unblock).catch(function(error){showToast(error.message||'That action could not be completed.','error');});return;}
      const safeUser=event.target.closest('[data-v6-safety-user]');
      if(safeUser){openSafety('user',safeUser.dataset.v6SafetyUser,safeUser.dataset.v6SafetyLabel,safeUser.dataset.v6SafetyUser);return;}
      const postSafe=event.target.closest('[data-v6-post-safety]');
      if(postSafe){
        const post=(state.socialPosts||[]).find(function(x){return Number(x.id)===Number(postSafe.dataset.v6PostSafety);});
        if(post)openSafety('post',post.id,'post by @'+String(post.author&&post.author.handle||'racer'),post.author&&post.author.id);
        return;
      }
      const commentSafe=event.target.closest('[data-v6-comment-safety]');
      if(commentSafe){
        openSafety('comment',commentSafe.dataset.v6CommentSafety,'comment',commentSafe.dataset.v6CommentAuthor);
        return;
      }
      const moderation=event.target.closest('[data-v6-moderate]');
      if(moderation){moderate(Number(moderation.dataset.v6Moderate),moderation.dataset.action).catch(function(error){showToast(error.message||'Moderation action failed.','error');});return;}
      const restoreUser=event.target.closest('[data-v6-restore-user]');
      if(restoreUser){
        restoreModeratedUser(restoreUser.dataset.v6RestoreUser).catch(function(error){showToast(error.message||'Could not restore account.','error');});
        return;
      }
      const follow=event.target.closest('[data-v6-follow-profile]');
      if(follow){
        const id=Number(follow.dataset.v6FollowProfile);
        const following=follow.dataset.following==='1';
        apiJson('/api/public/race-center/people/follow',{method:following?'DELETE':'PUT',body:JSON.stringify({user_id:id})})
          .then(async function(){
            await v6RefreshAccount();
            showToast(following?'Unfollowed.':'Following.','success');
            if(activeProfile)openProfileV6(activeProfile.handle);
          }).catch(function(error){showToast(error.message||'Could not update follow.','error');});
      }
    });

    $('#moderationRefresh')?.addEventListener('click',function(){loadModeration();});

    $('#changePasswordForm')?.addEventListener('submit',function(event){
      event.preventDefault();
      changePassword();
    });
    $('#deleteAccountForm')?.addEventListener('submit',function(event){
      event.preventDefault();
      deleteAccount();
    });

    const feed=$('#pitWallFeed');
    if(feed){
      new MutationObserver(decoratePosts).observe(feed,{childList:true,subtree:true});
      decoratePosts();
    }

    setTimeout(v6RefreshAccount,250);
    setTimeout(loadModeration,500);
    const deepLinkedHandle=String(document.body?.dataset?.profileHandle||'').trim();
    if(deepLinkedHandle)setTimeout(function(){openProfileV6(deepLinkedHandle);},550);
    const deepLinkedSeries=String(document.body?.dataset?.seriesKey||'').trim();
    if(deepLinkedSeries)setTimeout(function(){openDeepSeries(deepLinkedSeries,0);},250);
    setInterval(function(){
      if(state.account&&state.account.authenticated)v6RefreshAccount();
    },60000);
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});
  else init();
})();