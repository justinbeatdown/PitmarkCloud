(() => {
'use strict';
const queue=document.getElementById('socialReportsQueue');
const refresh=document.getElementById('refreshSocialReports');
if(!queue||!refresh)return;
const create=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=String(text);if(cls)n.className=cls;return n;};
async function request(path,options={}){
 const response=await fetch(path,{credentials:'same-origin',cache:'no-store',...options,
   headers:{Accept:'application/json',...(options.body?{'Content-Type':'application/json'}:{}),...(options.headers||{})}});
 const result=await response.json().catch(()=>({}));
 if(!response.ok)throw new Error(result.detail||'Moderation request failed.');
 return result;
}
async function review(row,action,notes,button){
 if(!confirm((action==='removed'?'Remove':'Dismiss report on')+' reported '+row.target_type+' #'+row.target_id+'?'))return;
 button.disabled=true;
 try{
  await request('/api/public/race-center/social/reports/'+row.id+'/review',{
    method:'PUT',body:JSON.stringify({action,note:notes.value.trim()})
  });
  await load();
 }catch(e){button.disabled=false;alert(e.message);}
}
async function load(){
 refresh.disabled=true;
 queue.replaceChildren(create('div','Loading social reports…','empty'));
 try{
  const data=await request('/api/public/race-center/social/reports/review?limit=70');
  const items=Array.isArray(data.reports)?data.reports:[];
  queue.replaceChildren();
  if(!items.length){queue.appendChild(create('div','No pending social reports.','empty'));return;}
  items.forEach(row=>{
    const panel=create('article',undefined,'review-item');
    const header=create('div',undefined,'review-item-header');
    header.append(create('h3',row.target_type+' #'+row.target_id),create('span',row.reason,'status-pill'));
    panel.appendChild(header);
    panel.appendChild(create('p','Report #'+row.id+' · '+row.submitted_at,'review-item-meta'));
    panel.appendChild(create('p',row.content||'[Content removed]','review-item-note'));
    if(row.details)panel.appendChild(create('p','Reporter context: '+row.details,'review-item-note'));
    const actionBar=create('div',undefined,'review-actions');
    const note=create('textarea');note.maxLength=1000;note.rows=2;note.placeholder='Staff review note (optional)';
    note.setAttribute('aria-label','Review note for report '+row.id);
    const dismiss=create('button','Dismiss report','button secondary');dismiss.type='button';
    dismiss.addEventListener('click',()=>review(row,'dismissed',note,dismiss));
    const remove=create('button','Remove content','button danger');remove.type='button';
    remove.addEventListener('click',()=>review(row,'removed',note,remove));
    actionBar.append(note,dismiss,remove);
    panel.appendChild(actionBar);
    queue.appendChild(panel);
  });
 }catch(e){queue.replaceChildren(create('div','Could not load reports: '+e.message,'empty'));}
 finally{refresh.disabled=false;}
}
refresh.addEventListener('click',load);
load();
})();