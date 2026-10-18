'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const errorMessage = error => error && error.message ? error.message : 'Please retry.';
  const request = async (path,options={}) => {
    const controller=new AbortController();
    const timeout=setTimeout(()=>controller.abort(),15000);
    try{
      const response=await fetch(path,{
        credentials:'same-origin',cache:'no-store',signal:controller.signal,
        ...options,
        headers:{Accept:'application/json',...(options.body?{'Content-Type':'application/json'}:{}),...(options.headers||{})}
      });
      const data=await response.json().catch(()=>({}));
      if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:response.status===403?'Staff permission is required.':'Request failed.');
      return data;
    }finally{clearTimeout(timeout);}
  };
  const append = (el,tag,text,cls) => {
    const child=document.createElement(tag);
    if(text!==undefined)child.textContent=String(text);
    if(cls)child.className=cls;
    el.appendChild(child);
    return child;
  };
  const safeExternal = (value) => {
    try{
      const url=new URL(String(value||''));
      return ['https:','http:'].includes(url.protocol)?url.href:null;
    }catch{return null;}
  };
  const link=(root,label,url)=>{
    const href=safeExternal(url);
    if(!href)return;
    const a=append(root,'a',label);
    a.href=href;a.target='_blank';a.rel='noopener noreferrer';
  };
  const setStatus=(message,error=false)=>{
    const node=$('adminStatus');node.textContent=message;node.classList.toggle('error',error);
  };
  const pill=(container,status)=>{
    const name=String(status||'pending').toLowerCase();
    append(container,'span',name,'status-pill '+name);
  };
  async function updateRow(kind,item,status,note,button){
    const isClaim=kind==='claim';
    const name=isClaim?item.entity_name:item.series_name;
    if(!window.confirm('Mark '+name+' as '+status+'? This changes the staff review record.'))return;
    button.disabled=true;
    setStatus('Saving '+(isClaim?'entity claim':'series submission')+' review…');
    try{
      const path=isClaim?'/api/public/race-center/entity-claims/'+item.id+'/review':
        '/api/public/race-center/series-submissions/'+item.id+'/review';
      const payload=isClaim?{status,note:String(note||'').slice(0,4000)}:{status};
      await request(path,{method:'PUT',body:JSON.stringify(payload)});
      await refreshAll();
      setStatus('Review saved successfully.');
    }catch(error){
      setStatus(errorMessage(error),true);
      button.disabled=false;
    }
  }
  function renderQueue(kind,data){
    const isClaim=kind==='claim';
    const host=$(isClaim?'claimQueue':'seriesQueue');
    host.replaceChildren();
    if(!data.length){
      append(host,'div','No pending '+(isClaim?'ownership claims.':'series submissions.'),'empty');
      return;
    }
    data.forEach(item=>{
      const card=append(host,'article',undefined,'review-item');
      const head=append(card,'div',undefined,'review-item-header');
      append(head,'h3',isClaim?(item.entity_name||item.entity_key||'Unnamed entity'):(item.series_name||'Unnamed series'));
      pill(head,item.status);
      const meta=[];
      if(isClaim){
        meta.push(String(item.entity_type||'entity').toUpperCase(),String(item.entity_key||''),'Submitter account #'+String(item.user_id));
      }else{
        meta.push(String(item.region||'Region unspecified'),String(item.sanctioning_body||''));
        if(item.contact_name)meta.push('Contact: '+item.contact_name);
        if(item.contact_email)meta.push(item.contact_email);
        if(Array.isArray(item.classes)&&item.classes.length)meta.push('Classes: '+item.classes.join(', '));
      }
      append(card,'p',meta.filter(Boolean).join(' · '),'review-item-meta');
      if(item.note)append(card,'p',item.note,'review-item-note');
      const links=append(card,'div',undefined,'review-links');
      if(isClaim){
        link(links,'Evidence ↗',item.evidence_url);
      }else{
        for(const [key,label] of [
          ['website_url','Website'],['schedule_url','Schedule'],['standings_url','Standings'],
          ['roster_url','Roster'],['results_url','Results'],['logo_url','Logo'],
        ])link(links,label+' ↗',item[key]);
      }
      const actions=append(card,'div',undefined,'review-actions');
      let note;
      if(isClaim){
        note=document.createElement('textarea');
        note.rows=2;note.maxLength=4000;note.placeholder='Review note (optional)';
        note.setAttribute('aria-label','Review note for '+(item.entity_name||item.entity_key));
        actions.appendChild(note);
      }
      const approve=append(actions,'button','Approve','button primary');
      approve.type='button';
      approve.addEventListener('click',()=>updateRow(kind,item,'approved',note?note.value:'',approve));
      const deny=append(actions,'button','Deny','button danger');
      deny.type='button';
      deny.addEventListener('click',()=>updateRow(kind,item,'denied',note?note.value:'',deny));
    });
  }
  async function refreshAll(){
    const [series,claims]=await Promise.all([
      request('/api/public/race-center/series-submissions/review?status=pending&limit=100'),
      request('/api/public/race-center/entity-claims/review?status=pending&limit=100'),
    ]);
    const seriesItems=Array.isArray(series.submissions)?series.submissions:[];
    const claimItems=Array.isArray(claims.claims)?claims.claims:[];
    $('pendingSeries').textContent=seriesItems.length.toLocaleString();
    $('pendingClaims').textContent=claimItems.length.toLocaleString();
    $('totalPending').textContent=(seriesItems.length+claimItems.length).toLocaleString();
    renderQueue('series',seriesItems);
    renderQueue('claim',claimItems);
    setStatus('Review queues updated. Only pending items are shown.');
  }
  $('refreshSeries').addEventListener('click',()=>refreshAll().catch(error=>setStatus(errorMessage(error),true)));
  $('refreshClaims').addEventListener('click',()=>refreshAll().catch(error=>setStatus(errorMessage(error),true)));
  $('editorialForm').addEventListener('submit',async event=>{
    event.preventDefault();
    const form=event.currentTarget;
    if(!form.reportValidity())return;
    if(!window.confirm('Attach this editorial link to the selected Race Center entity?'))return;
    const btn=$('attachEditorial');
    const status=$('editorialStatus');
    const fields=new FormData(form);
    const body={
      entity_type:String(fields.get('entity_type')||'').trim(),
      entity_key:String(fields.get('entity_key')||'').trim(),
      title:String(fields.get('title')||'').trim(),
      url:String(fields.get('url')||'').trim(),
      summary:String(fields.get('summary')||'').trim()
    };
    btn.disabled=true;status.textContent='Attaching article…';
    try{
      await request('/api/public/race-center/editorial-links',{method:'POST',body:JSON.stringify(body)});
      status.textContent='Editorial link attached successfully.';
      form.reset();
    }catch(error){
      status.textContent=errorMessage(error);
    }finally{btn.disabled=false;}
  });
  refreshAll().catch(error=>{
    $('seriesQueue').textContent='Unable to load series queue.';
    $('claimQueue').textContent='Unable to load ownership claims.';
    setStatus(errorMessage(error),true);
  });
})();
