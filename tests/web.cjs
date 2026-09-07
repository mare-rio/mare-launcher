/* Redesign acceptance at the TV's measured CSS viewport, with a larger stress catalog. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
const {pathToFileURL}=require('node:url');
const fixture={apps:[
 ['com.example.library','Library'],['org.smarttube.stable','SmartTube'],['org.jellyfin.androidtv','Jellyfin'],['com.stremio.one','Stremio'],
 ['com.spotify.tv.android','Spotify'],['com.formulaone.production','F1 TV'],['com.apple.atve.androidtv.appletv','Apple TV'],['com.disney.disneyplus','Disney+'],
 ...Array.from({length:56},(_,i)=>['test.app'+i,'Test '+String(i).padStart(2,'0')])].map(([p,n])=>({package:p,name:n,tv:true})),
 inputs:[{id:'hdmi1',name:'Console',label:'HDMI 1',type:1007,state:0},{id:'hdmi2',name:'HDMI 2',type:1007,state:1},{id:'hdmi3',name:'HDMI 3',type:1007,state:2},{id:'tuner',name:'TV',type:0,state:0}]};
fs.mkdirSync(path.resolve(__dirname,'../.evidence'),{recursive:true});
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH,headless:true,args:['--no-sandbox']});
 try {
 const page=await browser.newPage({viewport:{width:960,height:540},deviceScaleFactor:2,timezoneId:'America/Sao_Paulo'});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(({fixture})=>{
   window.testData=fixture;window.actions=[];
   window.TV={catalog:()=>JSON.stringify(testData),preferences:()=>localStorage.getItem('test-prefs')||JSON.stringify({favorites:fixture.apps.slice(0,8).map(a=>a.package),motion:true,theme:'night'}),
     save:(k,v)=>{const p=JSON.parse(TV.preferences());p[k]=k==='favorites'?JSON.parse(v):k==='motion'?v==='true':v;localStorage.setItem('test-prefs',JSON.stringify(p));},
     network:()=>'Wi-Fi connected',version:()=>'0.3.0',launch:p=>actions.push(['launch',p]),input:p=>actions.push(['input',p]),settings:p=>actions.push(['settings',p]),appInfo:p=>actions.push(['info',p]),exit:()=>actions.push(['exit'])};
 },{fixture});
 await page.goto(pathToFileURL(path.resolve(__dirname,'../.build/web/index.html')).href);
 await page.evaluate(()=>document.fonts.ready);await page.waitForTimeout(450);
 const id=()=>page.evaluate(()=>document.activeElement.dataset.f);
 const focus=async f=>{await page.locator(`[data-f="${f}"]`).focus();};
 const key=k=>page.keyboard.press(k);
 const remote=k=>page.evaluate(k=>remoteKey(k),k);
 const home=()=>page.evaluate(()=>launcherHome());
 const pane=async p=>{await home();await page.locator(`[data-f="nav:${p}"]`).click();await page.waitForTimeout(450);};
 const menu=async f=>{await focus(f);await key('ContextMenu');await page.waitForTimeout(250);};
 const hold=async()=>{await page.keyboard.down('Enter');await page.waitForTimeout(500);await page.keyboard.up('Enter');await page.waitForTimeout(250);};
 const action=async f=>{await focus(f);await key('Enter');};
 const prefs=()=>page.evaluate(()=>JSON.parse(TV.preferences()));
 const menuOpen=()=>page.locator('.tv-menu.open').count();
 const snap=async n=>{await page.waitForTimeout(500);await page.screenshot({path:path.resolve(__dirname,'../.evidence/browser-'+n+'.png')});};
 assert.equal(await id(),'app:com.example.library');
 const geometry=await page.evaluate(()=>{
   const box=s=>{const r=document.querySelector(s).getBoundingClientRect();return [r.x,r.y,r.width,r.height];};
   return {clock:box('.tv-time'),grid:box('.tv-favorites'),tile:box('.mare-app'),font:getComputedStyle(document.querySelector('.mare-app-name')).fontSize,canvas:!!document.querySelector('canvas[data-mark]'),grain:getComputedStyle(document.body,'::after').backgroundImage};
 });
 assert.deepEqual(geometry.clock.slice(0,2),[48,80]);assert.deepEqual(geometry.grid.slice(0,3),[48,190,864]);assert.equal(geometry.tile[2],192);assert.equal(geometry.font,'26px');assert.ok(geometry.canvas);assert.match(geometry.grain,/grain-4k/);
 assert.match(await page.locator('.tv-time time').textContent(),/^\d\d:\d\d$/);
 assert.equal(await page.locator('.tv-time span').textContent(),new Date().toLocaleDateString('en-GB',{weekday:'long',day:'numeric',month:'long',timeZone:'America/Sao_Paulo'}));
 await snap('home-night');
 await key('ArrowRight');assert.equal(await id(),'app:org.smarttube.stable');await key('ArrowDown');assert.equal(await id(),'app:com.formulaone.production');
 await key('Enter');assert.deepEqual(await page.evaluate(()=>actions.at(-1)),['launch','com.formulaone.production']);
 const count=await page.evaluate(()=>actions.length);await hold();assert.equal(await menuOpen(),1);assert.equal(await id(),'mi:open');assert.equal(await page.evaluate(()=>actions.length),count);
 const bounds=await page.locator('.tv-menu').boundingBox();assert.ok(bounds.x>=48&&bounds.x+bounds.width<=912&&bounds.y>=32&&bounds.y+bounds.height<=508);
 await snap('options');await hold();assert.equal(await menuOpen(),0);assert.equal(await id(),'app:com.formulaone.production');assert.equal(await page.evaluate(()=>actions.length),count);
 await menu('app:com.formulaone.production');await action('mi:up');assert.equal(await id(),'app:com.formulaone.production');assert.equal((await prefs()).favorites[4],'com.formulaone.production');
 await menu('app:com.formulaone.production');await action('mi:down');assert.equal((await prefs()).favorites[5],'com.formulaone.production');
 await pane('apps');assert.equal(await id(),'lib:com.apple.atve.androidtv.appletv');
 assert.equal(await page.locator('.tv-home').evaluate(e=>getComputedStyle(e).opacity),'0.35');assert.equal(await page.locator('canvas[data-mark]').count(),1);
 assert.equal((await page.locator('.tv-panel.open').boundingBox()).x,256);
 await snap('apps');
 // Column-major navigation and clipped, smooth scrolling retain access to all 64 entries.
 for(let i=0;i<15;i++)await key('ArrowDown');await page.waitForTimeout(450);
 const scroll=await page.locator('.tv-library').evaluate(e=>getComputedStyle(e).transform);assert.match(scroll,/-175/);
 const focused=await page.locator(':focus').boundingBox(),clip=await page.locator('.tv-library-clip').boundingBox();assert.ok(focused.y>=clip.y&&focused.y+focused.height<=clip.y+clip.height+1);
 await key('ArrowRight');assert.ok((await id()).startsWith('lib:'));
 // Pin places 9-12, reject 13 without closing the menu.
 for(let i=0;i<4;i++){await menu('lib:test.app'+i);await action('mi:pin');assert.equal(await menuOpen(),0);}
 assert.equal((await prefs()).favorites.length,12);
 await menu('lib:test.app4');await action('mi:pin');assert.equal(await menuOpen(),1);assert.equal(await page.locator('.toast .tk').textContent(),'full');assert.equal((await prefs()).favorites.length,12);
 await key('Escape');assert.equal(await id(),'lib:test.app4');await key('Escape');assert.equal(await id(),'nav:apps');
 await snap('12-favourites');
 // Source from a menu on home, then from Apps, with Back restoring the home origin.
 await menu('app:org.smarttube.stable');await remote('source');assert.equal(await menuOpen(),0);assert.equal(await page.locator('.tv-panel.open h2').textContent(),'Inputs');
 assert.match(await page.locator('[data-f="input:hdmi1"]').textContent(),/hdmi 1 · connected/);
 assert.match(await page.locator('[data-f="input:hdmi2"]').textContent(),/standby/);
 assert.match(await page.locator('[data-f="input:hdmi3"]').textContent(),/not connected/);
 await snap('inputs');await action('input:hdmi1');assert.deepEqual(await page.evaluate(()=>actions.at(-1)),['input','hdmi1']);
 await remote('source');assert.equal(await page.locator('.tv-panel.open').count(),0);assert.equal(await id(),'app:org.smarttube.stable');
 await pane('apps');await remote('source');assert.equal(await page.locator('.tv-panel.open h2').textContent(),'Inputs');await key('Escape');assert.equal(await id(),'nav:apps');
 await pane('settings');await key('ArrowRight');assert.equal(await page.locator('html').getAttribute('data-theme'),'day');assert.equal(await page.locator('.seg button.on').textContent(),'day');
 await key('ArrowDown');assert.equal(await id(),'set:motion');await snap('settings-day');await key('ArrowLeft');assert.equal(await page.locator('body.tv-still').count(),1);assert.equal(await page.locator('canvas[data-mark]').count(),0);
 await key('ArrowRight');assert.equal(await page.locator('canvas[data-mark]').count(),1);
 await page.emulateMedia({reducedMotion:'reduce'});await page.waitForFunction(()=>!document.querySelector('canvas[data-mark]'));assert.equal(await page.locator('canvas[data-mark]').count(),0);assert.equal((await prefs()).motion,true);await page.emulateMedia({reducedMotion:'no-preference'});await page.waitForFunction(()=>!!document.querySelector('canvas[data-mark]'));
 await action('set:bluetooth');assert.deepEqual(await page.evaluate(()=>actions.at(-1)),['settings','bluetooth']);
 await home();await snap('home-day');
 await page.reload();await page.waitForTimeout(100);assert.equal(await page.locator('html').getAttribute('data-theme'),'day');assert.equal(await page.locator('.mare-app').count(),12);
 // Home resets all layers. A cancelled/held press outside an app must never launch.
 await pane('apps');await menu('lib:com.example.library');await home();assert.equal(await id(),'app:com.example.library');assert.equal(await menuOpen(),0);assert.equal(await page.locator('.tv-panel.open').count(),0);
 await focus('nav:settings');await hold();assert.equal(await page.locator('.tv-panel.open').count(),0);
 await page.keyboard.down('Enter');await page.evaluate(()=>cancelRemoteHold());await page.keyboard.up('Enter');assert.equal(await page.locator('.tv-panel.open').count(),0);
 // Last favourite disappears: first-run replaces it and receives focus.
 await page.evaluate(()=>{TV.save('favorites',JSON.stringify(['com.example.library']));refreshTV();launcherHome();});
 await menu('app:com.example.library');await action('mi:pin');assert.equal(await id(),'first:run');await snap('first-run');
 await key('Enter');assert.equal(await page.locator('.tv-panel.open h2').textContent(),'Apps');
 await page.evaluate(()=>{testData.inputs=[];refreshTV();remoteKey('source');});assert.equal(await page.locator('.tv-panel.open h2').textContent(),'Inputs');await key('Escape');assert.equal(await id(),'first:run');
 await key('Escape');assert.deepEqual(await page.evaluate(()=>actions.at(-1)),['exit']);
 // The same layout fits different TV resolutions and density-derived viewports.
 await page.evaluate(()=>{TV.save('favorites',JSON.stringify(testData.apps.slice(0,8).map(a=>a.package)));refreshTV();launcherHome();});
 for(const viewport of [{width:640,height:360},{width:1280,height:720},{width:1920,height:1080},{width:1024,height:768}]){
   await page.setViewportSize(viewport);await page.waitForTimeout(150);
   await menu('app:com.formulaone.production');
   const rect=await page.locator('.tv-menu.open').boundingBox();assert.ok(rect.x>=0&&rect.y>=0&&rect.x+rect.width<=viewport.width+1&&rect.y+rect.height<=viewport.height+1);
   const marker=await page.locator('.tv-menu .tv-focus.on').boundingBox(),row=await page.locator('[data-f="mi:open"]').boundingBox();
   assert.ok(Math.abs(marker.x-row.x)<2&&Math.abs(marker.y-row.y)<2);await key('Escape');
 }
 await page.setViewportSize({width:960,height:540});
 assert.deepEqual(errors,[]);
 fs.writeFileSync(path.resolve(__dirname,'../.evidence/browser-verification.json'),JSON.stringify({verifiedAt:new Date().toISOString(),geometry,tests:'geometry, international date, D-pad, 450ms hold and suppression, menu bounds and Back, reorder, column-major 64-app scrolling, 12/13 cap, source, settings, reduced motion, preference reload, Home, empty inputs, first run',errors},null,2)+'\n',{mode:0o600});
 console.log('PASS: redesign geometry and remote/state acceptance, 64-app stress catalog, 12-place limit, first run, persistence, reduced motion; no JS errors.');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
