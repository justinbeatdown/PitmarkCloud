(() => {
  let desktopThread=null, mobileThread=null;
  async function mark(id, button){
    if(!id) return;
    button.disabled=true; const old=button.textContent; button.textContent='Training Shield…';
    try{
      const r=await fetch(`/api/control/email/threads/${id}/spam`,{method:'POST',credentials:'same-origin'});
      const d=await r.json(); if(!r.ok) throw Error(d.detail||'Unable to mark spam');
      button.textContent='Spam ✓ Shield trained';
      document.getElementById('mailRefreshBtn')?.click();
      if(typeof mailLoad==='function') try{ await mailLoad(); }catch{}
    }catch(e){button.disabled=false;button.textContent=old;alert(e.message);}
  }
  function desktop(){
    const box=document.getElementById('mailThread'); if(!box||!desktopThread||document.getElementById('mailMarkSpamBtn'))return;
    const head=box.querySelector('.record-row'); if(!head)return;
    const b=document.createElement('button');b.id='mailMarkSpamBtn';b.className='btn ghost mini';b.textContent='Mark as Spam';b.style.marginLeft='8px';
    b.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();mark(desktopThread,b)});head.appendChild(b);
  }
  function mobile(){
    const box=document.getElementById('mMailThread');if(!box||!mobileThread||document.getElementById('mMailMarkSpam'))return;
    const head=box.querySelector('.m-card-head');if(!head)return;
    const b=document.createElement('button');b.id='mMailMarkSpam';b.className='m-ghost';b.textContent='Mark Spam';
    b.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();mark(mobileThread,b)});head.appendChild(b);
  }
  document.addEventListener('click',e=>{
    const d=e.target.closest?.('[data-mail-thread]'); if(d){desktopThread=Number(d.dataset.mailThread)||null;setTimeout(desktop,80)}
    const m=e.target.closest?.('[data-mmail-thread]'); if(m){mobileThread=Number(m.dataset.mmailThread)||null;setTimeout(mobile,80)}
  },true);
  document.addEventListener('DOMContentLoaded',()=>{
    const d=document.getElementById('mailThread');if(d)new MutationObserver(desktop).observe(d,{childList:true,subtree:true});
    const m=document.getElementById('mMailThread');if(m)new MutationObserver(mobile).observe(m,{childList:true,subtree:true});
  });
})();