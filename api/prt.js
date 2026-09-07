const $=id=>document.getElementById(id);
let installUrl="";

async function loadReleaseVersion(){
  try{
    const response=await fetch("/downloads/latest.json",{cache:"no-store",credentials:"same-origin"});
    if(!response.ok) throw new Error("PRT release manifest unavailable");
    const manifest=await response.json();
    const version=String(manifest.version||"").trim();
    if(!version) return;
    const buildVersion=$("prtBuildVersion");
    const downloadVersion=$("prtDownloadVersion");
    if(buildVersion) buildVersion.textContent=`v${version}`;
    if(downloadVersion) downloadVersion.textContent=`DOWNLOAD PRT v${version}`;
  }catch(_){
    // Keep the server-rendered fallback version if the manifest is temporarily unavailable.
  }
}

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
    
  }catch(e){
    $("discordState").textContent="UNAVAILABLE";
    $("botStatus").textContent=e.message||"Discord install is unavailable.";
    
  }
}
document.addEventListener("DOMContentLoaded",()=>{
  loadReleaseVersion();
  loadPrt();
});


(() => {
  try {
    const params = new URLSearchParams(location.search);
    if (params.get('apply') === 'unavailable') {
      const status = document.getElementById('botStatus');
      if (status) status.textContent = 'Early Access application link is being connected. Check back shortly.';
    }
  } catch (_) {}
})();
