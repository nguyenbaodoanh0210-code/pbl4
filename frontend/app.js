const app=document.querySelector('#app');
const authScreen=document.querySelector('#auth-screen');
const appShell=document.querySelector('.app-shell');
const nav=[...document.querySelectorAll('.nav-item')];
const s={page:'home',greenhouses:[],devices:[],logs:{},recommendations:[],greenhouseId:localStorage.getItem('ln-greenhouse')||'',deviceId:'',metric:'soil_moisture',period:'day',detailId:'',error:'',token:sessionStorage.getItem('ln-access-token')||'',user:null,profileMode:'info',authPage:'login',authError:'',authValues:{},sessionError:''};
const metrics=[['temperature','Nhiệt độ','°C','temperature'],['humidity','Độ ẩm không khí','%','humidity'],['soil_moisture','Độ ẩm đất','%','soil_moisture'],['soil_pH','pH','','soil_pH'],['N','Nitơ (N)','mg/kg','N'],['P','Photpho (P)','mg/kg','P'],['K','Kali (K)','mg/kg','K']];
const metricIcons={
  temperature:'<rect x="9" y="2" width="6" height="14" rx="3"/><circle cx="12" cy="18" r="4"/><path d="M12 8v10"/><circle cx="12" cy="18" r="1.5" fill="currentColor" stroke="none"/>',
  humidity:'<path d="M12 2c-1.7 2.3-4.2 5.2-4.2 7.7a4.2 4.2 0 0 0 8.4 0C16.2 7.2 13.7 4.3 12 2Z"/><path d="M5.3 13.5c-1.2 1.6-2.3 3.1-2.3 4.4a2.3 2.3 0 0 0 4.6 0c0-1.3-1.1-2.8-2.3-4.4ZM18.7 13.5c-1.2 1.6-2.3 3.1-2.3 4.4a2.3 2.3 0 0 0 4.6 0c0-1.3-1.1-2.8-2.3-4.4Z"/>',
  soil_moisture:'<path d="M3 15.5c3-1.5 5.5-1.5 8 0s5.5 1.5 10 0M3 19.5c3-1.5 5.5-1.5 8 0s5.5 1.5 10 0"/><path d="M6 2.5c-1 1.3-1.8 2.5-1.8 3.4a1.8 1.8 0 0 0 3.6 0C7.8 5 7 3.8 6 2.5ZM12 5.5c-1 1.3-1.8 2.5-1.8 3.4a1.8 1.8 0 0 0 3.6 0c0-.9-.8-2.1-1.8-3.4ZM18 2.5c-1 1.3-1.8 2.5-1.8 3.4a1.8 1.8 0 0 0 3.6 0c0-.9-.8-2.1-1.8-3.4Z"/>',
  soil_pH:'<path d="M3 17a9 9 0 0 1 18 0H3ZM12 17l4-5"/><circle cx="12" cy="17" r="1.3" fill="currentColor" stroke="none"/><text x="12" y="23" text-anchor="middle" font-size="6.5" font-weight="700" fill="currentColor" stroke="none">pH</text>'
};
function metricIcon(name){return metricIcons[name]?'<svg viewBox="0 0 24 24" focusable="false" aria-hidden="true">'+metricIcons[name]+'</svg>':esc(name)}
const pages={home:['Tổng quan','Vườn hôm nay'],history:['Lịch sử quan trắc','Theo dõi dữ liệu'],greenhouses:['Nhà kính của bạn','Danh sách'],advice:['Gợi ý chăm sóc','Khuyến nghị'],alerts:['Thông báo','Theo dõi sự cố']};
const routeFields=['page','detailId','creatingGreenhouse','greenhouseId','deviceId','metric','period','authPage'];
function routeSnapshot(){return Object.fromEntries(routeFields.map(key=>[key,s[key]]))}
function readRoute(){
  const query=new URLSearchParams(location.search);
  return {page:query.get('page')||'home',detailId:query.get('detail')||'',creatingGreenhouse:query.get('create')==='1',greenhouseId:query.get('gh')||'',deviceId:query.get('device')||'',metric:query.get('metric')||'soil_moisture',period:query.get('period')||'day',authPage:query.get('auth')||'login'};
}
function applyRoute(route){
  const page=Object.hasOwn(pages,route.page)?route.page:'home';
  s.page=page;s.detailId=page==='greenhouses'&&s.greenhouses.some(h=>h.greenhouse_id===route.detailId)?route.detailId:'';
  s.creatingGreenhouse=page==='greenhouses'&&Boolean(route.creatingGreenhouse);
  s.greenhouseId=s.greenhouses.some(h=>h.greenhouse_id===route.greenhouseId)?route.greenhouseId:s.greenhouses[0]?.greenhouse_id||'';
  s.deviceId=s.devices.some(d=>d.device_id===route.deviceId&&d.greenhouse_id===s.greenhouseId)?route.deviceId:'';
  s.metric=metrics.some(m=>m[0]===route.metric)?route.metric:'soil_moisture';
  s.period=['hour','day','week','month'].includes(route.period)?route.period:'day';
  s.authPage=['login','register','forgot'].includes(route.authPage)?route.authPage:'login';
  if(s.detailId)s.greenhouseId=s.detailId;
}
function routeUrl(route=routeSnapshot()){
  const url=new URL(location.href);const query=new URLSearchParams();
  if(!s.user){if(route.authPage!=='login')query.set('auth',route.authPage)}
  else{
    if(route.page!=='home')query.set('page',route.page);
    if(route.detailId)query.set('detail',route.detailId);
    if(route.creatingGreenhouse)query.set('create','1');
    if(route.greenhouseId)query.set('gh',route.greenhouseId);
    if(route.deviceId)query.set('device',route.deviceId);
    if(route.metric!=='soil_moisture')query.set('metric',route.metric);
    if(route.period!=='day')query.set('period',route.period);
  }
  url.search=query.toString();return url.pathname+url.search+url.hash;
}
function writeRoute(replace=false){
  const route=routeSnapshot(),url=routeUrl(route),method=replace||url===location.pathname+location.search+location.hash?'replaceState':'pushState';
  window.history[method]({greenhouseRoute:route},'',url);
}
function navigateRoute(update,{replace=false,scroll=true}={}){
  update();writeRoute(replace);render();if(scroll)window.scrollTo(0,0);
}
window.addEventListener('popstate',event=>{
  applyRoute(event.state?.greenhouseRoute||readRoute());s.greenhouseNotice='';setProfileOpen(false);render();
});
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=(v,d=1)=>v==null||!Number.isFinite(Number(v))?'—':new Intl.NumberFormat('vi-VN',{maximumFractionDigits:d}).format(Number(v));
const date=v=>v?new Intl.DateTimeFormat('vi-VN',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit',timeZone:'Asia/Ho_Chi_Minh'}).format(new Date(v)):'Chưa có dữ liệu';
const gh=()=>s.greenhouses.find(x=>x.greenhouse_id===s.greenhouseId)||s.greenhouses[0]||null;
const devices=(id=gh()?.greenhouse_id)=>s.devices.filter(x=>x.greenhouse_id===id);
const dev=()=>devices().find(x=>x.device_id===s.deviceId)||devices()[0]||null;
const latest=id=>s.logs[id]?.[0]||null;
async function api(path,opts={}){const headers={Accept:'application/json',...(opts.body?{'Content-Type':'application/json'}:{}),...(s.token?{Authorization:'Bearer '+s.token}:{}),...opts.headers};const r=await fetch(path,{...opts,headers});if(!r.ok){let m='API trả về lỗi '+r.status;try{const j=await r.json();if(typeof j.detail==='string')m=j.detail}catch{}const error=new Error(m);error.status=r.status;throw error}return r.status===204?null:r.json()}
function clearSession(){s.creatingGreenhouse=false;s.greenhouseNotice='';s.token='';s.user=null;s.greenhouses=[];s.devices=[];s.logs={};s.recommendations=[];s.greenhouseId='';s.deviceId='';s.detailId='';sessionStorage.removeItem('ln-access-token');localStorage.removeItem('ln-greenhouse')}
async function load(){if(!s.user){render();return}app.innerHTML='<div class="loading-page"><span class="spinner"></span><p>Đang tải dữ liệu từ API…</p></div>';s.error='';try{const [g,d,r]=await Promise.all([api('/api/greenhouses'),api('/api/devices'),api('/api/recommendations?limit=100')]);s.greenhouses=Array.isArray(g)?g:[];s.devices=Array.isArray(d)?d:[];s.recommendations=Array.isArray(r)?r:[];if(!s.greenhouses.some(x=>x.greenhouse_id===s.greenhouseId))s.greenhouseId=s.greenhouses[0]?.greenhouse_id||'';if(s.greenhouseId)localStorage.setItem('ln-greenhouse',s.greenhouseId);await Promise.all(s.devices.map(async x=>{try{s.logs[x.device_id]=await api('/api/sensors/'+encodeURIComponent(x.device_id)+'?limit=100')}catch{s.logs[x.device_id]=[]}}));s.error=''}catch(e){if(e.status===401||e.status===403){clearSession();s.profileMode='info';s.sessionError='Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.';s.error='';s.authPage='login';writeRoute(true)}else{s.error=e.message}}render()}
function picker(){return s.greenhouses.length?'<div class="greenhouse-picker"><label class="field-label" for="gh">Nhà kính đang xem</label><div class="select-wrap greenhouse-select"><select id="gh" class="select">'+s.greenhouses.map(x=>'<option value="'+esc(x.greenhouse_id)+'" '+(x.greenhouse_id===gh()?.greenhouse_id?'selected':'')+'>'+esc(x.name)+(x.location?' · '+esc(x.location):'')+'</option>').join('')+'</select></div></div>':'<div class="card empty">Chưa có nhà kính trong API.</div>'}
function pill(t,k=''){return '<span class="status-pill '+k+'"><span class="status-icon" aria-hidden="true">●</span>'+esc(t)+'</span>'}
function locked(t){return '<div class="banner">▣ '+esc(t)+' cần xác minh API quản trị. Frontend không lưu hoặc gửi token quản trị.</div><button class="primary-button" disabled>▣ '+esc(t)+' · Chưa khả dụng</button>'}
function metricCard(m,v){return '<div class="metric"><div class="metric-label"><span class="metric-icon" aria-hidden="true">'+metricIcon(m[3])+'</span><span>'+m[1]+'</span></div><div class="metric-value">'+fmt(v)+'<span class="metric-unit">'+m[2]+'</span></div></div>'}
function banner(d,l){if(!d)return '<div class="banner warning">Chưa có thiết bị liên kết với nhà kính này.</div>';if(!l)return '<div class="banner warning">Thiết bị '+esc(d.device_id)+' chưa có bản ghi cảm biến.</div>';return d.is_online?'<div class="banner">Thiết bị đang gửi dữ liệu · cập nhật '+date(l.timestamp)+'.</div>':'<div class="banner danger">Thiết bị ngoại tuyến theo trạng thái API. Bản ghi gần nhất: '+date(l.timestamp)+'.</div>'}
function home(){
  const h=gh(),d=dev(),l=d&&latest(d.device_id);
  if(!h)return '<div class="card empty empty-state">Thêm nhà kính đầu tiên để bắt đầu theo dõi khu vườn của bạn.</div><div class="management-notice">'+addGreenhouseButton()+'</div>';
  return `<div class="page-toolbar"><div class="garden-picker">${picker()}</div><div class="toolbar-note">${banner(d,l)}</div></div>
    <section class="dashboard-overview"><div class="section-heading"><h2>Không gian trồng, trong tầm mắt.</h2><span>${date(l?.timestamp)}</span></div>
    <div class="metric-grid">${metrics.slice(0,4).map(m=>metricCard(m,l?.[m[0]])).join('')}</div></section>
    <div class="dashboard-grid">
      <section class="card nutrient-card"><div class="card-title">Dinh dưỡng trong đất</div><div class="nutrient-row">${metrics.slice(4).map(m=>'<div class="nutrient"><b>'+fmt(l?.[m[0]],0)+'</b><small>'+m[1]+' · '+m[2]+'</small></div>').join('')}</div><p class="tiny">${l?'Dữ liệu từ bản ghi '+date(l.timestamp)+'.':'Chưa có số đo để hiển thị.'}</p></section>
      <section class="card device-summary"><div class="card-title">Thiết bị đang theo dõi</div>${d?'<div class="row"><span>'+esc(d.device_id)+' · '+esc(d.device_type||'Cảm biến')+'</span>'+pill(d.is_online?'Đang kết nối':'Ngoại tuyến',d.is_online?'':'offline')+'</div><p class="tiny">Trạng thái quản lý: '+esc(d.status||'—')+'</p>':'<p class="tiny">Chưa có thiết bị.</p>'}<button class="link-button" data-page="history">Xem lịch sử quan trắc →</button></section>
      <section class="card care-card"><div class="card-title">Kiểm tra và chăm sóc</div><ol class="steps"><li>Kiểm tra kết nối và thời điểm gửi dữ liệu.</li><li>Đối chiếu số đo với tình trạng thực tế.</li><li>Đọc khuyến nghị trước khi quyết định chăm sóc.</li></ol><button class="link-button" data-page="advice">Mở gợi ý chăm sóc →</button></section>
    </div>`;
}
function getPeriodLogs(){const d=dev();if(!d)return[];const span={hour:3600000,day:86400000,week:604800000,month:2592000000}[s.period];return(s.logs[d.device_id]||[]).filter(x=>Date.parse(x.timestamp)>=Date.now()-span).slice().sort((a,b)=>Date.parse(a.timestamp)-Date.parse(b.timestamp))}
function drawChart(rows,m){const valid=rows.filter(x=>Number.isFinite(Number(x[m[0]])));if(valid.length<2)return '<div class="empty">Cần ít nhất hai điểm đo để vẽ biểu đồ.</div>';const a=valid.map(x=>Number(x[m[0]])),lo=Math.min(...a),span=Math.max(...a)-lo||1,pts=a.map((v,i)=>[35+i*290/(a.length-1),120-(v-lo)*90/span]),path=pts.map((p,i)=>(i?'L':'M')+p[0].toFixed(1)+','+p[1].toFixed(1)).join(' ');return '<svg class="chart" viewBox="0 0 340 160" role="img" aria-label="Biểu đồ '+esc(m[1])+'"><line class="grid" x1="30" y1="28" x2="330" y2="28"/><line class="grid" x1="30" y1="73" x2="330" y2="73"/><line class="grid" x1="30" y1="118" x2="330" y2="118"/><text x="0" y="31">'+fmt(lo+span)+'</text><text x="0" y="76">'+fmt(lo+span/2)+'</text><text x="0" y="121">'+fmt(lo)+'</text><path class="line" d="'+path+'"/><circle class="dot" cx="'+pts.at(-1)[0]+'" cy="'+pts.at(-1)[1]+'" r="3.5"/></svg>'}
function history(){
  if(!dev())return '<div class="page-toolbar"><div class="garden-picker">'+picker()+'</div></div><div class="card empty empty-state">Chưa có thiết bị để truy vấn lịch sử.</div>';
  const rows=getPeriodLogs(),m=metrics.find(x=>x[0]===s.metric)||metrics[2],periods=[['hour','Giờ'],['day','Ngày'],['week','Tuần'],['month','Tháng']];
  const values=rows.map(x=>x[m[0]]).filter(x=>x!=null&&Number.isFinite(Number(x))).map(Number);
  return `<div class="history-layout"><section class="history-main"><div class="page-toolbar"><div class="garden-picker">${picker()}</div><div class="segmented">${periods.map(x=>'<button data-period="'+x[0]+'" class="'+(s.period===x[0]?'selected':'')+'">'+x[1]+'</button>').join('')}</div></div>
    <div class="section-heading"><h2>Diễn biến quan trắc</h2><span>${rows.length} bản ghi</span></div><div class="tabs-chip">${metrics.map(x=>'<button class="chip '+(s.metric===x[0]?'selected':'')+'" data-metric="'+x[0]+'">'+x[1]+'</button>').join('')}</div>
    ${rows.length?'<div class="card chart-card"><div class="card-title">'+m[1]+'</div><div class="tiny">'+date(rows[0].timestamp)+' — '+date(rows.at(-1).timestamp)+'</div>'+drawChart(rows,m)+'<div class="row"><span>Số đo mới nhất</span><strong>'+fmt(rows.at(-1)[m[0]])+' '+m[2]+'</strong></div></div>':'<div class="card empty empty-state">Chưa có lịch sử quan trắc trong khoảng thời gian này.</div>'}</section>
    <aside class="history-aside"><section class="card history-filters"><div class="card-title">Nguồn dữ liệu</div><label for="device" class="field-label">Thiết bị quan trắc</label><div class="select-wrap"><select id="device" class="select">${devices().map(x=>'<option value="'+esc(x.device_id)+'" '+(x.device_id===dev().device_id?'selected':'')+'>'+esc(x.device_id)+'</option>').join('')}</select></div><p class="tiny">${esc(gh()?.name)} · ${esc(gh()?.location||'Chưa có vị trí')}</p>${pill(dev().is_online?'Đang kết nối':'Ngoại tuyến',dev().is_online?'':'offline')}</section>
    <section class="card history-summary"><div class="card-title">Trong khoảng đã chọn</div><div class="row"><span>Thấp nhất</span><strong>${values.length?fmt(Math.min(...values)):'—'} ${m[2]}</strong></div><div class="row"><span>Cao nhất</span><strong>${values.length?fmt(Math.max(...values)):'—'} ${m[2]}</strong></div><p class="tiny">${m[1]} · ${rows.length} bản ghi đã lưu</p></section><button class="secondary-button" data-action="refresh">↻ &nbsp;Tải lại dữ liệu</button></aside></div>`;
}
function addGreenhouseButton(){return '<button type="button" class="primary-button add-greenhouse-button" data-action="add-greenhouse">Thêm nhà kính</button>'}
function greenhouseForm(){
  return `<section class="greenhouse-create" aria-labelledby="greenhouse-form-title">
    <div class="greenhouse-form-intro"><h2 id="greenhouse-form-title">Thông tin nhà kính</h2><p>Đặt tên và ghi lại vị trí để dễ quản lý không gian trồng của bạn.</p><p>Dấu * là thông tin bắt buộc.</p></div>
    <form id="greenhouse-form" class="greenhouse-form">
      <fieldset><legend class="visually-hidden">Thông tin nhà kính mới</legend>
        <label for="greenhouse-name">Tên nhà kính *<input id="greenhouse-name" name="name" maxlength="100" required autocomplete="off" placeholder="Ví dụ: Nhà kính rau xanh"></label>
        <label for="greenhouse-code">Mã nhà kính *<input id="greenhouse-code" name="greenhouse_id" maxlength="50" required autocomplete="off" spellcheck="false" aria-describedby="greenhouse-code-hint" placeholder="Ví dụ: NK-01"><small id="greenhouse-code-hint">Mã duy nhất để nhận diện nhà kính, không trùng với mã đã có.</small></label>
        <label for="greenhouse-location">Vị trí<input id="greenhouse-location" name="location" maxlength="255" autocomplete="off" placeholder="Ví dụ: Khu A, Đà Lạt"></label>
        <label for="greenhouse-area">Diện tích (m²)<input id="greenhouse-area" name="area_sqm" type="number" min="0" step="any" inputmode="decimal" placeholder="Ví dụ: 120"><small>Nếu nhập, diện tích phải lớn hơn 0.</small></label>
      </fieldset>
      <p class="greenhouse-form-error" id="greenhouse-form-error" role="alert" tabindex="-1" hidden></p>
      <div class="greenhouse-form-actions"><button type="submit" class="primary-button">Lưu nhà kính</button><button type="button" class="secondary-button" data-action="cancel-greenhouse">Hủy</button></div>
    </form>
  </section>`;
}
function openGreenhouseForm(){
  if(!s.user||s.greenhouseSaving)return;
  navigateRoute(()=>{s.page='greenhouses';s.detailId='';s.creatingGreenhouse=true;s.greenhouseNotice=''});
  document.querySelector('#greenhouse-name')?.focus();
}
async function handleGreenhouseSubmit(e){
  const form=e.target.closest('#greenhouse-form');if(!form)return;e.preventDefault();
  if(s.greenhouseSaving||!s.user)return;
  const values=Object.fromEntries(new FormData(form).entries());
  const payload={greenhouse_id:values.greenhouse_id.trim(),name:values.name.trim(),location:values.location.trim()||null,area_sqm:values.area_sqm.trim()===''?null:Number(values.area_sqm)};
  const showError=message=>{const el=form.querySelector('#greenhouse-form-error');el.textContent=message;el.hidden=false;el.focus()};
  if(!payload.name||!payload.greenhouse_id){showError('Vui lòng nhập tên và mã nhà kính, không chỉ gồm khoảng trắng.');return}
  if(payload.area_sqm!==null&&(!Number.isFinite(payload.area_sqm)||payload.area_sqm<=0)){showError('Diện tích phải là số lớn hơn 0.');return}
  if(s.greenhouses.some(h=>h.greenhouse_id===payload.greenhouse_id)){showError('Mã nhà kính đã tồn tại. Vui lòng chọn mã khác.');return}
  const token=s.token,startedAt=location.pathname+location.search+location.hash,submit=form.querySelector('[type="submit"]');
  s.greenhouseSaving=true;form.setAttribute('aria-busy','true');form.querySelector('fieldset').disabled=true;submit.disabled=true;submit.textContent='Đang lưu…';form.querySelector('[data-action="cancel-greenhouse"]').disabled=true;form.querySelector('#greenhouse-form-error').hidden=true;
  try{
    const created=await api('/api/greenhouses',{method:'POST',body:JSON.stringify(payload)});
    if(s.token!==token||!s.user)return;
    if(!created?.greenhouse_id)throw new Error('Chưa xác nhận được nhà kính đã tạo. Hãy tải lại danh sách trước khi thử lại.');
    s.greenhouses=[...s.greenhouses.filter(h=>h.greenhouse_id!==created.greenhouse_id),created];
    if(location.pathname+location.search+location.hash!==startedAt){render();return}
    s.greenhouseId=created.greenhouse_id;s.deviceId='';s.detailId='';s.error='';
    localStorage.setItem('ln-greenhouse',created.greenhouse_id);
    s.greenhouseNotice='Đã thêm nhà kính “'+created.name+'”.';navigateRoute(()=>{s.creatingGreenhouse=false;s.page='greenhouses'});
    const notice=document.querySelector('#greenhouse-notice');notice?.focus();
  }catch(error){
    if(s.token!==token||!s.user)return;
    showError(error.status===409?'Mã nhà kính đã tồn tại. Vui lòng chọn mã khác.':error.status===401?'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại trước khi lưu.':error.status===403?'Tài khoản của bạn không có quyền thêm nhà kính.':error.status===422?'Thông tin chưa hợp lệ. Kiểm tra tên, mã, vị trí và diện tích rồi thử lại.':'Không thể lưu nhà kính. '+error.message);
  }finally{
    s.greenhouseSaving=false;form.removeAttribute('aria-busy');form.querySelector('fieldset').disabled=false;submit.disabled=false;submit.textContent='Lưu nhà kính';form.querySelector('[data-action="cancel-greenhouse"]').disabled=false;
  }
}
app.addEventListener('submit',handleGreenhouseSubmit);
app.addEventListener('click',e=>{
  if(e.target.closest('[data-action="add-greenhouse"]'))openGreenhouseForm();
  if(e.target.closest('[data-action="cancel-greenhouse"]')&&!s.greenhouseSaving){navigateRoute(()=>{s.creatingGreenhouse=false});app.querySelector('[data-action="add-greenhouse"]')?.focus()}
});
function greenhouseList(){
  if(!s.greenhouses.length)return '<div class="card empty empty-state"><div class="icon-tile" style="margin:auto auto 12px">⌂</div>Chưa có nhà kính nào được đăng ký.</div><div class="management-notice">'+addGreenhouseButton()+'</div>';
  return '<div class="greenhouse-list-actions">'+addGreenhouseButton()+'</div><div class="section-heading"><h2>Không gian của bạn</h2><span>'+s.greenhouses.length+' nhà kính · '+s.devices.length+' thiết bị</span></div><div class="collection-grid">'+s.greenhouses.map((h,i)=>{
    const ds=devices(h.greenhouse_id),on=ds.filter(x=>x.is_online).length;
    return '<article class="card greenhouse-card"><div class="greenhouse-cover" aria-hidden="true"><span class="greenhouse-cover-label">NHÀ KÍNH / '+String(i+1).padStart(2,'0')+'</span></div><div class="greenhouse-card-body"><div class="topline"><div class="icon-tile">⌂</div><div><h3>'+esc(h.name)+'</h3><div class="tiny">'+esc(h.location||'Chưa có vị trí')+' · '+(h.area_sqm?fmt(h.area_sqm,0)+' m²':'Chưa có diện tích')+'</div></div></div><p>'+pill(ds.length?on+'/'+ds.length+' thiết bị trực tuyến':'Chưa liên kết thiết bị',ds.length&&on===ds.length?'':'offline')+'</p><div class="tiny">Mã nhà kính: '+esc(h.greenhouse_id)+'</div><button class="link-button" data-open="'+esc(h.greenhouse_id)+'">Xem nhà kính →</button></div></article>';
  }).join('')+'</div>';
}
function greenhouseDetail(id){const h=s.greenhouses.find(x=>x.greenhouse_id===id);if(!h)return greenhouseList();const ds=devices(id);return '<div class="detail-heading"><div class="section-heading"><h2>Thiết bị liên kết</h2><span>'+ds.length+' thiết bị</span></div></div><div class="device-grid">'+(ds.length?ds.map(d=>{const l=latest(d.device_id);return '<article class="card device-card">'+pill(d.is_online?'Đang kết nối':'Chưa kết nối',d.is_online?'':'offline')+'<h3>'+esc(d.device_id)+'</h3><div class="tiny">'+esc(d.device_type||'Cảm biến')+' · '+esc(d.status||'—')+'</div><div class="row"><span>Bản ghi gần nhất</span><strong>'+date(l?.timestamp)+'</strong></div></article>'}).join(''):'<div class="card empty empty-state">Nhà kính này chưa có thiết bị nào.</div>')+'</div><div class="management-notice">'+locked('Thêm thiết bị')+'</div>'}
function advice(){const ids=new Set(devices().map(x=>x.device_id)),rows=s.recommendations.filter(x=>ids.has(x.device_id));return '<div class="page-toolbar"><div class="garden-picker">'+picker()+'</div><div class="toolbar-note"><div class="banner">Gợi ý chăm sóc từ dữ liệu cảm biến. Hãy đối chiếu điều kiện thực tế trước khi quyết định.</div></div></div><div class="section-heading"><h2>Cần xem xét</h2><span>'+rows.length+' gợi ý</span></div><div class="recommendation-grid">'+(rows.length?rows.map(r=>'<article class="card recommendation-card"><div class="tag">DỮ LIỆU CẢM BIẾN</div><p>'+pill(r.status==='PENDING'?'Chưa xác nhận':r.status,r.status==='PENDING'?'pending':'')+'</p><h3>'+esc(r.condition_diagnosis||'Khuyến nghị')+'</h3><div class="tiny">'+esc(r.device_id)+' · '+date(r.created_at)+'</div><p>'+esc(r.fertilizer_action||'API chưa có hướng dẫn xử lý.')+'</p>'+(r.status==='PENDING'?'<button class="secondary-button" data-apply="'+esc(r.rec_id)+'">Đánh dấu đã áp dụng</button>':'')+'</article>').join(''):'<div class="card empty empty-state">Chưa có khuyến nghị nào cho thiết bị trong nhà kính này.</div>')+'</div>'}
function alerts(){const ids=new Set(devices().map(x=>x.device_id)),items=[];for(const d of devices())if(!d.is_online){const l=latest(d.device_id);items.push(['danger',d.device_id+' chưa trực tuyến',l?'Bản ghi gần nhất '+date(l.timestamp)+'. Trạng thái lấy từ API.':'API chưa có bản ghi cảm biến.'])}for(const r of s.recommendations.filter(x=>ids.has(x.device_id)&&x.status==='PENDING'))items.push(['warning','Có khuyến nghị cần xem xét',(r.condition_diagnosis||r.fertilizer_action||'Mở khuyến nghị để xem chi tiết.')+' · '+date(r.created_at)]);return '<div class="page-toolbar"><div class="garden-picker">'+picker()+'</div><div class="toolbar-note"><div class="banner">Theo dõi trạng thái thiết bị và những khuyến nghị đang chờ xem xét.</div></div></div><div class="section-heading"><h2>Hiện tại</h2><span>'+items.length+' mục</span></div><div class="notification-list">'+(items.length?items.map(x=>'<article class="card notification-card '+x[0]+'">'+pill(x[0]==='danger'?'Kiểm tra thiết bị':'Cần xem xét',x[0]==='danger'?'error':'pending')+'<h3>'+esc(x[1])+'</h3><p class="tiny">'+esc(x[2])+'</p></article>').join(''):'<div class="card empty empty-state">Chưa có cảnh báo từ dữ liệu API.</div>')+'</div>'}
function renderHeader(){document.querySelector('#garden-name').textContent='Greenhouse';const fullName=s.user?.full_name||'';const initials=fullName.trim().split(/\s+/).filter(Boolean).slice(-2).map(part=>part[0]).join('').toLocaleUpperCase('vi-VN');const avatarIcon=profileToggle.querySelector('svg'),avatarInitials=document.querySelector('#profile-initials');avatarIcon.toggleAttribute('hidden',Boolean(initials));avatarInitials.hidden=!initials;avatarInitials.textContent=initials;profileToggle.setAttribute('aria-label',s.user?'Thông tin người dùng: '+fullName:'Yêu cầu đăng nhập')}
function eyeIcon(visible){return visible?'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 3l18 18M10.6 10.6a2 2 0 0 0 2.8 2.8M9.9 5.2A11.5 11.5 0 0 1 12 5c5.5 0 9 7 9 7a14 14 0 0 1-3 3.8M6.2 6.2C3.8 7.8 2 12 2 12s3.5 7 10 7a10 10 0 0 0 4-.8"/></svg>':'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>'}
function passwordField(name,label,autocomplete,minLength=0){const length=minLength?`minlength="${minLength}" maxlength="128"`:'';return `<label>${label}<span class="password-field"><input type="password" name="${name}" autocomplete="${autocomplete}" ${length} required><button type="button" class="password-toggle" data-password-toggle aria-label="Hiện mật khẩu" aria-pressed="false">${eyeIcon(false)}</button></span></label>`}
function renderUserPanel(){if(s.profileMode==='login'||s.profileMode==='register'){const isRegister=s.profileMode==='register',values=s.authValues;const errorMarkup=s.authError?`<p class="auth-message" role="alert">${esc(s.authError)}</p>`:'';const passwordFields=passwordField('password','Mật khẩu',isRegister?'new-password':'current-password',isRegister?12:0)+(isRegister?passwordField('password_confirm','Xác nhận mật khẩu','new-password',12):'');profilePanel.innerHTML=`<div class="auth-panel-title"><button class="panel-back" type="button" data-profile-mode="info" aria-label="Quay lại"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 12H5M12 19l-7-7 7-7"/></svg></button><strong>${isRegister?'Đăng ký':'Đăng nhập'}</strong></div><form class="auth-form" data-auth-form="${s.profileMode}">${isRegister?`<label>Họ và tên<input type="text" name="full_name" maxlength="100" autocomplete="name" required value="${esc(values.full_name||'')}"></label>`:''}<label>Email<input type="email" name="email" maxlength="254" autocomplete="email" required value="${esc(values.email||'')}"></label>${isRegister?`<label>Số điện thoại <small>(không bắt buộc)</small><input type="tel" name="phone_number" maxlength="40" autocomplete="tel" value="${esc(values.phone_number||'')}"></label>`:''}${passwordFields}${!isRegister?'<button class="forgot-link" type="button" data-profile-mode="forgot">Quên mật khẩu?</button>':''}${errorMarkup}<button class="primary-button" type="submit" ${s.authBusy?'disabled':''}>${s.authBusy?'Đang xử lý…':isRegister?'Tạo tài khoản':'Đăng nhập'}</button></form><p class="auth-switch">${isRegister?'Đã có tài khoản?':'Chưa có tài khoản?'} <button type="button" data-profile-mode="${isRegister?'login':'register'}">${isRegister?'Đăng nhập':'Đăng ký'}</button></p>`;return}if(s.profileMode==='forgot'){profilePanel.innerHTML=`<div class="auth-panel-title"><button class="panel-back" type="button" data-profile-mode="login" aria-label="Quay lại đăng nhập"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 12H5M12 19l-7-7 7-7"/></svg></button><strong>Quên mật khẩu</strong></div><label class="auth-email-label">Email<input type="email" autocomplete="email" value="${esc(s.authValues.email||'')}" required></label><p class="auth-info">API hiện chưa có chức năng gửi liên kết đặt lại mật khẩu. Vui lòng liên hệ quản trị viên để được hỗ trợ.</p><button class="secondary-button" type="button" disabled>Khôi phục mật khẩu chưa khả dụng</button>`;return}if(!s.user){profilePanel.innerHTML='<strong class="user-panel-heading">Thông tin cá nhân</strong><div class="auth-required"><b>Yêu cầu đăng nhập</b><p>'+esc(s.sessionError||'Cần đăng nhập để truy cập tài nguyên này.')+'</p></div><button class="primary-button" type="button" data-profile-mode="login">Đăng nhập</button>';return}const user=s.user;profilePanel.innerHTML='<strong class="user-panel-heading">Thông tin cá nhân</strong><div class="user-panel-person"><span class="user-panel-avatar" aria-hidden="true">'+esc((user.full_name||'?').trim().split(/\s+/).filter(Boolean).slice(-2).map(part=>part[0]).join('').toLocaleUpperCase('vi-VN'))+'</span><span><b>'+esc(user.full_name||'Người dùng')+'</b><small>'+esc(user.email||'Chưa có email')+'</small></span></div>'+(user.phone_number?'<p class="user-panel-note">Số điện thoại: '+esc(user.phone_number)+'</p>':'')+'<button class="link-button auth-logout" type="button" data-auth-logout>Đăng xuất</button>'}
function authLayout(content){
  const isRegister=s.authPage==='register',isForgot=s.authPage==='forgot';
  const title=isForgot?'Tìm lại kết nối.':isRegister?'Đăng ký':'Đăng nhập';
  const description=isForgot?'Trở lại với khu vườn và những điều bạn đang chăm chút.':isRegister?'Bắt đầu một hành trình xanh. Để mỗi ngày, khu vườn lại gần bạn hơn.':'Một chút quan tâm mỗi ngày. Cho khu vườn xanh, cho bạn an tâm.';
  return `<div class="auth-hero"><div class="auth-hero-copy"><h1>${title}</h1><p class="auth-hero-description">${description}</p></div><div class="auth-hero-footer"><span>Chăm vườn, an tâm.</span><a href="https://unsplash.com/photos/a-greenhouse-filled-with-lots-of-potted-plants-uSgwNO-_v2I" target="_blank" rel="noopener noreferrer">Ảnh nhà kính / Unsplash ↗</a></div></div><div class="auth-phone"><div class="auth-card">${content}</div></div>`;
}
function renderAuthPage(){
  const isRegister=s.authPage==='register',message=s.authError||s.sessionError,errorMarkup=message?`<p class="auth-message" role="alert">${esc(message)}</p>`:'';
  if(s.authPage==='forgot'){
    authScreen.innerHTML=authLayout(`<span class="auth-card-kicker">TÀI KHOẢN</span><h2>Khôi phục mật khẩu</h2><p class="auth-description">Nhập email tài khoản để bắt đầu khôi phục.</p><label class="auth-email-label">Email *<input type="email" name="email" autocomplete="email" value="${esc(s.authValues.email||'')}" required></label><p class="auth-info">API hiện chưa có chức năng gửi liên kết đặt lại mật khẩu. Vui lòng liên hệ quản trị viên để được hỗ trợ.</p><button class="primary-button" type="button" disabled>Khôi phục mật khẩu chưa khả dụng</button><p class="auth-switch"><button type="button" data-auth-page="login">← Quay lại đăng nhập</button></p>`);
    return;
  }
  const passwordFields=passwordField('password','Mật khẩu *',isRegister?'new-password':'current-password',isRegister?12:0)+(isRegister?passwordField('password_confirm','Xác nhận mật khẩu *','new-password',12):'');
  authScreen.innerHTML=authLayout(`<span class="auth-card-kicker">KHU VƯỜN CỦA BẠN</span><h2>${isRegister?'Tạo một khởi đầu xanh.':'Chào mừng trở lại.'}</h2><p class="auth-description">${isRegister?'Tạo tài khoản để đồng hành cùng khu vườn của bạn.':'Đăng nhập để tiếp tục đồng hành cùng khu vườn của bạn.'}</p><p class="auth-required-hint">Dấu * là thông tin bắt buộc.</p><form class="auth-form auth-page-form" data-auth-form="${s.authPage}">${isRegister?`<label>Họ và tên *<input type="text" name="full_name" maxlength="100" autocomplete="name" required value="${esc(s.authValues.full_name||'')}"></label>`:''}<label>Email *<input type="email" name="email" maxlength="254" autocomplete="email" required value="${esc(s.authValues.email||'')}"></label>${passwordFields}${!isRegister?'<button class="forgot-link" type="button" data-auth-page="forgot">Quên mật khẩu?</button>':''}${errorMarkup}<button class="primary-button auth-submit" type="submit" ${s.authBusy?'disabled':''}>${s.authBusy?'Đang xử lý…':isRegister?'Tạo tài khoản':'Đăng nhập'}</button></form><p class="auth-switch">${isRegister?'Bạn đã có tài khoản?':'Bạn chưa có tài khoản?'} <button type="button" data-auth-page="${isRegister?'login':'register'}">${isRegister?'Đăng nhập →':'Đăng ký →'}</button></p>`);
}
function render(){
  if(!s.user){appShell.classList.add('auth-mode');authScreen.hidden=false;renderAuthPage();return}
  appShell.classList.remove('auth-mode');authScreen.hidden=true;
  const detail=s.page==='greenhouses'&&s.greenhouses.find(x=>x.greenhouse_id===s.detailId);
  const creating=s.page==='greenhouses'&&s.creatingGreenhouse;
  const title=creating?'Thêm nhà kính':detail?detail.name:pages[s.page][0];
  const descriptions={home:'Nắm bắt nhịp sống khu vườn, từ những số đo nhỏ nhất.',history:'Nhìn lại dữ liệu để hiểu khu vườn của bạn hơn.',greenhouses:'Mỗi khu vườn, một không gian để chăm chút.',advice:'Chăm sóc đúng lúc, bắt đầu từ việc thấu hiểu.',alerts:'Những cập nhật cần bạn quan tâm.'};
  const description=detail?(detail.location||'Chưa có vị trí')+' · '+(detail.area_sqm?fmt(detail.area_sqm,0)+' m²':'Chưa có diện tích'):descriptions[s.page];
  nav.forEach(x=>{const active=x.dataset.page===s.page;x.classList.toggle('active',active);if(active)x.setAttribute('aria-current','page');else x.removeAttribute('aria-current')});
  app.dataset.view=s.page;app.dataset.detail=String(Boolean(detail));
  renderHeader();
  let body=creating?greenhouseForm():s.error?'<div class="error-page"><b>Chưa kết nối được API</b><br>'+esc(s.error)+'<p><button class="link-button" data-action="refresh">Thử tải lại</button></p></div>':s.page==='home'?home():s.page==='history'?history():s.page==='greenhouses'?(s.detailId?greenhouseDetail(s.detailId):greenhouseList()):s.page==='advice'?advice():alerts();
  if(s.page==='greenhouses'&&!creating&&s.greenhouseNotice)body='<p id="greenhouse-notice" class="banner" role="status" tabindex="-1">'+esc(s.greenhouseNotice)+'</p>'+body;
  app.innerHTML='<div class="page-header"><div class="page-heading"><span class="page-eyebrow">'+(detail?'NHÀ KÍNH':pages[s.page][1].toLocaleUpperCase('vi-VN'))+'</span><h1 class="page-title">'+esc(title)+'</h1><p class="subline">'+esc(description)+'</p></div><div class="page-status"><span aria-hidden="true">◷</span> Dữ liệu quan trắc · UTC+7</div></div>'+body;
}
const profileToggle=document.querySelector('#profile-toggle'),profilePanel=document.querySelector('#profile-panel');
function setProfileOpen(open){if(open)renderUserPanel();profilePanel.hidden=!open;profileToggle.setAttribute('aria-expanded',String(open))}
profileToggle.addEventListener('click',()=>setProfileOpen(profilePanel.hidden));
profilePanel.addEventListener('click',e=>{const eye=e.target.closest('[data-password-toggle]');if(eye){const input=eye.closest('.password-field')?.querySelector('input');if(input){const visible=input.type==='password';input.type=visible?'text':'password';eye.setAttribute('aria-label',visible?'Ẩn mật khẩu':'Hiện mật khẩu');eye.setAttribute('aria-pressed',String(visible));eye.innerHTML=eyeIcon(visible)}return}const mode=e.target.closest('[data-profile-mode]')?.dataset.profileMode;if(mode){e.stopPropagation();const email=profilePanel.querySelector('[name=email]')?.value||s.authValues.email||'';s.profileMode=mode;s.authError='';s.authValues=mode==='info'?{}:{email};renderUserPanel();return}if(e.target.closest('[data-auth-logout]')){e.stopPropagation();clearSession();s.profileMode='info';s.authError='';s.authValues={};s.sessionError='';s.error='';s.authPage='login';writeRoute(true);render();setProfileOpen(false)}});
authScreen.addEventListener('click',e=>{const eye=e.target.closest('[data-password-toggle]');if(eye){const input=eye.closest('.password-field')?.querySelector('input');if(input){const visible=input.type==='password';input.type=visible?'text':'password';eye.setAttribute('aria-label',visible?'Ẩn mật khẩu':'Hiện mật khẩu');eye.setAttribute('aria-pressed',String(visible));eye.innerHTML=eyeIcon(visible)}return}const pageButton=e.target.closest('[data-auth-page]');if(pageButton){const page=pageButton.dataset.authPage,email=authScreen.querySelector('[name="email"]')?.value||s.authValues.email||'',fullName=authScreen.querySelector('[name="full_name"]')?.value||s.authValues.full_name||'';navigateRoute(()=>{s.authPage=page;s.authError='';s.authValues={email,...(page==='register'&&fullName?{full_name:fullName}:{})}});const heading=authScreen.querySelector('h2');heading?.setAttribute('tabindex','-1');heading?.focus({preventScroll:true})}});
async function handleAuthSubmit(e){const form=e.target.closest('[data-auth-form]');if(!form)return;e.preventDefault();const mode=form.dataset.authForm,payload=Object.fromEntries(new FormData(form).entries()),submitButton=form.querySelector('[type="submit"]');if(mode==='register'&&payload.password!==payload.password_confirm){const confirmation=form.querySelector('[name="password_confirm"]');confirmation.setCustomValidity('Mật khẩu xác nhận không khớp');confirmation.reportValidity();confirmation.addEventListener('input',()=>confirmation.setCustomValidity(''),{once:true});return}delete payload.password_confirm;s.authValues={email:payload.email||'',full_name:payload.full_name||''};s.authError='';s.authBusy=true;submitButton.disabled=true;submitButton.textContent='Đang xử lý…';try{const result=await api('/api/auth/'+mode,{method:'POST',body:JSON.stringify(payload)});if(!result?.access_token||!result.user)throw new Error('API không trả về phiên đăng nhập hợp lệ');s.token=result.access_token;sessionStorage.setItem('ln-access-token',s.token);s.user=result.user;s.profileMode='info';s.authPage='login';s.page='home';s.detailId='';s.creatingGreenhouse=false;s.authError='';s.authValues={};s.sessionError='';s.error='';setProfileOpen(false);await load();writeRoute(true)}catch(error){s.authError=error.message;s.authBusy=false;if(authScreen.contains(form))renderAuthPage();else renderUserPanel();return}s.authBusy=false;if(s.user)renderUserPanel()}
authScreen.addEventListener('submit',handleAuthSubmit);
profilePanel.addEventListener('submit',handleAuthSubmit);
document.addEventListener('click',e=>{if(!e.target.closest('.profile-menu'))setProfileOpen(false)});
document.addEventListener('keydown',e=>{if(e.key==='Escape')setProfileOpen(false)});
async function restoreSession(){const route=readRoute();if(!s.token){s.user=null;applyRoute(route);writeRoute(true);render();return}try{s.user=await api('/api/auth/me');s.sessionError='';await load();applyRoute(route);writeRoute(true);render()}catch(error){if(error.status===401||error.status===403){clearSession();s.sessionError='Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.'}else{s.sessionError='Không thể xác minh phiên đăng nhập: '+error.message}writeRoute(true);render()}}
document.addEventListener('click',async e=>{const modeButton=e.target.closest('[data-profile-mode]');if(modeButton&&!profilePanel.contains(modeButton)){s.profileMode=modeButton.dataset.profileMode;s.authError='';s.authValues={};renderUserPanel();setProfileOpen(true);return}const p=e.target.closest('[data-page]')?.dataset.page;if(p){if(s.greenhouseSaving)return;navigateRoute(()=>{s.creatingGreenhouse=false;s.greenhouseNotice='';s.page=p;s.detailId=''});return}const m=e.target.closest('[data-metric]')?.dataset.metric;if(m){navigateRoute(()=>{s.metric=m},{scroll:false});return}const period=e.target.closest('[data-period]')?.dataset.period;if(period){navigateRoute(()=>{s.period=period},{scroll:false});return}if(e.target.closest('[data-action="refresh"]')){await load();return}const open=e.target.closest('[data-open]')?.dataset.open;if(open){navigateRoute(()=>{s.detailId=open;s.greenhouseId=open;localStorage.setItem('ln-greenhouse',open)});return}const id=e.target.closest('[data-apply]')?.dataset.apply;if(id&&confirm('Đánh dấu khuyến nghị này là đã áp dụng? Trạng thái sẽ được cập nhật trong API.'))try{await api('/api/recommendations/'+encodeURIComponent(id)+'/apply',{method:'PUT'});await load()}catch(err){alert('Không cập nhật được: '+err.message)}});
document.addEventListener('change',e=>{if(e.target.id==='gh'){navigateRoute(()=>{s.greenhouseId=e.target.value;s.detailId='';s.deviceId='';localStorage.setItem('ln-greenhouse',s.greenhouseId)},{scroll:false})}else if(e.target.id==='device'){navigateRoute(()=>{s.deviceId=e.target.value},{scroll:false})}});
restoreSession();
