/* Maré redesign 1a. React primitives provide the surface; this adapter owns TV focus and intents. */
(() => {
  'use strict';
  const h = React.createElement, LIMIT = 12, HOLD = 450, LIB_ROWS = 11;
  const names = {
    'org.smarttube.stable': ['SmartTube', 'Videos and channels'],
    'org.jellyfin.androidtv': ['Jellyfin', 'Your media server'],
    'com.stremio.one': ['Stremio', 'Films and series'],
    'com.spotify.tv.android': ['Spotify', 'Music and podcasts'],
    'com.formulaone.production': ['F1 TV', 'Races and replays'],
    'com.apple.atve.androidtv.appletv': ['Apple TV', 'Films and series'],
    'com.disney.disneyplus': ['Disney+', 'Films and series'],
    'com.globo.globotv': ['Globoplay', 'Live and on demand'],
    'com.amazon.amazonvideo.livingroom': ['Prime Video', 'Films and series'],
    'me.efesser.flauncher': ['FLauncher', 'Alternative home screen']
  };
  const demo = {apps: Object.keys(names).map(p => ({package:p, name:names[p][0], tv:true})),
    inputs:[1,2,3,4].map(n => ({id:'hdmi'+n, name:'HDMI '+n, label:'HDMI '+n, type:1007, state:n===1?0:n===2?1:2}))};
  const bridge = window.TV || {
    catalog: () => JSON.stringify(demo), preferences: () => localStorage.getItem('preview-prefs') || '{}',
    save: (key,value) => {const p=JSON.parse(localStorage.getItem('preview-prefs')||'{}');p[key]=key==='favorites'?JSON.parse(value):key==='motion'?value==='true':value;localStorage.setItem('preview-prefs',JSON.stringify(p));},
    network: () => 'Browser preview', version: () => '0.3.0',
    launch:p=>window.lastAction=['launch',p], input:p=>window.lastAction=['input',p], appInfo:p=>window.lastAction=['appInfo',p],
    settings:p=>window.lastAction=['settings',p], exit:()=>window.lastAction=['exit']
  };
  let data=JSON.parse(bridge.catalog()), pref=JSON.parse(bridge.preferences());
  const clean = list => [...new Set(list)].filter(p=>data.apps.some(a=>a.package===p)).slice(0,LIMIT);
  let favorites=clean(pref.favorites||[]), theme=pref.theme==='day'?'day':'night', motion=pref.motion!==false;
  let pane=null, paneView='apps', paneReturn=null, menu=null, menuView=null, menuReturn=null;
  let focusId=null, libScroll=0, toast=null, toastTimer, held=null;
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  const root=ReactDOM.createRoot(document.getElementById('root'));
  const appName=a=>(names[a.package]||[a.name])[0];
  const purpose=a=>(names[a.package]||[null,a.tv?'TV app':'Android app'])[1];
  const sorted=()=>data.apps.slice().sort((a,b)=>appName(a).localeCompare(appName(b),'en-GB'));
  const app=p=>data.apps.find(a=>a.package===p);
  const homeFirst=()=>favorites.length?'app:'+favorites[0]:'first:run';
  const network=()=>bridge.network().toLocaleLowerCase('en-GB');
  const scope=()=>menu?'menu':pane?'pane':'home';
  const elFor=id=>Array.from(document.querySelectorAll('[data-f]')).find(e=>e.dataset.f===id);
  const boxFor=e=>e?.closest('.mare-app')||e;
  const focusables=()=>Array.from(document.querySelectorAll('[data-f]')).filter(e=>e.closest('[data-scope]')?.dataset.scope===scope());
  const indicator=(kind='')=>h('li',{'aria-hidden':true,role:'presentation',className:'tv-focus '+kind,key:'indicator'});
  function syncFocus() {
    const active=elFor(focusId), nodes=focusables();
    for(const e of document.querySelectorAll('[data-f]'))e.tabIndex=nodes.includes(e)&&e===active?0:-1;
    for(const e of document.querySelectorAll('.tv-focus'))e.classList.remove('on');
    if(!active||!nodes.includes(active))return;
    const layer=active.closest('[data-layer]'), marker=layer?.querySelector('.tv-focus');
    if(!marker)return;
    const a=boxFor(active).getBoundingClientRect(), b=layer.getBoundingClientRect();
    const underline=marker.classList.contains('underline');
    const sx=b.width/layer.offsetWidth||1, sy=b.height/layer.offsetHeight||1;
    Object.assign(marker.style,{left:((a.left-b.left)/sx-layer.clientLeft)+'px',top:(((underline?a.bottom+2*sy:a.top)-b.top)/sy-layer.clientTop)+'px',width:(a.width/sx)+'px',height:(underline?2:a.height/sy)+'px'});
    marker.classList.add('on');
  }
  function focus(id) {
    const list=focusables();
    const e=list.find(e=>e.dataset.f===id)||list.find(e=>e.dataset.f===homeFirst())||list[0];
    focusId=e?.dataset.f||null;
    if(focusId?.startsWith('lib:')) {
      const rows=Math.ceil(data.apps.length/4), index=sorted().findIndex(a=>'lib:'+a.package===focusId), row=index%rows;
      libScroll=Math.min(libScroll,row);if(row>=libScroll+LIB_ROWS)libScroll=row-LIB_ROWS+1;
      document.querySelector('.tv-library').style.transform=`translateY(${-libScroll*35}px)`;
    }
    (e||document.querySelector('.tv-panel.open'))?.focus({preventScroll:true});syncFocus();
  }
  function saveFavorites(){favorites=clean(favorites);bridge.save('favorites',JSON.stringify(favorites));}
  function notify(text,kind){clearTimeout(toastTimer);toast={text,kind};render();toastTimer=setTimeout(()=>{toast=null;render();},4000);}
  function cancelHold(){if(held)clearTimeout(held.timer);held=null;}
  function openPane(next){
    cancelHold();if(!pane)paneReturn=menu?menuReturn:focusId;menu=null;pane=paneView=next;libScroll=0;render();focus();
  }
  function closePane(){cancelHold();menu=null;pane=null;render();focus(paneReturn);}
  function openMenu(pkg){
    if(!app(pkg))return;cancelHold();menuReturn=focusId;menu=menuView=pkg;render();placeMenu();focus('mi:open');
  }
  function closeMenu(){cancelHold();menu=null;render();focus(menuReturn);}
  function placeMenu(){
    if(!menu)return;
    const row=boxFor(elFor(menuReturn)), node=document.querySelector('.tv-menu');if(!row||!node)return;
    // offset dimensions are independent of the menu's entrance scale.
    const box=row.getBoundingClientRect(), frame=document.getElementById('root').getBoundingClientRect(), scale=frame.width/960;
    const r={left:(box.left-frame.left)/scale,right:(box.right-frame.left)/scale,top:(box.top-frame.top)/scale,bottom:(box.bottom-frame.top)/scale}, w=node.offsetWidth, height=node.offsetHeight;
    let left=r.left+12, top=r.bottom+4;
    if(top+height>508){
      if(r.right+12+w<=912){left=r.right+12;top=Math.min(r.top,508-height);}
      else if(r.left-12-w>=48){left=r.left-12-w;top=Math.min(r.top,508-height);}
      else top=Math.max(32,508-height);
    }
    node.style.left=Math.max(48,Math.min(left,912-w))+'px';node.style.top=Math.max(32,top)+'px';
  }
  function changeTheme(next){theme=next;bridge.save('theme',theme);render();focus(focusId);}
  function changeMotion(next){motion=next;bridge.save('motion',String(motion));render();focus(focusId);}
  function activate(id){
    if(!id)return;
    if(id.startsWith('app:')||id.startsWith('lib:'))return bridge.launch(id.slice(4));
    if(id.startsWith('input:'))return bridge.input(id.slice(6));
    if(id.startsWith('nav:'))return openPane(id.slice(4));
    if(id==='first:run'||id==='set:favourites')return openPane('apps');
    if(id==='set:appearance')return changeTheme(theme==='night'?'day':'night');
    if(id==='set:motion')return changeMotion(!motion);
    if(id.startsWith('set:'))return bridge.settings(id.slice(4));
    if(!menu||!id.startsWith('mi:'))return;
    const pkg=menu, name=appName(app(pkg)), index=favorites.indexOf(pkg);
    if(id==='mi:open'||id==='mi:info'){
      closeMenu();return id==='mi:open'?bridge.launch(pkg):bridge.appInfo(pkg);
    }
    if(id==='mi:pin'){
      if(index<0&&favorites.length===LIMIT)return notify('All 12 places are taken · unpin a favourite first','full');
      if(index<0)favorites.push(pkg);else favorites.splice(index,1);
      saveFavorites();closeMenu();
      // Removing the focused home tile keeps focus at its former position when possible.
      if(!pane&&index>=0)focus('app:'+(favorites[Math.min(index,favorites.length-1)]||''));
      return notify(`${name} · ${favorites.length} of 12 on home`,index<0?'pinned':'unpinned');
    }
    if(id==='mi:up'||id==='mi:down'){
      const next=index+(id==='mi:up'?-1:1);if(index<0||next<0||next>=favorites.length)return;
      [favorites[index],favorites[next]]=[favorites[next],favorites[index]];saveFavorites();
      menu=null;pane=null;render();focus('app:'+pkg);notify(`${name} · ${next+1} of ${favorites.length}`,'moved');
    }
  }
  function navigate(key){
    if(!menu&&pane==='settings'&&['left','right'].includes(key)){
      if(focusId==='set:appearance')return changeTheme(key==='left'?'night':'day');
      if(focusId==='set:motion')return changeMotion(key==='right');
    }
    const current=elFor(focusId), list=focusables();if(!current||!list.includes(current))return focus();
    const a=boxFor(current).getBoundingClientRect(), ax=a.left+a.width/2, ay=a.top+a.height/2;
    let best=null, score=Infinity;
    for(const e of list){
      if(e===current)continue;
      const b=boxFor(e).getBoundingClientRect(), dx=b.left+b.width/2-ax, dy=b.top+b.height/2-ay;
      const horizontal=key==='left'||key==='right';
      const primary=key==='right'?dx:key==='left'?-dx:key==='down'?dy:-dy, secondary=Math.abs(horizontal?dy:dx);
      const overlap=horizontal?b.bottom>a.top+2&&b.top<a.bottom-2:b.right>a.left+2&&b.left<a.right-2;
      if(primary<3)continue;const value=primary+secondary*2+(overlap?0:1000);
      if(value<score){score=value;best=e;}
    }
    if(best)focus(best.dataset.f);
  }
  window.cancelRemoteHold=cancelHold;
  window.remoteKey=key=>{
    if(key==='enter'){
      if(held)return;
      const press={id:focusId,long:false};held=press;
      press.timer=setTimeout(()=>{
        if(held!==press)return;press.long=true;
        if(menu)closeMenu();else if(press.id?.startsWith('app:')||press.id?.startsWith('lib:'))openMenu(press.id.slice(4));
        // Preserve the consumed press after opening/closing a menu until key-up.
        held=press;
      },HOLD);return;
    }
    if(key==='enter-up'){
      const press=held;cancelHold();if(press&&!press.long&&press.id===focusId)activate(press.id);return;
    }
    cancelHold();
    if(['left','right','up','down'].includes(key))navigate(key);
    else if(key==='back'){if(menu)closeMenu();else if(pane)closePane();else bridge.exit();}
    else if(key==='menu'){if(menu)closeMenu();else if(focusId?.startsWith('app:')||focusId?.startsWith('lib:'))openMenu(focusId.slice(4));else openPane('apps');}
    else if(key==='source'){if(pane==='inputs')closePane();else openPane('inputs');}
    else if(key==='home')window.launcherHome();
  };
  window.launcherHome=()=>{cancelHold();menu=null;pane=null;libScroll=0;render();focus(homeFirst());};
  window.refreshTV=()=>{
    cancelHold();data=JSON.parse(bridge.catalog());pref=JSON.parse(bridge.preferences());favorites=clean(pref.favorites||favorites);
    theme=pref.theme==='day'?'day':'night';motion=pref.motion!==false;
    if(menu&&!app(menu))menu=null;
    libScroll=Math.max(0,Math.min(libScroll,Math.ceil(data.apps.length/4)-LIB_ROWS));render();focus(focusId);
  };
  const keys={ArrowLeft:'left',ArrowRight:'right',ArrowUp:'up',ArrowDown:'down',Enter:'enter',Escape:'back',ContextMenu:'menu',TVInput:'source',F2:'source'};
  document.addEventListener('keydown',e=>{const key=keys[e.key];if(key){e.preventDefault();if(!e.repeat||key.match(/^(left|right|up|down)$/))window.remoteKey(key);}});
  document.addEventListener('keyup',e=>{if(e.key==='Enter'){e.preventDefault();window.remoteKey('enter-up');}});
  window.addEventListener('blur',cancelHold);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)cancelHold();});
  document.addEventListener('focusin',e=>{const target=e.target.closest('[data-f]');if(target&&focusables().includes(target)){focusId=target.dataset.f;syncFocus();}});
  document.addEventListener('click',e=>{
    const control=e.target.closest('[data-theme-choice],[data-motion-choice]');
    if(control){e.preventDefault();if(control.hasAttribute('data-theme-choice')){focusId='set:appearance';changeTheme(control.dataset.themeChoice);}else{focusId='set:motion';changeMotion(!motion);}return;}
    const target=e.target.closest('[data-f]');if(target){e.preventDefault();if(focusables().includes(target)){focus(target.dataset.f);activate(target.dataset.f);}}
    else if(e.target.closest('.mare-wordmark')){e.preventDefault();window.launcherHome();}
  });
  function row(id,children,extra={}){return h('li',{key:id,className:'tv-row',tabIndex:-1,role:'button','data-f':id,...extra},children);}
  function panelContent(){
    if(paneView==='apps'){
      return h('div',{className:'tv-library-clip'},h('ul',{className:'tv-library','data-layer':'library',style:{'--rows':Math.max(1,Math.ceil(data.apps.length/4)),transform:`translateY(${-libScroll*35}px)`}},indicator(),...sorted().map(a=>row('lib:'+a.package,[h('span',{key:'name',className:'tv-row-name'},appName(a)),h('span',{key:'pin',className:'tv-pin','aria-label':favorites.includes(a.package)?'On home':undefined})],{className:'tv-row'+(favorites.includes(a.package)?' pinned':''),'aria-label':appName(a)+(favorites.includes(a.package)?', on home':'')})),!data.apps.length?h('li',{className:'tv-panel-empty'},'No apps available'):null));
    }
    if(paneView==='inputs')return h('ul',{className:'tv-rows tv-inputs','data-layer':'inputs'},indicator(),...data.inputs.slice().sort((a,b)=>b.type-a.type||a.id.localeCompare(b.id)).map(input=>{
      const state=input.type===0?'tuner':input.state===0?'connected':input.state===1?'standby':'not connected';
      const prefix=input.label&&input.label!==input.name?input.label.toLowerCase()+' · ':'';
      return row('input:'+input.id,[h('span',{key:'name',className:'tv-row-name'},input.name),h('span',{key:'state',className:'tv-row-value'},prefix+state)],{className:'tv-row'+(input.type!==0&&input.state===2?' disconnected':input.state===0?' connected':'')});
    }),!data.inputs.length?h('li',{className:'tv-panel-empty'},data.inputError||'No inputs available · open TV settings'):null);
    const setting=(id,label,value)=>row('set:'+id,[h('span',{key:'name',className:'tv-row-label'},label),value],{role:['appearance','motion'].includes(id)?'group':'button','aria-label':label});
    return h('ul',{className:'tv-rows tv-settings','data-layer':'settings'},indicator(),
      setting('appearance','Appearance',h('div',{key:'value',className:'seg','aria-label':'Appearance'},...['night','day'].map(t=>h('button',{key:t,tabIndex:-1,'data-theme-choice':t,className:theme===t?'on':'','aria-pressed':theme===t},t)))),
      setting('motion','Motion',h('button',{key:'value',className:'switch'+(motion?' on':''),role:'switch','aria-label':'Motion','aria-checked':motion,'data-motion-choice':'toggle',tabIndex:-1})),
      setting('network','Network',h('span',{key:'value',className:'tv-row-value'},network()+' ↗')),
      setting('bluetooth','Bluetooth',h('span',{key:'value',className:'tv-row-value'},'remotes & accessories ↗')),
      setting('tv','TV settings',h('span',{key:'value',className:'tv-row-value'},'picture · sound · system ↗')),
      setting('favourites','Favourites',h('span',{key:'value',className:'tv-row-value'},`${favorites.length} of 12 on home · organise`)));
  }
  function menuContent(){
    const a=app(menuView);if(!a)return null;const i=favorites.indexOf(a.package);
    const item=(id,label,hint)=>h('button',{key:id,className:'menu-item',role:'menuitem',tabIndex:-1,'data-f':'mi:'+id},label,h('span',{className:'k'},hint));
    return [h('div',{key:'title',className:'tv-menu-title'},appName(a)),h('div',{key:'focus',className:'tv-focus menu-focus','aria-hidden':true}),
      item('open','Open','ok'),item('pin',i>=0?'Unpin from home':'Pin to home',`${favorites.length} / 12`),
      i>0?item('up','Move up','↑'):null,i>=0&&i<favorites.length-1?item('down','Move down','↓'):null,
      h('div',{key:'sep',className:'menu-sep',role:'separator'}),item('info','App info','android ↗')];
  }
  function render(){
    document.documentElement.dataset.theme=theme;
    const still=!motion||pref.systemReduced||reduced.matches;
    document.documentElement.classList.toggle('tv-still',!!still);document.body.classList.toggle('tv-still',!!still);
    document.body.classList.toggle('tv-dialog-open',!!pane);
    const now=new Date(), time=now.toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit',hour12:false}),date=now.toLocaleDateString('en-GB',{weekday:'long',day:'numeric',month:'long'});
    const titles={apps:'Apps',inputs:'Inputs',settings:'Settings'};
    const inputMeta=[data.inputs.filter(i=>i.type===1007).length+' hdmi',...(data.inputs.some(i=>i.type===1001)?['av']:[]),...(data.inputs.some(i=>i.type===0)?['tuner']:[])].join(' · ');
    const meta=paneView==='apps'?`${data.apps.length} apps · a–z`:paneView==='inputs'?inputMeta:'appearance · motion · connections';
    const footLeft=paneView==='apps'?`${favorites.length} of 12 on home`:paneView==='inputs'?'input key behaviour depends on your TV':`maré launcher ${bridge.version?bridge.version():'0.3.0'}`;
    const footRight=paneView==='apps'?'ok opens · hold ok to pin · back closes':paneView==='inputs'?'ok switches · back closes':'left / right changes · back closes';
    ReactDOM.flushSync(()=>root.render(h(Mare.Page,{variant:'arrival'},
      h('div',{className:'tv-home','data-scope':'home','aria-hidden':!!pane||!!menu},
        h(Mare.TopBar,null,h(Mare.Wordmark,{href:'#home'}),h(Mare.Nav,null,...['apps','inputs','settings'].map(p=>h(Mare.NavItem,{key:p,href:'nav:'+p,current:pane===p},p)),h('span',{className:'tv-focus underline','aria-hidden':true}))),
        h('section',{className:'tv-time','aria-label':date},h('time',null,time),h('span',null,date)),
        h('section',{className:'tv-favorites'+(!favorites.length?' tv-firstrun':''),'aria-label':'Favourites'},h(Mare.AppList,null,indicator(),...(favorites.length?favorites.map(p=>h(Mare.App,{key:p,name:appName(app(p)),purpose:purpose(app(p)),href:'app:'+p})):[h(Mare.App,{key:'first',name:'Choose your favourites',purpose:`${data.apps.length} apps installed · hold ok on any app to pin it`,href:'first:run'})]))),
        !still?h(Mare.HorizonMark):null,
        h(Mare.Foot,{left:network(),right:menu?'back closes':favorites.length?'ok opens · hold ok for options · source for inputs':'ok chooses · source for inputs'})),
      h('section',{className:'tv-panel'+(pane?' open':''),'data-scope':'pane',role:pane?'dialog':undefined,'aria-modal':pane?'true':undefined,'aria-hidden':!pane||!!menu,'aria-label':titles[paneView],tabIndex:-1},
        h('header',{className:'tv-panel-top'},h('h2',null,titles[paneView]),h('span',{className:'tv-panel-meta'},meta)),panelContent(),
        h('footer',{className:'tv-panel-foot'},h('span',null,footLeft),h('span',null,footRight))),
      h('div',{className:'tv-menu menu'+(menu?' open':''),'data-scope':'menu','data-layer':'menu',role:'menu','aria-label':menuView&&app(menuView)?appName(app(menuView))+' options':'App options','aria-hidden':!menu},menuContent()),
      h('div',{className:'toast'+(toast?' show':''),role:'status','aria-live':'polite'},toast?h(React.Fragment,null,h('span',{className:'tk'},toast.kind),h('span',null,toast.text)):null))));
    // The published primitives intentionally expose a small prop API. Decorate their links here.
    for(const e of document.querySelectorAll('a[href]')){const id=e.getAttribute('href');if(id!=='#home')e.dataset.f=id;else e.tabIndex=-1;}
    document.querySelector('.mare-nav').dataset.layer='nav';document.querySelector('.mare-applist').dataset.layer='home-grid';
    syncFocus();placeMenu();
  }
  reduced.addEventListener('change',()=>{render();focus(focusId);});
  function fit(){document.documentElement.style.setProperty('--tv-scale',Math.min(innerWidth/960,innerHeight/540));syncFocus();placeMenu();}
  window.addEventListener('resize',fit);
  fit();
  render();focus(homeFirst());document.fonts.ready.then(()=>{syncFocus();placeMenu();});
  setInterval(()=>render(),30000);
})();
