import {t} from './i18n.js';
let chart;
export function renderActivityChart(canvas,rows=[]){
  if(chart) chart.destroy();
  if(!window.Chart) return;
  const style=getComputedStyle(document.documentElement);
  chart=new window.Chart(canvas,{type:'bar',data:{labels:rows.map(x=>x.date),datasets:[{label:t('dashboard.chartSuccess'),data:rows.map(x=>x.success),backgroundColor:'#22c55e',borderRadius:5},{label:t('dashboard.chartFailed'),data:rows.map(x=>x.failed),backgroundColor:'#ef4444',borderRadius:5}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{stacked:true,grid:{display:false},ticks:{color:style.getPropertyValue('--muted')}},y:{stacked:true,beginAtZero:true,ticks:{precision:0,color:style.getPropertyValue('--muted')},grid:{color:style.getPropertyValue('--line')}}}}});
}
