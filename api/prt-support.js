const q=document.getElementById('faqSearch'),items=[...document.querySelectorAll('#faqList details')],buttons=[...document.querySelectorAll('[data-filter]')];
function matches(item,v){return !v||((item.innerText+' '+(item.dataset.tags||'')).toLowerCase().includes(v));}
function filter(v){v=(v||'').toLowerCase().trim();items.forEach(x=>x.hidden=!matches(x,v));}
q.addEventListener('input',e=>{buttons.forEach(b=>b.classList.remove('active'));filter(e.target.value);});
buttons.forEach(b=>b.addEventListener('click',()=>{const v=(b.dataset.filter||'').toLowerCase().trim();const wasActive=b.classList.contains('active');buttons.forEach(x=>x.classList.remove('active'));q.value='';if(wasActive){filter('');return;}b.classList.add('active');filter(v);}));
