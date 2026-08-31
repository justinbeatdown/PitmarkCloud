const $=id=>document.getElementById(id);
let installUrl="";

async function loadPrt(){
  try{
    const [prt,discord]=await Promise.all([
      fetch("/api/prt/status",{credentials:"same-origin"}).then(r=>r.json()),
      fetch("/api/discord/install",{credentials:"same-origin"}).then(async r=>{
        if(!r.ok) throw new Error((await r.json()).detail||"Discord install unavailable");
        return r.json();
      })
    ]);
    installUrl=discord.install_url||"";
    $("cloudState").textContent="ONLINE";
    $("discordState").textContent=installUrl?"READY":"UNAVAILABLE";
    $("botStatus").textContent=installUrl
      ?"Pitmark Bot is ready — Discord will let you choose the server."
      :"Pitmark Bot install is not configured yet.";
    document.querySelectorAll("#installBot,#installBot2").forEach(b=>b.disabled=!installUrl);
  }catch(e){
    $("discordState").textContent="UNAVAILABLE";
    $("botStatus").textContent=e.message||"Discord install is unavailable.";
    document.querySelectorAll("#installBot,#installBot2").forEach(b=>b.disabled=true);
  }
}
function install(){
  if(installUrl) location.href=installUrl;
}
document.addEventListener("DOMContentLoaded",()=>{
  $("installBot")?.addEventListener("click",install);
  $("installBot2")?.addEventListener("click",install);
  loadPrt();
});
