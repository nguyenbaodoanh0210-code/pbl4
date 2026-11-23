const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const code = fs.readFileSync(path.join(__dirname, '../js/models/cameraWorkflow.js'), 'utf8')
  .replace(/export /g, '');
const sandbox = vm.createContext({setTimeout});
vm.runInContext(code, sandbox);
const { normalizeCameraResult, captureAndWait } = sandbox;

test('upload and history normalize to the same fields used by the view', () => {
  const log = {log_id:'cam-1', timestamp:'2026-11-23T01:00:00Z', ai_diagnosis:'Healthy',
    confidence_score:.9, cnn_confidence:.8, temperature_at_capture:25, humidity_at_capture:60, status:'NEW'};
  const upload = normalizeCameraResult({camera_log:log, multimodal:{confidence_delta:.1}});
  const history = normalizeCameraResult(log);
  assert.equal(upload.log_id, history.log_id);
  assert.equal(upload.final_diagnosis, 'Healthy');
  assert.equal(history.final_confidence, .9);
  assert.equal(history.captured_at, log.timestamp);
  assert.equal(upload.sensor_context.temperature, 25);
  assert.equal(normalizeCameraResult({log_id:'x'}).sensor_context, null);
});

test('failed dispatch cannot poll or claim success', async () => {
  let polls = 0;
  await assert.rejects(captureAndWait({trigger:async()=>({dispatched:false,message:'offline'}),
    getResult:async()=>{ polls++; }}), /offline/);
  assert.equal(polls, 0);
});

test('capture ignores old or unrelated photos and waits for matching request', async () => {
  let polls=0, clock=0;
  const result=await captureAndWait({trigger:async()=>({dispatched:true,capture_id:'cam-new'}),
    getResult:async id=>{ assert.equal(id,'cam-new'); return {log_id:++polls<3?'cam-old':'cam-new'}; },
    now:()=>clock, sleep:async ms=>{clock+=ms;}});
  assert.equal(result.log_id,'cam-new');
  assert.equal(polls,3);
});

test('missing capture result times out without selecting an old image', async () => {
  let clock=0;
  await assert.rejects(captureAndWait({trigger:async()=>({dispatched:true,capture_id:'cam-new'}),
    getResult:async()=>{throw Object.assign(new Error('missing'),{status:404});},
    now:()=>clock,sleep:async ms=>{clock+=ms;},timeoutMs:4000}), /Chưa nhận được ảnh/);
});

test('leaving the garden cancels result display', async () => {
  const result=await captureAndWait({trigger:async()=>({dispatched:true,capture_id:'cam-new'}),
    isCurrent:()=>false,getResult:async()=>{throw Error('must not poll');}});
  assert.equal(result,null);
});

test('authorization failures stop polling immediately', async () => {
  await assert.rejects(captureAndWait({trigger:async()=>({dispatched:true,capture_id:'cam-new'}),
    getResult:async()=>{throw Object.assign(new Error('expired'),{status:401});}}), /expired/);
});
