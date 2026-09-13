const $=id=>document.getElementById(id);
let installUrl="";

async function fetchJsonWithTimeout(url,timeoutMs=7000){
  const controller=new AbortController();
  const timer=setTimeout(()=>controller.abort(),timeoutMs);
  try{
    const response=await fetch(url,{cache:"no-store",credentials:"same-origin",signal:controller.signal});
    let body={};
    try{body=await response.json();}catch(_){body={};}
    if(!response.ok) throw new Error(body.detail||`${url} unavailable`);
    return body;
  }finally{
    clearTimeout(timer);
  }
}

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
    // Keep the generic Windows download label if the manifest is unavailable.
  }
}

async function loadPrt(){
  const cloudState=$("cloudState");
  const discordState=$("discordState");
  const botStatus=$("botStatus");

  if(cloudState) cloudState.textContent="CHECKING";
  if(discordState) discordState.textContent="CHECKING";

  const [prtResult,discordResult]=await Promise.allSettled([
    fetchJsonWithTimeout("/api/prt/status",5000),
    fetchJsonWithTimeout("/api/discord/install",7000)
  ]);

  if(prtResult.status==="fulfilled"){
    if(cloudState) cloudState.textContent="ONLINE";
  }else{
    if(cloudState) cloudState.textContent="OFFLINE";
  }

  if(discordResult.status==="fulfilled"){
    const discord=discordResult.value||{};
    installUrl=discord.install_url||"";
    if(discordState) discordState.textContent=installUrl?"READY":"UNAVAILABLE";
    if(botStatus) botStatus.textContent=installUrl
      ?"Pitmark Bot is ready — Discord will let you choose the server."
      :"Pitmark Bot install is not configured yet.";
  }else{
    installUrl="";
    if(discordState) discordState.textContent="UNAVAILABLE";
    if(botStatus){
      const error=discordResult.reason;
      botStatus.textContent=(error&&error.name==="AbortError")
        ?"Discord status check timed out. The community link still works."
        :(error&&error.message)||"Discord install is unavailable.";
    }
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
