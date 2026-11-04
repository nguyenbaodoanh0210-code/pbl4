const {test}=require('node:test');
const assert=require('node:assert/strict');
const {readFileSync}=require('node:fs');
const vm=require('node:vm');
const source=readFileSync(require('node:path').join(__dirname,'../app.js'),'utf8');
function setup(values={},response={ok:true,status:201,json:async()=>({greenhouse_id:'NK-01',name:'Rau xanh'})}){
  const nodes={};
  const node=selector=>nodes[selector]??=( {disabled:false,hidden:true,textContent:'',focus(){this.focused=true}} );
  const form={values:{name:' Rau xanh ',greenhouse_id:' NK-01 ',location:'',area_sqm:'',...values},querySelector:node,setAttribute(){},removeAttribute(){}};
  const state={user:{user_id:'u1'},token:'session',greenhouses:[],creatingGreenhouse:true};
  const calls=[],stored={};let renders=0;
  const context=vm.createContext({s:state,location:{pathname:'/',search:'?page=greenhouses&create=1',hash:''},FormData:class{constructor(f){this.f=f}entries(){return Object.entries(this.f.values)}},fetch:async(...args)=>{calls.push(args);return typeof response==='function'?response():response},localStorage:{setItem:(k,v)=>stored[k]=v},document:{querySelector:node},navigateRoute:update=>{update();renders++},render:()=>renders++});
  vm.runInContext(source.slice(source.indexOf('async function api('),source.indexOf('function clearSession('))+source.slice(source.indexOf('async function handleGreenhouseSubmit('),source.indexOf("app.addEventListener('submit',handleGreenhouseSubmit)")),context);
  return {state,calls,stored,nodes,form,submit:()=>context.handleGreenhouseSubmit({target:{closest:()=>form},preventDefault(){}}),renders:()=>renders};
}
test('creates through authenticated API, trims fields, selects persisted greenhouse',async()=>{
  const f=setup();await f.submit();assert.equal(f.calls.length,1);
  const [url,opts]=f.calls[0];assert.equal(url,'/api/greenhouses');assert.equal(opts.method,'POST');assert.equal(opts.headers.Authorization,'Bearer session');
  assert.deepEqual(JSON.parse(opts.body),{name:'Rau xanh',greenhouse_id:'NK-01',location:null,area_sqm:null});
  assert.equal(f.state.greenhouses.length,1);assert.equal(f.state.greenhouseId,'NK-01');assert.equal(f.stored['ln-greenhouse'],'NK-01');assert.equal(f.state.creatingGreenhouse,false);assert.equal(f.state.page,'greenhouses');assert.match(f.state.greenhouseNotice,/Rau xanh/);assert.equal(f.renders(),1);
});
test('rejects whitespace-only fields, invalid area, and duplicate IDs before sending',async()=>{
  for(const values of [{name:'   '},{greenhouse_id:' '},{area_sqm:'0'},{area_sqm:'-1'},{area_sqm:'Infinity'}]){const f=setup(values);await f.submit();assert.equal(f.calls.length,0);assert.equal(f.nodes['#greenhouse-form-error'].hidden,false)}
  const f=setup();f.state.greenhouses=[{greenhouse_id:'NK-01'}];await f.submit();assert.equal(f.calls.length,0);
});
test('sends positive decimal area and location',async()=>{const f=setup({area_sqm:'12.5',location:' Khu A '});await f.submit();assert.equal(JSON.parse(f.calls[0][1].body).area_sqm,12.5);assert.equal(JSON.parse(f.calls[0][1].body).location,'Khu A')});
test('server conflicts, expired sessions, validation and network failures retain form for retry',async()=>{
  for(const status of [409,401,403,422,503]){const f=setup({}, {ok:false,status,json:async()=>({detail:'server error'})});await f.submit();assert.equal(f.state.greenhouses.length,0);assert.equal(f.state.creatingGreenhouse,true);assert.equal(f.nodes['fieldset'].disabled,false);assert.equal(f.nodes['[type="submit"]'].disabled,false);assert.equal(f.nodes['#greenhouse-form-error'].hidden,false);assert.equal(f.form.values.name,' Rau xanh ')}
  const f=setup({},async()=>{throw new Error('Network error')});await f.submit();assert.match(f.nodes['#greenhouse-form-error'].textContent,/Network error/);assert.equal(f.state.greenhouseSaving,false);
});
test('ignores repeated submit and response after logout',async()=>{
  let finish;const f=setup({},()=>new Promise(resolve=>{finish=resolve}));const pending=f.submit();await f.submit();assert.equal(f.calls.length,1);assert.equal(f.nodes['fieldset'].disabled,true);
  f.state.token='';f.state.user=null;finish({ok:true,status:201,json:async()=>({greenhouse_id:'NK-01',name:'Rau xanh'})});await pending;assert.equal(f.state.greenhouses.length,0);assert.equal(f.renders(),0);
});
