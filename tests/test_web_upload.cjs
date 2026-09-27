// No npm dependencies: DOM event fixture exercises the shipped script's handlers.
// Usage: node tests/test_web_upload.cjs [absolute repository path]
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = process.argv[2] || path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'web/index.html'), 'utf8');
const fixedSource = fs.readFileSync(path.join(root, 'web/app.js'), 'utf8');
class Element {
  constructor(id, hidden=false) {
    this.id=id; this.textContent=''; this.disabled=false; this.files=[]; this.style={}; this.children=[]; this.listeners={};
    this.clientWidth=600; this.currentTime=0; this.duration=20; this.videoWidth=640; this.videoHeight=360;
    const classes=new Set(hidden?['hidden']:[]);
    this.classList={add:c=>classes.add(c), remove:c=>classes.delete(c), contains:c=>classes.has(c)};
  }
  addEventListener(name, fn) { (this.listeners[name] ||= []).push(fn); }
  async emit(name, event={}) { for (const fn of this.listeners[name]||[]) await fn(event); }
  setAttribute(name,value) {this[name]=value;}
  removeAttribute(name) {delete this[name];}
  append(...nodes) {this.children.push(...nodes);}
  replaceChildren(...nodes) {this.children=nodes;}
  play() {return Promise.resolve();}
  getContext() {return new Proxy({}, {get:(_o,_key)=>()=>{}});}
}
function fixture(source) {
  const elements={};
  for (const match of html.matchAll(/<[^>]+\bid="([^"]+)"[^>]*>/g)) {
    elements[match[1]]=new Element(match[1],/\bhidden\b/.test(match[0]));
    elements[match[1]].disabled=/\bdisabled\b/.test(match[0]);
  }
  elements['selected-file'].textContent='Hali video tanlanmagan';
  let mode='success'; const calls=[];
  const response = (data,status=200) => ({ok:status<400,status,headers:{get:()=> 'application/json'},json:async()=>data});
  const sandbox={
    document:{getElementById:id=>elements[id],createElement:tag=>new Element(tag)},
    window:{devicePixelRatio:1,addEventListener(){}},
    URL:{createObjectURL:()=> 'blob:fixture-video',revokeObjectURL(){}},
    FormData:class {constructor(){this.entries=[];} append(...entry){this.entries.push(entry);}},
    fetch:async(url,options)=> {
      calls.push({url,options});
      if(url==='/api/samples') return response({message:'pending',videos:[]});
      if(url==='/api/analyze') return mode==='failure'?response({error:'Server sinov xatosi'},503):response({job_id:'test-job'},202);
      if(url==='/api/jobs/test-job') return response({status:'done',message:'done',progress:100,result:{duration:20,width:640,height:360,events:[],risk:[[0,.1],[10,.2]]}});
      throw Error('Unexpected URL '+url);
    },
    setTimeout:fn=>queueMicrotask(fn), console
  };
  vm.runInNewContext(source,sandbox,{filename:'web/app.js'});
  return {elements,calls,setMode:value=>mode=value};
}
(async()=>{
  // Demonstrate the original exact failure, with the real file-change handler.
  const brokenSource = fixedSource.replace(/function showError\(message\) \{[\s\S]*?\n\}\n\nfunction clearError\(\) \{[\s\S]*?\n\}\n\n/,'');
  assert.notEqual(brokenSource,fixedSource);
  const broken=fixture(brokenSource);
  broken.elements['video-input'].files=[{name:'RoadSight_test_20s.mp4',size:201400}];
  await assert.rejects(broken.elements['video-input'].emit('change'), /clearError is not defined/);
  assert.equal(broken.elements['selected-file'].textContent,'Hali video tanlanmagan');
  assert.equal(broken.elements['analyze-btn'].disabled,true);
  console.log('REPRODUCED prior bug: ReferenceError before filename/preview/button changes');

  const f=fixture(fixedSource), e=f.elements;
  e['video-input'].files=[{name:'bad.txt',size:1}];
  await e['video-input'].emit('change');
  assert.match(e.error.textContent,/Faqat MP4/); assert.equal(e.error.classList.contains('hidden'),false);
  assert.equal(e['analyze-btn'].disabled,true);
  e['video-input'].files=[{name:'RoadSight_test_20s.mp4',size:201400}];
  await e['video-input'].emit('change');
  assert.equal(e.error.textContent,''); assert.equal(e.error.classList.contains('hidden'),true);
  assert.match(e['selected-file'].textContent,/RoadSight_test_20s.mp4/);
  assert.equal(e['analyze-btn'].disabled,false); assert.equal(e.video.src,'blob:fixture-video');
  assert.equal(e.video.classList.contains('hidden'),false); assert.equal(e['empty-video'].classList.contains('hidden'),true);
  await e.video.emit('loadedmetadata');
  assert.equal(e['meta-duration'].textContent,'20.0 s');
  await e['analyze-btn'].emit('click');
  assert.equal(f.calls.filter(c=>c.url==='/api/analyze').length,1);
  assert.equal(f.calls.find(c=>c.url==='/api/analyze').options.body.entries[0][1].name,'RoadSight_test_20s.mp4');
  assert.equal(e['download-json'].classList.contains('hidden'),false);
  assert.equal(e['download-json'].href,'/api/jobs/test-job/download');
  assert.equal(e['progress'].classList.contains('hidden'),true);
  assert.equal(e['analyze-btn'].disabled,false); assert.equal(e['video-input'].disabled,false);
  f.setMode('failure');
  await e['analyze-btn'].emit('click');
  assert.equal(e.error.textContent,'Server sinov xatosi'); assert.equal(e.error.classList.contains('hidden'),false);
  assert.equal(e['analyze-btn'].disabled,false); assert.equal(e['video-input'].disabled,false);
  e.video.duration=121;
  await e.video.emit('loadedmetadata');
  assert.equal(e['analyze-btn'].disabled,true); assert.match(e.error.textContent,/2 daqiqa/);
  console.log('PASS: invalid file, valid file change, error clearing, filename, preview, enabled button, metadata, async analysis completion/download, API error recovery, duration limit');
})().catch(e=>{console.error(e);process.exitCode=1;});
