/* Optional acceptance on an explicitly selected development TV or emulator. */
const {chromium}=require('playwright');
const {execFileSync}=require('node:child_process');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const target=process.env.MARE_TEST_TARGET,adbPath=process.env.ADB||'adb';
assert.ok(target,'Set MARE_TEST_TARGET to the explicit test device serial; no device is selected automatically.');
const adb=(...args)=>execFileSync(adbPath,['-s',target,...args],{timeout:25000}).toString();
const key=k=>adb('shell','input','keyevent',k);
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const resumed=()=>adb('shell','dumpsys','activity','activities').split('\n').filter(l=>/mResumedActivity|topResumedActivity/.test(l)).join('\n');
(async()=>{
 let browser,page,original,port;
 try {
  key('KEYCODE_HOME');await sleep(1000);
  const pid=adb('shell','pidof','rio.dan.mare.launcher').trim();assert.match(pid,/^\d+$/);
  port=adb('forward','tcp:0','localabstract:webview_devtools_remote_'+pid).trim();assert.match(port,/^\d+$/);
  browser=await chromium.connectOverCDP('http://127.0.0.1:'+port);page=browser.contexts()[0].pages()[0];
  await page.waitForSelector('.tv-home');await page.evaluate(()=>document.fonts.ready);
  original=await page.evaluate(()=>JSON.parse(TV.preferences()));
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const catalog=await page.evaluate(()=>JSON.parse(TV.catalog()));assert.ok(catalog.apps.length);
  const launchPackage=process.env.MARE_TEST_APP || (catalog.apps.some(a=>a.package==='com.android.vending')?'com.android.vending':catalog.apps[0].package);
  assert.ok(catalog.apps.some(a=>a.package===launchPackage),'MARE_TEST_APP must be installed and launchable');
  const fixture=[launchPackage,...catalog.apps.map(a=>a.package).filter(p=>p!==launchPackage)].slice(0,4);
  await page.evaluate(f=>{TV.save('favorites',JSON.stringify(['not.installed',...f,f[0]]));refreshTV();launcherHome();},fixture);
  assert.deepEqual(await page.evaluate(()=>JSON.parse(TV.preferences()).favorites),fixture);
  assert.equal(await page.locator('html').getAttribute('lang'),'en');
  assert.match(await page.locator('time').textContent(),/^\d\d:\d\d$/);
  await page.locator('[data-f="app:'+fixture[0]+'"]').focus();
  key('KEYCODE_MENU');await sleep(300);assert.equal(await page.locator('.tv-menu.open').count(),1);
  key('KEYCODE_BACK');await sleep(300);assert.equal(await page.locator('.tv-menu.open').count(),0);
  key('KEYCODE_DPAD_CENTER');
  for(let i=0;i<10&&resumed().includes('rio.dan.mare.launcher/');i++)await sleep(500);
  assert.ok(!resumed().includes('rio.dan.mare.launcher/'),'Pinned app must launch and stay foreground; use MARE_TEST_APP for a suitable test app');
  key('KEYCODE_HOME');await sleep(600);assert.match(resumed(),/rio\.dan\.mare\.launcher/);
  await page.locator('[data-f="nav:settings"]').focus();key('KEYCODE_DPAD_CENTER');await sleep(500);
  await page.locator('[data-f="set:motion"]').focus();key('KEYCODE_DPAD_LEFT');await sleep(250);
  assert.equal(await page.locator('canvas[data-mark]').count(),0);
  await page.locator('[data-f="set:tv"]').focus();key('KEYCODE_DPAD_CENTER');await sleep(1000);assert.match(resumed(),/settings/i);
  key('KEYCODE_HOME');await sleep(600);assert.equal(await page.locator('.tv-panel.open').count(),0);
  const info=await page.evaluate(()=>({version:TV.version(),viewport:[innerWidth,innerHeight],dpr:devicePixelRatio,webview:navigator.userAgent}));
  assert.deepEqual(errors,[]);
  fs.mkdirSync(path.resolve(__dirname,'../.evidence'),{recursive:true});
  fs.writeFileSync(path.resolve(__dirname,'../.evidence/android-verification.json'),JSON.stringify({...info,apps:catalog.apps.length,inputs:catalog.inputs.length,errors,verifiedAt:new Date().toISOString()},null,2)+'\n');
  console.log('PASS: native catalog, English/24h clock, preference validation, Menu/Back, app launch, Settings and Home; '+JSON.stringify(info));
 } finally {
  if(page&&original) await page.evaluate(p=>{TV.save('favorites',JSON.stringify(p.favorites));TV.save('theme',p.theme);TV.save('motion',String(p.motion));refreshTV();launcherHome();},original).catch(()=>{});
  try{key('KEYCODE_HOME');}catch{}
  if(browser)await browser.close();
  if(port)try{adb('forward','--remove','tcp:'+port);}catch{}
 }
})().catch(e=>{console.error(e);process.exitCode=1;});
