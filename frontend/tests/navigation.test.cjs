const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../app.js'),'utf8');
function setup(initial='/'){
  const state={user:{user_id:'test'},page:'home',greenhouses:[{greenhouse_id:'NK-01'}],devices:[{greenhouse_id:'NK-01',device_id:'D-01'}],greenhouseId:'NK-01',deviceId:'',detailId:'',creatingGreenhouse:false,metric:'soil_moisture',period:'day',authPage:'login'};
  const location=new URL('http://local.test'+initial),stack=[location.pathname+location.search],entries=[null];let index=0,renders=0;
  const listeners={};
  const history={pushState(value,unused,url){stack.splice(++index);entries.splice(index);stack.push(url);entries.push(value);location.href='http://local.test'+url},replaceState(value,unused,url){stack[index]=url;entries[index]=value;location.href='http://local.test'+url}};
  const context=vm.createContext({s:state,location,window:{history,scrollTo(){},addEventListener:(name,fn)=>listeners[name]=fn},URL,URLSearchParams,Object,metrics:[['soil_moisture'],['temperature']],pages:{home:[],greenhouses:[],history:[],advice:[],alerts:[]},render:()=>renders++,setProfileOpen(){}});
  vm.runInContext(source.slice(source.indexOf('const routeFields='),source.indexOf('const esc='))+'\nfunction history(){}',context);
  return {state,location,stack,entries,history,context,renders:()=>renders,back(){if(index>0){index--;location.href='http://local.test'+stack[index];listeners.popstate({state:entries[index]})}},forward(){if(index<stack.length-1){index++;location.href='http://local.test'+stack[index];listeners.popstate({state:entries[index]})}}};
}
test('browser back and forward restore menu, greenhouse detail and creation step',()=>{
  const f=setup();f.context.writeRoute(true);
  f.context.navigateRoute(()=>{f.state.page='greenhouses'});
  f.context.navigateRoute(()=>{f.state.detailId='NK-01'});
  assert.equal(f.location.search,'?page=greenhouses&detail=NK-01&gh=NK-01');
  f.back();assert.equal(f.state.page,'greenhouses');assert.equal(f.state.detailId,'');
  f.forward();assert.equal(f.state.detailId,'NK-01');
  f.back();f.context.navigateRoute(()=>{f.state.creatingGreenhouse=true});
  assert.equal(f.stack.length,3);assert.match(f.location.search,/create=1/);
  f.back();assert.equal(f.state.creatingGreenhouse,false);f.forward();assert.equal(f.state.creatingGreenhouse,true);
});
test('filter and selected-device changes become reversible history entries',()=>{
  const f=setup();f.context.writeRoute(true);
  f.context.navigateRoute(()=>{f.state.page='history'});
  f.context.navigateRoute(()=>{f.state.metric='temperature'},{scroll:false});
  f.context.navigateRoute(()=>{f.state.period='week'},{scroll:false});
  f.context.navigateRoute(()=>{f.state.deviceId='D-01'},{scroll:false});
  assert.match(f.location.search,/device=D-01/);f.back();assert.equal(f.state.deviceId,'');f.back();assert.equal(f.state.period,'day');f.back();assert.equal(f.state.metric,'soil_moisture');f.forward();assert.equal(f.state.metric,'temperature');
});
test('auth steps have direct URLs and browser history',()=>{
  const f=setup();f.state.user=null;f.context.writeRoute(true);
  f.context.navigateRoute(()=>{f.state.authPage='register'});
  assert.equal(f.location.search,'?auth=register');f.back();assert.equal(f.state.authPage,'login');f.forward();assert.equal(f.state.authPage,'register');
});
test('initial deep link can restore a greenhouse detail after data loads',()=>{
  const f=setup('/?page=greenhouses&detail=NK-01&gh=NK-01');
  f.context.applyRoute(f.context.readRoute());
  assert.equal(f.state.page,'greenhouses');assert.equal(f.state.detailId,'NK-01');assert.equal(f.state.greenhouseId,'NK-01');
});
