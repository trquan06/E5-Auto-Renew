import {t} from './i18n.js';
export const $=(selector,root=document)=>root.querySelector(selector);
export const $$=(selector,root=document)=>[...root.querySelectorAll(selector)];
export function showOnly(id,...all){ all.forEach(name=>document.getElementById(name)?.classList.toggle('hidden',name!==id)); }
export function escapeHtml(value=''){ const node=document.createElement('div'); node.textContent=String(value); return node.innerHTML; }
export function toast(message,type='success'){ const el=document.createElement('div'); el.className=`toast ${type}`; el.textContent=message; $('#toast-region').append(el); setTimeout(()=>el.remove(),4200); }
export async function withButton(button,work){ const old=button.disabled; button.disabled=true; button.setAttribute('aria-busy','true'); try{return await work();}finally{button.disabled=old;button.removeAttribute('aria-busy');} }
export function confirmDialog(title,message){ const dialog=$('#confirm-dialog'); $('#confirm-title').textContent=title; $('#confirm-message').textContent=message; dialog.showModal(); return new Promise(resolve=>dialog.addEventListener('close',()=>resolve(dialog.returnValue==='confirm'),{once:true})); }
export function emptyState(title,text){return `<div class="empty-state"><strong>${escapeHtml(title)}</strong><span>${escapeHtml(text)}</span></div>`;}
export function errorMessage(error){ return error?.message||t('common.error'); }
export function skeletons(container,count=3){ container.innerHTML=Array.from({length:count},()=>'<div class="skeleton"></div>').join(''); }
