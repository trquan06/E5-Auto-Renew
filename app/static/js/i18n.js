import en from './i18n/en.js';
import vi from './i18n/vi.js';
import zhCN from './i18n/zh-CN.js';

const catalogs = { en, vi, 'zh-CN': zhCN };
let locale = localStorage.getItem('ms365.locale');
if (!catalogs[locale]) locale = navigator.language === 'vi' ? 'vi' : navigator.language.toLowerCase().startsWith('zh') ? 'zh-CN' : 'en';
const listeners = new Set();

export function t(key, values = {}) {
  let value = catalogs[locale][key] ?? catalogs.en[key] ?? key;
  for (const [name, replacement] of Object.entries(values)) value = value.replaceAll(`{${name}}`, String(replacement));
  return value;
}
export function getLocale(){ return locale; }
export function setLocale(next){ if(!catalogs[next]) return; locale=next; localStorage.setItem('ms365.locale',next); document.documentElement.lang=next; applyTranslations(); listeners.forEach(fn=>fn(next)); }
export function onLocaleChange(fn){ listeners.add(fn); return ()=>listeners.delete(fn); }
export function applyTranslations(root=document){
  root.querySelectorAll('[data-i18n]').forEach(el=>{ el.textContent=t(el.dataset.i18n); });
  root.querySelectorAll('[data-i18n-placeholder]').forEach(el=>{ el.placeholder=t(el.dataset.i18nPlaceholder); });
  root.querySelectorAll('[data-i18n-aria-label]').forEach(el=>{ el.setAttribute('aria-label',t(el.dataset.i18nAriaLabel)); });
  root.querySelectorAll('.locale-select').forEach(el=>{ el.value=locale; el.setAttribute('aria-label',t('common.language')); });
  root.querySelector('#sidebar')?.setAttribute('aria-label',t('a11y.primaryNavigation'));
  root.querySelector('#menu-button')?.setAttribute('aria-label',t('a11y.openNavigation'));
  root.querySelector('#theme-button')?.setAttribute('aria-label',t('a11y.toggleTheme'));
  root.querySelector('#activity-chart')?.setAttribute('aria-label',t('a11y.activityChart'));
  root.querySelectorAll('.dialog-close').forEach(el=>el.setAttribute('aria-label',t('a11y.close')));
  document.documentElement.lang=locale;
}
export function formatDate(value){ if(!value) return t('common.never'); const date=new Date(value); return Number.isNaN(date.valueOf())?t('common.never'):new Intl.DateTimeFormat(locale,{dateStyle:'medium',timeStyle:'short'}).format(date); }
export function formatNumber(value, options){ return new Intl.NumberFormat(locale,options).format(value ?? 0); }
