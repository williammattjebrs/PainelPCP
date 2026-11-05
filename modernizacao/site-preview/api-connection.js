(function(){
"use strict";
const API="http://127.0.0.1:8001";
const tokenKey="pcp_test_api_token";
const $=id=>document.getElementById(id);
const modal=$("loginModal"),form=$("loginForm"),errorBox=$("loginError"),badge=$("modeBadge"),dayInput=$("apiDay"),centerSelect=$("center");
let token=sessionStorage.getItem(tokenKey)||"",user=null,centers=[];
const fmt=n=>new Intl.NumberFormat("pt-BR",{maximumFractionDigits:2}).format(n);
const dateLabel=s=>{if(!s)return "—";const p=s.split("-");return p.length===3?p[2]+"/"+p[1]+"/"+p[0]:s};
function notice(text){const toast=$("toast");toast.textContent=text;toast.classList.add("show");setTimeout(()=>toast.classList.remove("show"),3200)}
function setStatus(text){$("dataStatus").textContent=text}
function setMode(connected){
 badge.classList.toggle("connected",connected);
 badge.innerHTML=connected?"<i></i> BANCO DE TESTE LOCAL":"<i></i> DADOS FICTÍCIOS";
 $("connectOpen").hidden=connected;$("disconnect").hidden=!connected;
}
async function request(path,options){
 const headers=new Headers(options&&options.headers||{});
 if(token)headers.set("Authorization","Bearer "+token);
 if(options&&options.body)headers.set("Content-Type","application/json");
 let response;
 try{response=await fetch(API+path,{...(options||{}),headers,mode:"cors",credentials:"omit"});}
 catch(_){throw new Error("Não foi possível acessar a API local. Inicie a API em 127.0.0.1:8001 e confira a permissão CORS para esta prévia.");}
 if(!response.ok){
  if(response.status===401)throw new Error("Sessão expirada. Conecte-se novamente.");
  if(response.status===403)throw new Error("Este usuário não tem permissão para consultar os indicadores.");
  if(response.status===503)throw new Error("A API não encontrou uma cópia de teste válida. Confira o banco de teste e o arquivo .env.");
  throw new Error("A API respondeu com erro HTTP "+response.status+".");
 }
 return response.status===204?null:response.json();
}
function updateKpis(rows,day){
 const withValue=rows.filter(r=>r.valor!==null&&r.valor!==undefined).length;
 const cds=new Set(rows.map(r=>r.cd).filter(Boolean));
 $("metricOneLabel").textContent="REGISTROS NO DIA";
 $("production").textContent=fmt(rows.length);
 $("metricTwoLabel").textContent="INDICADORES COM VALOR";
 $("metricTwoValue").textContent=fmt(withValue);
 $("metricThreeLabel").textContent="CENTROS COM DADOS";
 $("metricThreeValue").textContent=fmt(cds.size);
 $("metricFourLabel").textContent="DATA CONSULTADA";
 $("metricFourValue").textContent=dateLabel(day);
 const subtitle=document.querySelector(".page-heading .eyebrow");
 subtitle.textContent="DADOS DA CÓPIA LOCAL · "+dateLabel(day);
}
function updateTable(rows){
 const table=document.querySelector(".table-panel table");
 const head=table.querySelector("thead tr"),body=table.querySelector("tbody");
 ["INDICADOR","CD","VALOR","ORIGEM","ATUALIZADO"].forEach((label,i)=>{
  const th=head.children[i]||document.createElement("th");th.textContent=label;if(!th.parentNode)head.appendChild(th);
 });
 while(head.children.length>5)head.lastElementChild.remove();
 body.replaceChildren();
 rows.slice(0,12).forEach(r=>{
  const tr=document.createElement("tr");
  const values=[r.indicador,r.cd,r.valor==null?"—":fmt(Number(r.valor)),r.source||"—",r.updated_at||r.created_at||"—"];
  values.forEach((value,i)=>{const td=document.createElement("td");td.textContent=value==null?"—":String(value);if(i===2){const b=document.createElement("b");b.textContent=td.textContent;td.replaceChildren(b)}tr.appendChild(td)});
  body.appendChild(tr);
 });
 if(!rows.length){const tr=document.createElement("tr"),td=document.createElement("td");td.colSpan=5;td.textContent="Sem registros para esta data e centro.";tr.appendChild(td);body.appendChild(tr)}
 const footer=document.querySelector(".table-footer span");
 footer.textContent="Exibindo "+Math.min(rows.length,12)+" de "+rows.length+" registros da consulta";
}
function updateGroupChart(rows){
 const counts=new Map();rows.forEach(r=>{const name=r.grupo||"Sem grupo";counts.set(name,(counts.get(name)||0)+1)});
 const data=[...counts.entries()].sort((a,b)=>b[1]-a[1]).slice(0,6);
 const host=$("chart"),w=720,rowH=24,h=Math.max(70,data.length*rowH+8),labelW=180,countW=42,barW=w-labelW-countW-24,max=Math.max(1,...data.map(x=>x[1]));
 host.innerHTML="";
 const svg=document.createElementNS("http://www.w3.org/2000/svg","svg");svg.setAttribute("viewBox","0 0 "+w+" "+h);svg.setAttribute("preserveAspectRatio","none");
 data.forEach((d,i)=>{
  const y=i*rowH+5;
  const label=document.createElementNS(svg.namespaceURI,"text");label.setAttribute("x","0");label.setAttribute("y",String(y+12));label.setAttribute("class","real-chart-label");label.textContent=d[0].length>24?d[0].slice(0,22)+"…":d[0];svg.appendChild(label);
  const track=document.createElementNS(svg.namespaceURI,"rect");track.setAttribute("x",String(labelW));track.setAttribute("y",String(y));track.setAttribute("width",String(barW));track.setAttribute("height","15");track.setAttribute("rx","4");track.setAttribute("class","real-chart-track");svg.appendChild(track);
  const bar=document.createElementNS(svg.namespaceURI,"rect");bar.setAttribute("x",String(labelW));bar.setAttribute("y",String(y));bar.setAttribute("width",String(Math.max(3,barW*d[1]/max)));bar.setAttribute("height","15");bar.setAttribute("rx","4");bar.setAttribute("class","real-chart-bar");svg.appendChild(bar);
  const count=document.createElementNS(svg.namespaceURI,"text");count.setAttribute("x",String(labelW+barW+9));count.setAttribute("y",String(y+12));count.setAttribute("class","real-chart-count");count.textContent=String(d[1]);svg.appendChild(count);
 });
 host.appendChild(svg);
 const panel=document.querySelector(".chart-panel");
 panel.querySelector("h2").textContent="Apontamentos por grupo";
 panel.querySelector(".panel-header p").textContent="Distribuição dos registros na data consultada";
 const legend=panel.querySelector(".chart-legend");
 legend.innerHTML='<span><i class="legend-dot actual"></i>Registros</span><strong>'+fmt(rows.length)+' <small>apontamentos</small></strong>';
 panel.querySelector(".chart-labels").hidden=true;
}
function updateCenters(rows){
 const counts=new Map();rows.forEach(r=>{if(r.cd)counts.set(r.cd,(counts.get(r.cd)||0)+1)});
 const max=Math.max(1,...counts.values()),list=document.querySelector(".target-list");list.replaceChildren();
 [...counts.entries()].sort((a,b)=>b[1]-a[1]).forEach(([code,count])=>{
  const meta=centers.find(c=>c.code===code),name=meta?meta.name:code;
  const row=document.createElement("div");row.className="target-row";
  const nameLine=document.createElement("div");nameLine.className="target-name";
  const icon=document.createElement("span");icon.className="cd-avatar ca";icon.textContent=code.slice(0,2);
  const text=document.createElement("div");const b=document.createElement("b");b.textContent=name;const small=document.createElement("small");small.textContent=code;text.append(b,small);
  const total=document.createElement("strong");total.textContent=fmt(count)+" registros";nameLine.append(icon,text,total);
  const track=document.createElement("div");track.className="target-track";const bar=document.createElement("i");bar.className="good";bar.style.width=(count/max*100)+"%";track.appendChild(bar);
  row.append(nameLine,track);list.appendChild(row);
 });
 const panel=document.querySelector(".target-panel");panel.querySelector("h2").textContent="Registros por CD";panel.querySelector(".panel-header p").textContent="Quantidade de apontamentos no dia";
 panel.querySelector(".text-link").hidden=true;
}
async function loadSummary(){
 if(!token)return;
 setStatus("Consultando a cópia local…");
 const query=new URLSearchParams({start:dayInput.value,end:dayInput.value,limit:"50000",...(centerSelect.value?{cd:centerSelect.value}:{})});
 const rows=await request("/api/values?"+query.toString());
 updateKpis(Array.isArray(rows)?rows:[],dayInput.value);
 updateTable(Array.isArray(rows)?rows:[]);
 updateGroupChart(Array.isArray(rows)?rows:[]);
 updateCenters(Array.isArray(rows)?rows:[]);
 setStatus("API local conectada · somente consulta nesta prévia");
}
async function connect(username,password){
 const health=await request("/api/health",{});
 if(health.status!=="ok")throw new Error("API local indisponível ou cópia de teste inválida.");
 const response=await fetch(API+"/api/auth/login",{method:"POST",mode:"cors",credentials:"omit",headers:{"Content-Type":"application/json"},body:JSON.stringify({username,password})});
 if(!response.ok){
  if(response.status===401)throw new Error("Usuário ou senha não reconhecidos na cópia local.");
  if(response.status===503)throw new Error("API sem uma cópia de teste válida. Verifique o arquivo .env.");
  throw new Error("Falha de autenticação na API local (HTTP "+response.status+").");
 }
 const data=await response.json();token=data.access_token;user=data.user;sessionStorage.setItem(tokenKey,token);
 centers=await request("/api/centers");
 centerSelect.replaceChildren();
 const all=document.createElement("option");all.value="";all.textContent="Todos os CDs";centerSelect.appendChild(all);
 centers.forEach(c=>{const option=document.createElement("option");option.value=c.code;option.textContent=c.code+" · "+c.name;centerSelect.appendChild(option)});
 centerSelect.value="";
 await loadSummary();setMode(true);modal.hidden=true;errorBox.textContent="";$("loginPassword").value="";
}
$("connectOpen").addEventListener("click",()=>{errorBox.textContent="";modal.hidden=false;$("loginUser").focus()});
$("closeLogin").addEventListener("click",()=>{modal.hidden=true});
modal.addEventListener("click",e=>{if(e.target===modal)modal.hidden=true});
form.addEventListener("submit",async e=>{
 e.preventDefault();const button=form.querySelector("button[type=submit]");button.disabled=true;button.textContent="Conectando…";errorBox.textContent="";
 try{await connect($("loginUser").value.trim(),$("loginPassword").value);}
 catch(err){errorBox.textContent=err.message;setStatus("Sem conexão com a API local");}
 finally{button.disabled=false;button.textContent="Conectar e carregar";}
});
$("disconnect").addEventListener("click",()=>{sessionStorage.removeItem(tokenKey);token="";user=null;centers=[];window.location.reload()});
dayInput.addEventListener("change",()=>{if(token)loadSummary().catch(e=>{setStatus(e.message);notice(e.message)})});
centerSelect.addEventListener("change",()=>{if(token)loadSummary().catch(e=>{setStatus(e.message);notice(e.message)})});
$("refresh").addEventListener("click",()=>{if(token)loadSummary().then(()=>notice("Dados atualizados a partir do banco de teste.")).catch(e=>{setStatus(e.message);notice(e.message)})});
document.querySelectorAll(".period-chip").forEach(button=>button.addEventListener("click",()=>{
 if(!token)return;
 const d=new Date(),today=new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,10);
 if(button.textContent.trim()==="Este mês")dayInput.value=today.slice(0,8)+"01";else dayInput.value=today;
 loadSummary().catch(e=>{setStatus(e.message);notice(e.message)});
}));
if(token){
 request("/api/auth/me",{}).then(async current=>{user=current;centers=await request("/api/centers");const all=document.createElement("option");all.value="";all.textContent="Todos os CDs";centerSelect.replaceChildren(all);centers.forEach(c=>{const o=document.createElement("option");o.value=c.code;o.textContent=c.code+" · "+c.name;centerSelect.appendChild(o)});await loadSummary();setMode(true)}).catch(()=>{sessionStorage.removeItem(tokenKey);token="";setMode(false);setStatus("Sessão local expirada; os dados fictícios continuam visíveis.")});
}
})();


