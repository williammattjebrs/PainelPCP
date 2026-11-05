(function(){
const labels=['Visão geral','Painel matricial','Visão diária','Visão mensal','Importações','Metas','Indicadores','Centros de distribuição','Auditoria','Usuários e acessos'];
const ids=['overview','matrix','daily','monthly','imports','targets','indicators','centers','audit','users'];
const subtitles=['Acompanhe os resultados da operação em um só lugar.','Consulte os indicadores por dia e centro de distribuição.','Acompanhe os apontamentos e resultados diários.','Compare o desempenho consolidado mês a mês.','Acompanhe importações de dados operacionais.','Visualize metas e versões configuradas por período.','Consulte os indicadores ativos e suas regras.','Acompanhe o desempenho de cada centro de distribuição.','Consulte alterações e eventos registrados no sistema.','Gerencie usuários e níveis de acesso.'];
const nav=document.getElementById('nav'),title=document.getElementById('pageTitle'),crumb=document.getElementById('crumb'),sub=document.getElementById('pageSub'),toast=document.getElementById('toast');
function notify(s){toast.textContent=s;toast.classList.add('show');setTimeout(()=>toast.classList.remove('show'),2200)}
nav.addEventListener('click',function(e){const b=e.target.closest('.nav-item');if(!b)return;document.querySelectorAll('.nav-item').forEach(x=>x.classList.remove('active'));b.classList.add('active');const i=ids.indexOf(b.dataset.page);title.textContent=labels[i];crumb.textContent=labels[i];sub.textContent=subtitles[i];if(i!==0)notify('Prévia visual: tela de '+labels[i].toLowerCase()+' em construção.');document.querySelector('.sidebar').classList.remove('open')});
document.querySelectorAll('[data-go]').forEach(b=>b.addEventListener('click',()=>{const target=document.querySelector('[data-page="'+b.dataset.go+'"]');if(target)target.click()}));
document.getElementById('refresh').addEventListener('click',()=>notify('Demonstração atualizada. Os números são fictícios.'));
document.getElementById('center').addEventListener('change',function(){const p=document.getElementById('production');p.innerHTML=this.value==='Todos os CDs'?'18.426 <small>un.</small>':this.value==='CD Cajamar'?'7.842 <small>un.</small>':this.value==='CD Extrema'?'5.106 <small>un.</small>':'2.936 <small>un.</small>';notify('Filtro aplicado: '+this.value)});
document.getElementById('period').addEventListener('click',()=>notify('Use os atalhos de período para navegar na demonstração.'));
document.querySelectorAll('.period-chip').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('.period-chip').forEach(x=>x.classList.remove('active'));b.classList.add('active');document.querySelector('#period span').textContent=b.textContent==='30 dias'?'Últimos 30 dias':b.textContent;notify('Período: '+b.textContent)}));
document.getElementById('menuToggle').addEventListener('click',()=>document.querySelector('.sidebar').classList.toggle('open'));
document.querySelectorAll('.table-footer button:not(:disabled),.more,.icon-btn').forEach(b=>b.addEventListener('click',()=>notify('Ação disponível na versão funcional após validação da interface.')));
const vals=[39,47,43,55,49,64,58,70,61,74,57,68,81,73,89,67,77,92,84,96,75,88,71,83,99,78,91,85,100,87];
const W=720,H=170,pad=18,step=(W-pad*2)/(vals.length-1);
let points=vals.map((v,i)=>(pad+i*step)+','+(H-10-v*1.24)).join(' ');
let area=pad+','+(H-10)+' '+points+' '+(W-pad)+','+(H-10);
let grid=[35,75,115,155].map(y=>'<line x1="0" y1="'+y+'" x2="'+W+'" y2="'+y+'" stroke="#edf0f4" stroke-dasharray="3 4"/><text x="0" y="'+(y-4)+'" fill="#a3adba" font-size="9">'+(190-y)+'</text>').join('');
document.getElementById('chart').innerHTML='<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none"><defs><linearGradient id="fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#ed781f" stop-opacity=".16"/><stop offset="1" stop-color="#ed781f" stop-opacity="0"/></linearGradient></defs>'+grid+'<line x1="0" y1="84" x2="'+W+'" y2="84" stroke="#c4cfdb" stroke-dasharray="5 5"/><polygon points="'+area+'" fill="url(#fill)"/><polyline points="'+points+'" fill="none" stroke="#ed781f" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>'+vals.map((v,i)=>i%5===0?'<circle cx="'+(pad+i*step)+'" cy="'+(H-10-v*1.24)+'" r="3" fill="#fff" stroke="#ed781f" stroke-width="2"/>':'').join('')+'</svg>';
})();

