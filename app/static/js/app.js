import {api,setToken,ApiError} from './api.js';
import {applyTranslations,formatDate,formatNumber,onLocaleChange,setLocale,t} from './i18n.js';
import {$,$$,confirmDialog,emptyState,errorMessage,escapeHtml,showOnly,skeletons,toast,withButton} from './ui.js';
import {renderActivityChart} from './charts.js';

let currentPage='dashboard', logPage=1, lastStats=null, accounts=[];
const screens=['boot-screen','setup-screen','login-screen','app-shell'];
const screen=id=>showOnly(id,...screens);
function authFailure(error){if(error instanceof ApiError&&error.status===401){setToken(null);screen('login-screen');toast(t('login.expired'),'error');return true}return false}

async function boot(){
  applyTranslations();
  document.documentElement.dataset.theme=localStorage.getItem('ms365.theme')||'light';
  try{
    const state=await api.setupStatus();
    if(!state.is_initialized){screen('setup-screen');return}
    try{const auth=await api.authStatus();auth.is_authenticated?openApp():screen('login-screen')}catch{screen('login-screen')}
  }catch(error){screen('login-screen');$('#login-error').textContent=errorMessage(error)}
}
function openApp(){screen('app-shell');navigate('dashboard')}
async function submitSetup(event){
  event.preventDefault();
  const password=$('#setup-password').value;
  if(password!==$('#setup-password-confirm').value){$('#setup-error').textContent=t('setup.mismatch');return}
  await withButton(event.submitter,async()=>{try{await api.initialize({setup_code:$('#setup-code').value.trim(),password});toast(t('setup.complete'));screen('login-screen')}catch(error){$('#setup-error').textContent=errorMessage(error)}});
}
async function submitLogin(event){
  event.preventDefault();
  await withButton(event.submitter,async()=>{try{const result=await api.login($('#login-password').value);setToken(result.access_token);$('#login-error').textContent='';openApp()}catch(error){$('#login-error').textContent=error.status===401?t('login.invalid'):errorMessage(error)}});
}
async function logout(){try{await api.logout()}finally{setToken(null);screen('login-screen')}}

function navigate(page){
  currentPage=page;
  $$('.page').forEach(el=>el.classList.toggle('active',el.id===`page-${page}`));
  $$('.nav-item').forEach(el=>el.classList.toggle('active',el.dataset.page===page));
  $('#page-title').textContent=t(`nav.${page}`);
  $('#sidebar').classList.remove('open');$('#menu-button').setAttribute('aria-expanded','false');
  loadPage(page);$('#main-content').focus();
}
async function loadPage(page){try{if(page==='dashboard')await loadDashboard();if(page==='accounts')await loadAccounts();if(page==='logs')await loadLogs();if(page==='settings')await loadSettings()}catch(error){if(!authFailure(error))toast(errorMessage(error),'error')}}

function metric(label,value,detail=''){return `<article class="metric-card"><span class="metric-label">${escapeHtml(label)}</span><strong class="metric-value">${escapeHtml(value)}</strong><span class="metric-detail">${escapeHtml(detail)}</span></article>`}
async function loadDashboard(){
  skeletons($('#stats-grid'),4);lastStats=await api.stats();const s=lastStats;
  $('#stats-grid').innerHTML=[metric(t('dashboard.totalAccounts'),formatNumber(s.total_accounts),`${formatNumber(s.active_accounts)} ${t('common.enabled').toLowerCase()}`),metric(t('dashboard.activeAccounts'),formatNumber(s.active_accounts)),metric(t('dashboard.totalCalls'),formatNumber(s.total_calls),t('dashboard.calls24h',{count:formatNumber(s.calls_last_24h)})),metric(t('dashboard.successRate'),formatNumber(s.success_rate,{maximumFractionDigits:1})+'%')].join('');
  $('#scheduler-card').innerHTML=`<div class="scheduler-state"><span class="scheduler-icon">◷</span><div><strong>${s.scheduler_running?t('common.running'):t('common.stopped')}</strong><p class="muted">${s.scheduler_running?t('dashboard.schedulerActive'):t('dashboard.schedulerStopped')}</p></div></div><span class="metric-label">${t('dashboard.nextRun')}</span><strong class="metric-value">${escapeHtml(formatDate(s.next_run_at))}</strong>`;
  renderActivityChart($('#activity-chart'),s.daily_stats);
  $('#recent-list').innerHTML=s.recent_logs.length?s.recent_logs.map(activityRow).join(''):emptyState(t('common.noData'),t('dashboard.noRecent'));
}
function activityRow(row){return `<div class="activity-row"><span class="activity-icon">${row.is_success?'✓':'!'}</span><div><strong>${escapeHtml(row.account_name)}</strong><div class="activity-meta">${escapeHtml(row.task_type)} · ${escapeHtml(formatDate(row.created_at))}</div></div><span class="badge ${row.is_success?'success':'failed'}">${t(row.is_success?'common.success':'common.failed')}</span></div>`}

async function loadAccounts(){const container=$('#accounts-list');skeletons(container,3);accounts=await api.accounts();container.innerHTML=accounts.length?accounts.map(accountCard).join(''):emptyState(t('accounts.emptyTitle'),t('accounts.emptyText'))}
function accountCard(a){
  const active=a.status==='active';
  return `<article class="account-card"><div class="account-head"><span class="account-avatar">${escapeHtml((a.name||'M')[0].toUpperCase())}</span><div><h3>${escapeHtml(a.name)}</h3><p>${escapeHtml(a.email||a.tenant_id)}</p></div><span class="badge ${active?'success':''}">${escapeHtml(a.status)}</span></div><div class="account-data"><div><span>${t('accounts.lastRun')}</span><strong>${escapeHtml(formatDate(a.last_run_at))}</strong></div><div><span>${t('accounts.nextRun')}</span><strong>${escapeHtml(formatDate(a.task_config?.next_run_at))}</strong></div></div><div class="account-actions"><button class="btn btn-secondary" data-account-action="config" data-id="${a.id}">${t('accounts.configure')}</button><button class="btn btn-secondary" data-account-action="run" data-id="${a.id}">${t('accounts.runNow')}</button><button class="btn btn-secondary" data-account-action="test" data-id="${a.id}">${t('accounts.test')}</button><button class="btn btn-quiet" data-account-action="toggle" data-id="${a.id}">${t(active?'accounts.disable':'accounts.enable')}</button><button class="btn btn-danger" data-account-action="delete" data-id="${a.id}">${t('accounts.delete')}</button></div></article>`;
}
async function accountAction(event){
  const button=event.target.closest('[data-account-action]');if(!button)return;
  const id=Number(button.dataset.id),action=button.dataset.accountAction;
  await withButton(button,async()=>{try{
    if(action==='config')return openConfig(id);
    if(action==='run'){await api.runAccount(id);toast(t('accounts.runStarted'))}
    if(action==='test'){await api.testAccount(id);toast(t('accounts.testPassed'))}
    if(action==='toggle'){await api.toggleAccount(id);await loadAccounts()}
    if(action==='delete'&&await confirmDialog(t('accounts.deleteTitle'),t('accounts.deleteMessage'))){await api.deleteAccount(id);toast(t('accounts.deleted'));await loadAccounts()}
  }catch(error){if(!authFailure(error))toast(errorMessage(error),'error')}});
}
async function openConfig(id){try{const config=await api.taskConfig(id),form=$('#config-form');for(const [key,value] of Object.entries(config)){const field=form.elements.namedItem(key);if(!field)continue;if(field.type==='checkbox')field.checked=Boolean(value);else field.value=value??''}$('#config-error').textContent='';$('#config-dialog').showModal()}catch(error){toast(errorMessage(error),'error')}}
async function submitConfig(event){
  event.preventDefault();const f=event.currentTarget,e=f.elements;
  if(Number(e.jitter_min_minutes.value)>Number(e.jitter_max_minutes.value)){ $('#config-error').textContent=t('accounts.invalidVariance');return}
  const body={interval_hours:Number(e.interval_hours.value),jitter_min_minutes:Number(e.jitter_min_minutes.value),jitter_max_minutes:Number(e.jitter_max_minutes.value),active_hour_start:Number(e.active_hour_start.value),active_hour_end:Number(e.active_hour_end.value),timezone:e.timezone.value};
  ['mail','calendar','todo','teams','onedrive','onenote','profile'].forEach(x=>body[`enable_${x}`]=e[`enable_${x}`].checked);
  await withButton(event.submitter,async()=>{try{await api.updateTaskConfig(e.account_id.value,body);$('#config-dialog').close();toast(t('accounts.updated'));await loadAccounts()}catch(error){$('#config-error').textContent=errorMessage(error)}});
}

async function submitAccount(event){
  event.preventDefault();const form=new FormData(event.currentTarget),payload=Object.fromEntries(form.entries());
  await withButton(event.submitter,async()=>{try{
    const auth=await api.authorize({client_id:payload.client_id,tenant_id:payload.tenant_id,account_name:payload.name});
    const popup=window.open(auth.auth_url,'ms365-oauth','popup,width=560,height=720');if(!popup)throw new Error(t('accounts.oauthBlocked'));
    toast(t('accounts.oauthWaiting'));const result=await waitForOAuth(popup);
    await api.oauthCallback({code:result.code,state:result.state,client_secret:payload.client_secret||null});result.code='';
    $('#account-dialog').close();event.currentTarget.reset();event.currentTarget.elements.tenant_id.value='common';toast(t('accounts.connected'));await loadAccounts();
  }catch(error){$('#account-error').textContent=errorMessage(error)}});
}
function waitForOAuth(popup){
  return new Promise((resolve,reject)=>{
    const timeout=setTimeout(done,5*60*1000);const closed=setInterval(()=>{if(popup.closed)done()},700);
    function message(event){if(event.origin!==location.origin||event.source!==popup||event.data?.type!=='ms365-oauth-callback')return;cleanup();if(event.data.error)reject(new Error(event.data.error));else resolve({code:event.data.code,state:event.data.state})}
    function cleanup(){clearTimeout(timeout);clearInterval(closed);window.removeEventListener('message',message)}function done(){cleanup();reject(new Error(t('common.error')))}window.addEventListener('message',message);
  });
}

async function loadLogs(){
  const params={page:String(logPage),page_size:'20'};if($('#log-task').value)params.task_type=$('#log-task').value;if($('#log-result').value)params.is_success=$('#log-result').value;
  const data=await api.logs(params),body=$('#logs-body');
  body.innerHTML=data.items.length?data.items.map(x=>`<tr><td>${escapeHtml(formatDate(x.created_at))}</td><td>${escapeHtml(x.account_name)}</td><td>${escapeHtml(x.task_type)}</td><td title="${escapeHtml(x.endpoint)}">${escapeHtml(x.method)} ${escapeHtml(x.endpoint)}</td><td><span class="badge ${x.is_success?'success':'failed'}">${x.status_code||'—'}</span></td><td>${escapeHtml(t('common.ms',{value:formatNumber(x.duration_ms)}))}</td></tr>`).join(''):`<tr><td colspan="6">${emptyState(t('common.noData'),t('logs.empty'))}</td></tr>`;
  $('#logs-pagination').innerHTML=`<button class="btn btn-secondary" data-log-page="${Math.max(1,data.page-1)}" ${data.page<=1?'disabled':''}>${t('common.previous')}</button><span>${t('common.page',{page:data.page,total:data.total_pages})}</span><button class="btn btn-secondary" data-log-page="${Math.min(data.total_pages,data.page+1)}" ${data.page>=data.total_pages?'disabled':''}>${t('common.next')}</button>`;
}
async function clearLogs(){if(await confirmDialog(t('logs.clearTitle'),t('logs.clearMessage'))){await api.clearLogs();toast(t('logs.cleared'));loadLogs()}}
async function loadSettings(){const data=await api.settings(),form=$('#settings-form');form.elements.telegram_bot_token.placeholder=data.telegram_bot_token||'';form.elements.telegram_chat_id.value=data.telegram_chat_id||'';form.elements.discord_webhook_url.placeholder=data.discord_webhook_url||'';form.elements.telegram_bot_token.value='';form.elements.discord_webhook_url.value=''}
async function submitSettings(event){event.preventDefault();const data=new FormData(event.currentTarget),body={};for(const [key,value] of data.entries())if(value)body[key]=value;await withButton(event.submitter,async()=>{try{await api.updateSettings(body);event.currentTarget.elements.webui_password.value='';toast(t('common.saved'));await loadSettings()}catch(error){toast(errorMessage(error),'error')}})}

function bind(){
  document.addEventListener('change',event=>{if(event.target.matches('.locale-select'))setLocale(event.target.value)});
  $('#setup-form').addEventListener('submit',submitSetup);$('#login-form').addEventListener('submit',submitLogin);$('#logout-button').addEventListener('click',logout);
  $$('.nav-item').forEach(x=>x.addEventListener('click',()=>navigate(x.dataset.page)));$$('[data-go]').forEach(x=>x.addEventListener('click',()=>navigate(x.dataset.go)));$$('.refresh-button').forEach(x=>x.addEventListener('click',()=>loadPage(x.dataset.target)));
  $('#menu-button').addEventListener('click',()=>{const open=$('#sidebar').classList.toggle('open');$('#menu-button').setAttribute('aria-expanded',String(open))});
  $('#theme-button').addEventListener('click',()=>{const next=document.documentElement.dataset.theme==='dark'?'light':'dark';document.documentElement.dataset.theme=next;localStorage.setItem('ms365.theme',next);if(lastStats)renderActivityChart($('#activity-chart'),lastStats.daily_stats)});
  $('#add-account-button').addEventListener('click',()=>{$('#account-error').textContent='';$('#account-dialog').showModal()});$$('.dialog-close').forEach(x=>x.addEventListener('click',()=>x.closest('dialog').close()));
  $('#account-form').addEventListener('submit',submitAccount);$('#config-form').addEventListener('submit',submitConfig);$('#accounts-list').addEventListener('click',accountAction);
  $('#log-filters').addEventListener('submit',event=>{event.preventDefault();logPage=1;loadLogs()});$('#logs-pagination').addEventListener('click',event=>{const b=event.target.closest('[data-log-page]');if(b&&!b.disabled){logPage=Number(b.dataset.logPage);loadLogs()}});$('#clear-logs-button').addEventListener('click',clearLogs);
  $('#settings-form').addEventListener('submit',submitSettings);$('#test-notification-button').addEventListener('click',async event=>withButton(event.currentTarget,async()=>{try{await api.testNotifications();toast(t('settings.testSent'))}catch(error){toast(errorMessage(error),'error')}}));
  onLocaleChange(()=>{if(currentPage)navigate(currentPage)});
}
bind();boot();
