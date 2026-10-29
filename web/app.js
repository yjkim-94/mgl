'use strict';
const $=id=>document.getElementById(id);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const GROUPS={daily:'일상',education:'교육',training:'훈련',hobby:'취미',relationship:'인연',life:'생활 이벤트',career:'프로젝트',story:'인물 서사'};
let game=null, options=[], group='life', toastTimer;
const serverless = !['localhost','127.0.0.1'].includes(location.hostname);
const SAVE_KEY='mgl_v193_autosave';
let snapshot=null;
try { snapshot=JSON.parse(localStorage.getItem(SAVE_KEY)||'null'); } catch { snapshot=null; }
async function request(path, data) {
  if(serverless){
    if(path==='/api/slots') return {slots:Object.keys(localStorage).filter(k=>k.startsWith('mgl_slot_')).map(k=>k.slice(9))};
    if(path==='/api/save'){
      if(!/^[A-Za-z0-9_-]{1,30}$/.test(data.slot)||data.slot==='autosave')throw Error('저장 슬롯 이름 오류');
      localStorage.setItem('mgl_slot_'+data.slot,JSON.stringify(snapshot));return {result:{saved_slot:data.slot}};
    }
    if(path==='/api/load'){
      if(!/^[A-Za-z0-9_-]{1,30}$/.test(data.slot)||data.slot==='autosave')throw Error('저장 슬롯 이름 오류');
      const raw=localStorage.getItem('mgl_slot_'+data.slot);if(!raw)throw Error('저장 슬롯을 찾을 수 없습니다.');
      snapshot=JSON.parse(raw);localStorage.setItem(SAVE_KEY,raw);
      return {result:{loaded_slot:data.slot},state:(await request('/api/state')).result};
    }
    const op=path.split('?')[0].replace('/api/','');
    const payload={op,data:data===undefined?(op==='actions'?{all:path.includes('all=1')}:{}):data,snapshot};
    const res=await fetch('/api/session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const j=await res.json();if(!res.ok)throw Error(j.error||`HTTP ${res.status}`);
    snapshot=j.snapshot;
    try{localStorage.setItem(SAVE_KEY,JSON.stringify(snapshot));}catch(e){console.warn('자동 저장 실패',e);}
    if(op==='state'||op==='actions')return j.result;
    return {result:j.result,state:j.state};
  }
  let res=await fetch(path,data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  let j=await res.json();if(!res.ok)throw Error(j.error||`HTTP ${res.status}`);return j;
}
function toast(msg){clearTimeout(toastTimer);$('toast').textContent=msg;$('toast').classList.add('show');toastTimer=setTimeout(()=>$('toast').classList.remove('show'),3500);}
let modalReturnFocus=null;
function closeModal(){ $('modal').hidden=true; if(modalReturnFocus?.isConnected)modalReturnFocus.focus(); modalReturnFocus=null; }
function modal(title,html){modalReturnFocus=document.activeElement;$('modal-content').innerHTML=`<h2 id="modal-title">${esc(title)}</h2>${html}`;$('modal').hidden=false;$('close-modal').focus();}
function money(x){return Number(x).toLocaleString('ko-KR',{maximumFractionDigits:1});}
function actionName(a){let label=a.action;
  return ({life:'생활 선택',bond:'NPC 교류',course:'시설 교육',study:'능력 훈련',hobby:'취미',event:'진로 이벤트',project:'프로젝트',rest:'휴식',ear:'지구 준비',work:'아르바이트'})[label]||label;
}
async function refresh(){
  const [s,a]=await Promise.all([request('/api/state'),request('/api/actions?all='+($('all-projects').checked?'1':'0'))]);
  game=s;options=a.actions;render();renderTutorial(s);
}
function render(){
  const s=game;
  $('age').textContent=s.completed?'20세 · 지구에서의 새로운 시작':`${s.age}세 · ${s.calendar_month}월`;
  $('chapter').textContent=s.completed?'EPILOGUE · 지구로 이동':`YEAR ${String(s.age-9).padStart(2,'0')} / 10 · ${s.season}`;
  $('narrative').textContent=s.completed?'아스텔리아에서의 10년은 끝났지만, 배운 모든 것이 지구의 미래로 이어집니다.':s.age>=19?'지구와 공명이 짙어지고 있습니다. 마지막 한 해의 선택을 기록하세요.':s.age>=16?'선택한 공부와 관계가 나만의 진로로 연결되는 시기입니다.':'매달 네 번까지 행동을 선택해 아스텔리아에서의 시간을 채워 보세요.';
  renderJourney(s);
  $('ap').textContent=`남은 행동력 ${s.ap_left} AP`;
  $('slots').textContent=`활동 ${s.slots_used} / 4`;
  $('season').textContent=s.season;
  $('next').disabled=s.completed;
  $('next').textContent=s.completed?'지구로 이동 완료':s.month_index===119?'20세 · 지구로 이동 →':'다음 달 →';
  $('activity-meta').textContent=`현재 ${s.slots_used}/4회 · ${s.ap_used}/8 AP 사용`;
  $('show-locked').disabled=s.completed;
  $('all-projects').disabled=s.completed;
  renderFocus(s); renderStats(s); renderNPCs(s); renderStories(s); renderReports(s); renderHistory(s);renderActions();renderFinal(s);
}
function renderFocus(s){
  const list=$('focus'), old=list.value;
  list.innerHTML=s.endings.map(x=>`<option value="${esc(x.id)}">${esc(x.id)} · ${esc(x.name)} (${esc(x.grade)})</option>`).join('');
  list.value=s.focus.id;list.disabled=s.completed;
  $('hint-mode').value=s.hint_mode;
  const f=s.focus;
  $('goal').innerHTML=`<strong>${esc(f.name)} · ${esc(f.grade)}등급</strong>${f.ready?'<p class="ok">현재 필수 조건을 충족했습니다. 최종 우선순위는 20세에 판정됩니다.</p>':'<ul>'+f.missing.slice(0,9).map(t=>`<li>${esc(t)}</li>`).join('')+(f.missing.length>9?`<li>외 ${f.missing.length-9}개 조건</li>`:'')+'</ul>'}`;
  $('career-readiness').innerHTML=`<b>목표 진로 상태: ${s.focus.ready?'필수 조건 충족':'준비 중'}</b><small>미충족 조건 ${s.focus.missing.length}개 · 완료 프로젝트 ${s.project_count}건 · 진로 이벤트 ${s.career_event_count}건</small>`;
  const road=s.career_roadmap;
  $('roadmap').innerHTML=road?`<h3>진로 준비 지도 · ${esc(road.status)}</h3><small>현재 남은 점검 항목 ${esc(road.remaining_items)}개</small>${road.milestones.map(m=>`<div class="milestone"><b>${esc(m.name)}</b><small>${esc(m.priority)} · ${esc(m.note)}</small>${m.kind==='stat'?`<small>${esc(m.current)} / ${esc(m.required)}</small>`:''}</div>`).join('')}`:'';
  $('warnings').innerHTML=s.warnings.map(x=>`<div class="warn">${esc(x)}</div>`).join('');
  const r=s.recommendation, box=$('recommendation');box.innerHTML='';
  if(r){box.innerHTML=`<b>이번 달 추천 · ${esc(r.label)}</b><p>${esc(r.reason)}</p><small>추천은 참고 정보이며 목표 달성을 보장하지 않습니다. 행동 시 AP·자금 및 월간 행동 횟수가 소모될 수 있습니다.</small>`;
    let b=document.createElement('button');b.textContent=r.kind==='specialize'?'전문화 설정':'추천 행동 선택';
    b.onclick=()=>mutate(r.kind==='specialize'?'/api/specialize':'/api/action',r.kind==='specialize'?r.args:{kind:r.kind,args:r.args},'추천 행동을 반영했습니다.');box.appendChild(b);
  }
}
function renderJourney(s){
  const months=s.completed?120:Math.max(0,Math.min(120,s.month_index));
  $('journey-label').textContent=`아스텔리아 육성 ${months} / 120개월`;
  $('journey-percent').textContent=`${(months/120*100).toFixed(1)}%`;
  $('journey-fill').style.width=`${months/120*100}%`;
  $('journey-track').setAttribute('aria-valuenow',String(months));
  $('ap-visual').textContent=`남은 AP ${s.ap_left} / 8`;
  $('slots-visual').textContent=`남은 행동 ${s.slots_left} / 4`;
}
function pct(v){return Math.max(0,Math.min(100,Number(v)||0))}
function meter(label,value){return `<div class="meter"><div class="journey-head"><span>${esc(label)}</span><span>${pct(value).toFixed(0)} / 100</span></div><div class="track"><i style="width:${pct(value)}%"></i></div></div>`}
function renderStats(s){
  $('stats').innerHTML=Object.entries(s.stats).map(([key,x])=>`<div class="stat-row"><span>${esc(x.name)}${s.specializations.includes(key)?' ★':''}</span><div class="bar"><i style="width:${Math.max(0,Math.min(100,x.value))}%"></i></div><span class="number">${x.value.toFixed(1)} / ${x.cap}</span></div>`).join('');
  const keys=[['자금',`${money(s.cash)} G`],['지구 준비',`${s.ear.toFixed(1)} / 100`],['스트레스',`${s.stress.toFixed(1)} / 100`],['행복도',`${s.happiness.toFixed(1)} / 100`],['자율성',`${s.autonomy.toFixed(1)} / 100`],['보호자 신뢰',`${s.trust.toFixed(1)} / 100`]];
  $('resources').innerHTML=keys.map(([k,v])=>`<div class="metric"><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join('');
  const sp=$('specialize');sp.innerHTML='';
  if(!s.completed&&s.age>=16&&s.specializations.length<2){
    const title=document.createElement('small');title.textContent=`전문화 슬롯 (${s.specializations.length}/2) · 능력치 상한 확대`;sp.appendChild(title);
    for(const [k,v] of Object.entries(s.stats))if(!s.specializations.includes(k)){
      const b=document.createElement('button');b.textContent=v.name+' 전문화';b.onclick=()=>mutate('/api/specialize',{stat:k},`${v.name} 전문화를 설정했습니다.`);sp.appendChild(b);
    }
  }else if(s.specializations.length){sp.innerHTML=`<small class="small">전문화: ${s.specializations.map(x=>esc(s.stats[x].name)).join(', ')}</small>`}
}
function renderNPCs(s){$('npcs').innerHTML=s.npcs.map(n=>`<div class="npc"><b>${esc(n.name)}</b><small>${esc(n.interest)}</small>${meter('호감',n.affinity)}${meter('신뢰',n.trust)}<small>갈등 ${n.conflict.toFixed(0)} · 친밀 ${n.intimacy.toFixed(0)}</small></div>`).join('')}

function renderStories(s){
  $('stories').innerHTML=s.stories.map(x=>`<div class="story"><b>${esc(x.name)} · ${esc(x.theme)}</b><small>진행 ${esc(x.chapter)}/3 · ${esc(x.branch_name)}</small>${x.next_scene?'<span class="ok">이번 달 새 장면이 열렸습니다.</span>':''}${x.outcome?`<p>${esc(x.outcome)}</p>`:''}</div>`).join('');
}
function reportHtml(r){return `<div class="year"><b>${r.age}세의 기록 · ${r.year}년 차</b><small>가장 성장한 능력: ${r.top_growth.map(t=>`${esc(t.name)} +${t.delta}`).join(', ')}</small><small>프로젝트 ${r.project_completed}건 · 생활 선택 ${r.life_event_choices}회 · NPC 교류 ${r.npc_visits}회</small><small>자금 변동 ${r.cash_delta>=0?'+':''}${money(r.cash_delta)} G · 지구 준비 +${r.ear_delta}</small><small>${r.notes.map(esc).join(' ')}</small></div>`}
function renderReports(s){$('reports').innerHTML=s.year_reports.length?s.year_reports.slice().reverse().slice(0,4).map(reportHtml).join('')+'<small class="small">전체 연말 리포트 '+s.year_reports.length+'개 저장됨</small>':'<p class="empty">12개월을 보내면 첫 성장 리포트가 열립니다.</p>'}
function renderHistory(s){$('history').innerHTML=s.recent_month_actions.length?s.recent_month_actions.map(a=>`<div class="entry">${esc(actionName(a))} · ${esc(a.id||a.npc||a.stat||a.hobby||a.facility||'')} · ${a.ap} AP${a.success?'':' · 판정 실패'}${a.score!==undefined?' · '+a.score+'점':''}</div>`).join(''):'<p class="empty">아직 이번 달의 선택이 없습니다.</p>'}
function renderActions(){
  const el=$('tabs');el.innerHTML='';
  for(let [key,name] of Object.entries(GROUPS)){
    const btn=document.createElement('button');btn.textContent=name;btn.className=key===group?'selected':'';btn.onclick=()=>{group=key;renderActions()};el.appendChild(btn);
  }
  const opts=options.map((x,i)=>({...x,source_index:i})).filter(x=>x.group===group);
  const filtered=$('show-locked').checked?opts:opts.filter(x=>x.usable);
  $('actions').innerHTML='';
  if(!filtered.length){$('actions').innerHTML=`<div class="empty">${game.completed?'아스텔리아에서의 육성이 완료되었습니다.':'이 분류에서 현재 실행 가능한 활동이 없습니다. 잠긴 활동 표시를 켜서 해금 조건을 확인하세요.'}</div>`;return}
  for(const a of filtered){
    const row=document.createElement('div');row.className='action'+(a.usable?'':' locked');
    const meta=`${a.ap} AP · ${a.pay?money(a.pay)+' G':'무료'}${a.score!==null?` · 예상 ${a.score}/${a.threshold}점`:''}`;
    const description=a.usable?(a.description|| (a.score!==null&&a.score<a.threshold?'합격 예상점에 미달합니다. 성공하지 못할 수 있습니다.':'')):
                          '해금 조건: '+a.lock_reasons.join(' / ');
    row.innerHTML=`<div><div class="title">${esc(a.label)}</div><div class="meta">${esc(meta)}</div>${description?`<div class="explain">${esc(description)}</div>`:''}</div>`;
    const b=document.createElement('button');b.textContent=a.usable?'선택':'잠김';b.disabled=!a.usable;
    b.onclick=()=>mutate('/api/action',{kind:a.kind,args:a.args},a.label+' 선택 완료');row.appendChild(b);
    $('actions').appendChild(row);
  }
}
function renderFinal(s){
  const p=$('end-panel');p.hidden=!s.completed;if(!s.completed)return;
  const selected=s.final?.selected;const social=s.final?.social_epilogue||{};
  p.innerHTML=`<div class="ending-summary">육성 완료 · 120 / 120개월 · 지구 이동 ${esc(s.transfer_count)}회</div><span class="tag">MANDATORY EARTH TRANSFER · AGE 20</span><h2>${selected?'엔딩: '+esc(selected.name):'등록된 48종 엔딩 미해금'}</h2>
    <p>20세의 지구 이동은 예외 없이 발생했습니다. ${selected?'아스텔리아에서의 선택을 토대로 지구에서의 긴 성장과 진로가 펼쳐집니다.':'아직 특정 직업·특수엔딩의 필수 조건을 충족하지 못했지만, 지구에서의 삶은 계속됩니다.'}</p>
    <p>기억에 남은 인연: ${esc(social.friendship_memory||'소중했던 사람들')} · 강한 우정 ${esc(social.lasting_bonds??0)}명</p>
    <small class="small">지구에서 마법을 직접 사용하지 않으며, 의료·법률 등 전문 자격은 지구에서 별도로 취득합니다.</small>`;
}
function resultSummary(result){
  if(!result||typeof result!=='object')return '<p>선택이 반영되었습니다.</p>';
  const names={success:'성공',score:'판정 점수',threshold:'요구 점수',ap:'사용 AP',cash:'자금',reason:'결과 사유',id:'활동 ID',reward:'보상',rewards:'보상',effects:'변화',completed:'완료'};
  const entries=Object.entries(result).filter(([k])=>!['story_result','year_report','ending'].includes(k));
  return '<dl class="result-details">'+entries.map(([k,v])=>'<div><dt>'+esc(names[k]||k)+'</dt><dd>'+esc(typeof v==='object'?JSON.stringify(v):typeof v==='boolean'?(v?'예':'아니오'):v)+'</dd></div>').join('')+'</dl>';
}
async function mutate(path,args,msg){
  try{
    const r=await request(path,args);if(r.state)game=r.state;await refresh();
    if(r.result?.story_result){const st=r.result.story_result;modal(`${st.npc} · ${st.title}`,`<p>${esc(st.opening)}</p><blockquote>${esc(st.choice)}</blockquote><p>${esc(st.aftermath)}</p><small>챕터 ${st.chapter}/3 · 선택에 따라 인연의 분기가 달라집니다.</small>`)}
    else if(r.result?.completed){modal('20세 · 지구로 향하는 날',`<p>아스텔리아의 120개월이 끝났습니다. 떠나는 운명은 바꿀 수 없지만, 떠난 이후의 삶은 달라질 수 있습니다.</p><p>${esc(r.result.ending?.selected?.name||'특정 엔딩 미해금')} · 지구에서 새로운 출발</p>`)}
    else if(r.result?.year_report){const y=r.result.year_report;modal(`${y.age}세 연말 성장 리포트`,reportHtml(y)+'<p class="subtle">지난 한 해의 행동과 결과를 요약했습니다.</p>')}
    else if(r.result?.reason==='score_failed')modal('행동 판정 결과',`<p>능력·조건 판정에 실패했습니다. 사용한 AP와 자금은 복구되지 않습니다.</p><p>다음 시도 전에 요구 능력치와 프로젝트 조건을 확인하세요.</p>`);
    else if(path==='/api/action' && ['project','event','life'].includes(args.kind))modal('선택 결과',`<p>${esc(msg||'선택이 반영되었습니다.')}</p>${resultSummary(r.result)}`);
    else toast(msg||'반영했습니다.');
  }catch(e){toast('실행할 수 없습니다: '+e.message)}
}
$('next').onclick=()=>mutate('/api/advance',{},'다음 달이 시작되었습니다.');
$('hint-mode').onchange=e=>mutate('/api/hint',{mode:e.target.value},'진로 힌트 설정을 변경했습니다.');
$('focus').onchange=e=>mutate('/api/focus',{focus:e.target.value},'진로 목표를 변경했습니다.');
$('show-locked').onchange=renderActions;
$('all-projects').onchange=async()=>{try{await refresh()}catch(e){toast(e.message)}};
$('save').onclick=async()=>{const slot=prompt('저장 슬롯 이름 (영문/숫자/밑줄, 최대 30자)','slot1');if(slot)try{await request('/api/save',{slot});toast(`${slot} 슬롯에 저장했습니다.`)}catch(e){toast(e.message)}};
$('load').onclick=async()=>{try{const s=await request('/api/slots');const slot=prompt('불러올 슬롯 이름\n저장된 슬롯: '+s.slots.join(', '),s.slots[0]||'slot1');if(slot)await mutate('/api/load',{slot},`${slot} 저장을 불러왔습니다.`)}catch(e){toast('저장 목록을 불러올 수 없습니다: '+e.message)}};
$('new').onclick=()=>{if(!confirm('현재 플레이 기록을 초기화하고 새 게임을 시작하시겠습니까? 필요하다면 먼저 슬롯에 저장하세요.'))return;mutate('/api/new',{focus:'J01',seed:20261029,economy:'standard'},'새 게임이 시작되었습니다.')};
$('close-modal').onclick=closeModal;
$('modal').onclick=e=>{if(e.target.id==='modal')closeModal()};
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!$('modal').hidden)closeModal();});
refresh().catch(e=>toast('서버에 접속할 수 없습니다: '+e.message));

// v1.4: non-blocking tutorial; never changes simulation resources or action rules.
const TUTORIAL_KEY='mgl_tutorial_skipped_v14';
let tutorialHidden=false, tutorialCollapsed=false;
try { tutorialHidden=localStorage.getItem(TUTORIAL_KEY)==='1'; } catch (_) {}
function setTutorialSkipped(skipped){
 tutorialHidden=skipped;
 try { localStorage.setItem(TUTORIAL_KEY,skipped?'1':'0'); } catch (_) {}
 if(game)renderTutorial(game);
 $('tutorial-restore').hidden=!skipped;
}
$('tutorial-restore').hidden=!tutorialHidden;
$('tutorial-restore').addEventListener('click',()=>setTutorialSkipped(false));
function renderTutorial(s){
 const box=$('onboarding');if(!box)return;
 box.hidden=tutorialHidden||s.completed||s.month_index>=24;
 if(box.hidden)return;
 const m=Math.max(0,Math.min(24,s.month_index));
 $('tutorial-progress').setAttribute('aria-valuenow',String(m));
 $('tutorial-progress').textContent=`첫 24개월 진행: ${m}/24개월`;
 $('tutorial-message').textContent=m<3?'첫 3개월: 교육·휴식·인연 활동을 둘러보세요.':m<12?'첫해: 진로 지도와 자금·스트레스의 변화를 확인하세요.':'둘째 해: 전문화 계획과 NPC 관계, 지구 적응 준비도를 점검하세요.';
 $('tutorial-checklist').hidden=tutorialCollapsed;
 $('tutorial-toggle').textContent=tutorialCollapsed?'펼치기':'접기';
 $('tutorial-toggle').setAttribute('aria-expanded',String(!tutorialCollapsed));
}
$('tutorial-toggle').addEventListener('click',()=>{tutorialCollapsed=!tutorialCollapsed;if(game)renderTutorial(game)});
$('tutorial-dismiss').addEventListener('click',()=>{setTutorialSkipped(true);toast('튜토리얼을 건너뛰었습니다. 상단에서 다시 볼 수 있습니다.');});
