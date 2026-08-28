const TOKEN_KEY = 'ms365.accessToken';
export class ApiError extends Error { constructor(message, status, code){ super(message); this.status=status; this.code=code; } }
export const getToken=()=>localStorage.getItem(TOKEN_KEY);
export const setToken=(token)=>token?localStorage.setItem(TOKEN_KEY,token):localStorage.removeItem(TOKEN_KEY);
export async function request(path,{method='GET',body,auth=true}={}){
  const headers={Accept:'application/json'};
  if(body!==undefined) headers['Content-Type']='application/json';
  if(auth&&getToken()) headers.Authorization=`Bearer ${getToken()}`;
  const response=await fetch(path,{method,headers,body:body===undefined?undefined:JSON.stringify(body),credentials:'same-origin',cache:'no-store'});
  const contentType=response.headers.get('content-type')||'';
  const data=contentType.includes('application/json')?await response.json():null;
  if(!response.ok){ const detail=data?.detail; throw new ApiError(detail?.message||detail||data?.message||response.statusText,response.status,detail?.code||data?.code); }
  return data;
}
export const api={
  setupStatus:()=>request('/api/setup/status',{auth:false}), initialize:(body)=>request('/api/setup/initialize',{method:'POST',body,auth:false}),
  login:(password)=>request('/api/auth/login',{method:'POST',body:{password},auth:false}), authStatus:()=>request('/api/auth/status'), logout:()=>request('/api/auth/logout',{method:'POST'}),
  stats:()=>request('/api/logs/stats'), accounts:()=>request('/api/accounts'), updateAccount:(id,body)=>request(`/api/accounts/${id}`,{method:'PUT',body}), deleteAccount:(id)=>request(`/api/accounts/${id}`,{method:'DELETE'}), toggleAccount:(id)=>request(`/api/accounts/${id}/toggle`,{method:'POST'}), testAccount:(id)=>request(`/api/accounts/${id}/test`,{method:'POST'}), runAccount:(id)=>request(`/api/accounts/${id}/run-now`,{method:'POST'}),
  authorize:(params)=>request(`/api/accounts/oauth/authorize-url?${new URLSearchParams(params)}`), oauthCallback:(body)=>request('/api/accounts/oauth/callback',{method:'POST',body}),
  taskConfig:(id)=>request(`/api/accounts/${id}/config`), updateTaskConfig:(id,body)=>request(`/api/accounts/${id}/config`,{method:'PUT',body}),
  logs:(params)=>request(`/api/logs?${new URLSearchParams(params)}`), clearLogs:(days=30)=>request(`/api/logs/clear?days=${days}`,{method:'DELETE'}),
  settings:()=>request('/api/settings'), updateSettings:(body)=>request('/api/settings',{method:'PUT',body}), testNotifications:()=>request('/api/settings/test-notification',{method:'POST',body:{channel:'all'}}),
};
