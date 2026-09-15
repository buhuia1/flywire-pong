'use strict';
const $=id=>document.getElementById(id);
const classLabels={central:'中枢',optic:'视叶',sensory:'感觉',visual_projection:'视觉投射',ascending:'上行',descending:'下行',sensory_ascending:'感觉上行',visual_centrifugal:'视觉离心',motor:'运动',endocrine:'内分泌',unknown:'未标注'};
const palette=['#8ebfea','#b9a4ec','#8cc8bd','#c5b69c','#cfa4b3','#badba4','#e6af81','#e0cc93','#8a9d90','#afc8e1','#edb7ce'];
const hex=v=>[1,3,5].map(i=>parseInt(v.slice(i,i+2),16)/255);
const brainCanvas=$('brain'),pongCanvas=$('pong'),ctx=pongCanvas.getContext('2d');
let geometry,replay,activity,gl,program,positions,colors,colorBuffer,mode='anatomy',selected=-1;
let angleX=.16,angleY=.05,zoom=1.1,pointer=null,interacted=true,brainDirty=true,lastActivity=-1;
let playing=!matchMedia('(prefers-reduced-motion: reduce)').matches,time=0,lastDraw=0,brainVisible=true,gameVisible=false;
const defaultSelection='点选查看神经元 ID、细胞类型与实测坐标。';
const observer=new IntersectionObserver(entries=>{for(const e of entries){if(e.target===brainCanvas)brainVisible=e.isIntersecting;else gameVisible=e.isIntersecting;}},{rootMargin:'100px'});
observer.observe(brainCanvas);observer.observe(pongCanvas);

function shader(type,source){const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error('三维着色器初始化失败');return s;}
function setupBrain(){
 gl=brainCanvas.getContext('webgl',{alpha:false,antialias:true,powerPreference:'low-power'});
 if(!gl)throw Error('此浏览器未开启 WebGL。可继续看游戏实录，在电脑安装版中查看三维脑图。');
 const vertex=shader(gl.VERTEX_SHADER,'attribute vec3 a_pos;attribute vec4 a_color;uniform vec2 u_angle;uniform float u_aspect,u_zoom,u_dpr;varying vec4 v_color;void main(){vec3 p=a_pos;float sx=sin(u_angle.x),cx=cos(u_angle.x),sy=sin(u_angle.y),cy=cos(u_angle.y);p=vec3(p.x,p.y*cx-p.z*sx,p.y*sx+p.z*cx);p=vec3(p.x*cy+p.z*sy,p.y,-p.x*sy+p.z*cy);gl_Position=vec4(p.x*u_zoom/u_aspect,p.y*u_zoom,p.z*.2,1.);gl_PointSize=(a_color.a>.9?3.2:1.8)*u_dpr;v_color=a_color;}');
 const fragment=shader(gl.FRAGMENT_SHADER,'precision mediump float;varying vec4 v_color;void main(){vec2 p=gl_PointCoord-.5;if(dot(p,p)>.25)discard;gl_FragColor=v_color;}');
 program=gl.createProgram();gl.attachShader(program,vertex);gl.attachShader(program,fragment);gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error('三维程序初始化失败');gl.useProgram(program);
 const xyz=geometry.points.map(p=>[p[1],-p[2],p[3]]),lo=[Infinity,Infinity,Infinity],hi=[-Infinity,-Infinity,-Infinity];
 xyz.forEach(p=>p.forEach((v,k)=>{lo[k]=Math.min(lo[k],v);hi[k]=Math.max(hi[k],v);}));const center=lo.map((v,k)=>(v+hi[k])/2),scale=Math.max(...hi.map((v,k)=>v-lo[k]))/2;
 positions=new Float32Array(xyz.flatMap(p=>p.map((v,k)=>(v-center[k])/scale)));colors=new Float32Array(xyz.length*4);
 gl.bindBuffer(gl.ARRAY_BUFFER,gl.createBuffer());gl.bufferData(gl.ARRAY_BUFFER,positions,gl.STATIC_DRAW);const p=gl.getAttribLocation(program,'a_pos');gl.enableVertexAttribArray(p);gl.vertexAttribPointer(p,3,gl.FLOAT,false,0,0);
 colorBuffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,colorBuffer);const c=gl.getAttribLocation(program,'a_color');gl.enableVertexAttribArray(c);gl.vertexAttribPointer(c,4,gl.FLOAT,false,0,0);
 gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA);gl.clearColor(0,0,0,1);
 new ResizeObserver(()=>{brainDirty=true;}).observe(brainCanvas);updateColors(0);updateLegend();$('selection').textContent=defaultSelection;
}
function updateLegend(){
 const entries=mode==='anatomy'?[['实测胞体位置 · 抽样显示','#eeeeee'],['12,583 / 118,086 个有坐标节点',null]]:mode==='class'?geometry.class_names.map((name,i)=>[classLabels[name]||name,palette[i%palette.length]]):mode==='ports'?[['314 个输入胞体','#ffad70'],['191 个读出胞体','#99d5f2'],['其余抽样胞体','#48634f']]:[['≤ 10⁻⁶','#404040'],['10⁻³','#a0a0a0'],['1','#ffffff'],['模拟 |x| · a.u. · 固定对数色标',null]];
 $('legend').replaceChildren(...entries.map(([label,color])=>{const item=document.createElement('span');if(color){const dot=document.createElement('i');dot.style.background=color;item.append(dot);}item.append(document.createTextNode(label));return item;}));
}
function updateColors(frame){
 if(!program)return;const offset=frame*geometry.points.length;
 geometry.points.forEach((p,i)=>{let c;if(mode==='anatomy')c=[.92,.92,.92,.62];else if(mode==='class')c=[...hex(palette[p[4]%palette.length]),.68];else if(mode==='ports')c=p[6]&1?[...hex('#ffad70'),.99]:p[6]&2?[...hex('#99d5f2'),.99]:[.2,.32,.25,.24];else{const t=(activity?.[offset+i]||0)/255;c=[.25+.75*t,.25+.75*t,.25+.75*t,.3+.69*t];}if(i===selected)c=[1,1,1,1];colors.set(c,i*4);});
 gl.bindBuffer(gl.ARRAY_BUFFER,colorBuffer);gl.bufferData(gl.ARRAY_BUFFER,colors,gl.DYNAMIC_DRAW);brainDirty=true;
}
function drawBrain(){
 if(!program)return;const dpr=Math.min(devicePixelRatio||1,2),w=Math.round(brainCanvas.clientWidth*dpr),h=Math.round(brainCanvas.clientHeight*dpr);
 if(brainCanvas.width!==w||brainCanvas.height!==h){brainCanvas.width=w;brainCanvas.height=h;}
 gl.viewport(0,0,w,h);gl.clear(gl.COLOR_BUFFER_BIT);gl.uniform2f(gl.getUniformLocation(program,'u_angle'),angleX,angleY);gl.uniform1f(gl.getUniformLocation(program,'u_aspect'),w/h);gl.uniform1f(gl.getUniformLocation(program,'u_zoom'),zoom);gl.uniform1f(gl.getUniformLocation(program,'u_dpr'),dpr);gl.drawArrays(gl.POINTS,0,geometry.points.length);brainDirty=false;
}
function pick(e){
 if(!positions)return;const rect=brainCanvas.getBoundingClientRect(),cx=e.clientX-rect.left,cy=e.clientY-rect.top,sx=Math.sin(angleX),ax=Math.cos(angleX),sy=Math.sin(angleY),ay=Math.cos(angleY);let best=14**2,found=-1;
 geometry.points.forEach((p,i)=>{const x=positions[3*i],y=positions[3*i+1]*ax-positions[3*i+2]*sx,z=positions[3*i+1]*sx+positions[3*i+2]*ax,rx=x*ay+z*sy,px=rect.width/2+rx*zoom*rect.height/2,py=rect.height/2-y*zoom*rect.height/2,d=(px-cx)**2+(py-cy)**2;if(d<best){best=d;found=i;}});
 selected=found;updateColors(Math.max(0,lastActivity));if(found<0){$('selection').textContent=defaultSelection;return;}const p=geometry.points[found];$('selection').textContent=`ID ${p[0]} · ${p[5]} · ${classLabels[geometry.class_names[p[4]]]} · (${p[1]}, ${p[2]}, ${p[3]}) μm`;
}
brainCanvas.onpointerdown=e=>{interacted=true;pointer={x:e.clientX,y:e.clientY,startX:e.clientX,startY:e.clientY};brainCanvas.setPointerCapture(e.pointerId);};
brainCanvas.onpointermove=e=>{if(!pointer)return;angleY+=(e.clientX-pointer.x)*.007;angleX+=(e.clientY-pointer.y)*.007;pointer.x=e.clientX;pointer.y=e.clientY;brainDirty=true;};
brainCanvas.onpointerup=e=>{if(pointer&&Math.hypot(e.clientX-pointer.startX,e.clientY-pointer.startY)<5)pick(e);pointer=null;};brainCanvas.onpointercancel=()=>{pointer=null;};
brainCanvas.addEventListener('wheel',e=>{e.preventDefault();interacted=true;zoom=Math.max(.65,Math.min(2.2,zoom*Math.exp(-e.deltaY*.001)));brainDirty=true;},{passive:false});
brainCanvas.onkeydown=e=>{if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','+','-'].includes(e.key))return;e.preventDefault();interacted=true;if(e.key==='ArrowLeft')angleY-=.1;if(e.key==='ArrowRight')angleY+=.1;if(e.key==='ArrowUp')angleX-=.1;if(e.key==='ArrowDown')angleX+=.1;if(e.key==='+')zoom=Math.min(2.2,zoom+.1);if(e.key==='-')zoom=Math.max(.65,zoom-.1);brainDirty=true;};
$('reset-view').onclick=()=>{angleX=.16;angleY=.05;zoom=1.1;selected=-1;interacted=true;$('selection').textContent=defaultSelection;updateColors(Math.max(0,lastActivity));};
document.querySelectorAll('[data-color]').forEach(button=>{button.onclick=()=>{mode=button.dataset.color;document.querySelectorAll('[data-color]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));updateLegend();updateColors(Math.max(0,lastActivity));};});

function drawGame(){
 if(!replay)return;const dpr=Math.min(devicePixelRatio||1,2),w=pongCanvas.clientWidth,h=w/1.7;if(pongCanvas.width!==Math.round(w*dpr)||pongCanvas.height!==Math.round(h*dpr)){pongCanvas.width=Math.round(w*dpr);pongCanvas.height=Math.round(h*dpr);}ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
 const margin=24,cw=w-margin*2,ch=h-64,top=43,X=x=>margin+x*cw,Y=y=>top+y*ch;
 ctx.strokeStyle='#303030';ctx.lineWidth=1;ctx.strokeRect(margin,top,cw,ch);ctx.setLineDash([4,7]);ctx.beginPath();ctx.moveTo(X(.5),top);ctx.lineTo(X(.5),top+ch);ctx.stroke();ctx.setLineDash([]);
 const index=Math.min(replay.frames.length-1,Math.floor(time/replay.dt)),f=replay.frames[index],next=replay.frames[Math.min(index+1,replay.frames.length-1)],fraction=(time/replay.dt-index);let bx=f[0],by=f[1],paddle=f[4];
 if(Math.abs(next[0]-bx)<.13&&Math.abs(next[1]-by)<.13){bx+=(next[0]-bx)*fraction;by+=(next[1]-by)*fraction;}paddle+=(next[4]-paddle)*fraction;
 ctx.font=`${Math.max(9,w/70)}px "Segoe UI","Microsoft YaHei",sans-serif`;ctx.fillStyle='#dddddd';ctx.textAlign='left';ctx.fillText('FLYWIRE / 左拍',margin,24);ctx.textAlign='right';ctx.fillStyle='#777777';ctx.fillText('反弹墙',w-margin,24);ctx.textAlign='center';ctx.fillStyle='#bbbbbb';ctx.fillText(`接中 ${f[5]}  ·  漏球 ${f[6]}`,w/2,24);
 ctx.fillStyle='#eeeeee';ctx.fillRect(X(.055)-3,Y(paddle-replay.paddle_half),6,ch*replay.paddle_half*2);ctx.fillStyle='#777777';ctx.fillRect(X(1)-3,top,3,ch);ctx.fillStyle='#ffffff';ctx.beginPath();ctx.arc(X(bx),Y(by),Math.max(3.3,.012*ch),0,Math.PI*2);ctx.fill();
 $('timeline').value=String(time);$('timestamp').textContent=`00:${String(Math.floor(time)).padStart(2,'0')} / 00:30`;
}
function updatePlayback(){const text=playing?'暂停实录':'播放实录';$('play').textContent=playing?'Ⅱ':'▶';$('play').setAttribute('aria-label',text);$('replay-status').textContent=playing?'30 秒循环 · 已记录':'实录已暂停';}
$('play').onclick=()=>{playing=!playing;updatePlayback();};$('timeline').oninput=e=>{time=Number(e.target.value);drawGame();lastActivity=-1;};
function tick(now){
 requestAnimationFrame(tick);if(document.hidden||now-lastDraw<1000/30)return;const renderElapsed=lastDraw?Math.min((now-lastDraw)/1000,.1):0;lastDraw=now;
 if(playing&&replay&&(brainVisible||gameVisible))time=(time+renderElapsed)%replay.duration_seconds;
 const clock='T+00:'+String(Math.floor(time)).padStart(2,'0');if($('mission-clock').textContent!==clock)$('mission-clock').textContent=clock;
 if(brainVisible){const a=replay?Math.min(replay.activity_frames-1,Math.floor(time/replay.activity_dt)):0;if(mode==='activity'&&a!==lastActivity){lastActivity=a;updateColors(a);}if(playing&&!interacted){angleY+=renderElapsed*.025;brainDirty=true;}if(brainDirty)drawBrain();}
 if(gameVisible&&replay)drawGame();
}
$('share').onclick=async()=>{const text='GitHub 搜索 buhuia1/flywire-pong，下载 Windows 安装包，装好后离线玩！\n手机看 Demo + 可旋转的果蝇神经元图：https://buhuia1.github.io/flywire-pong/\n安装包：https://github.com/buhuia1/flywire-pong/releases/latest';try{await navigator.clipboard.writeText(text);$('copy-status').textContent='已复制口令与链接';}catch{$('copy-status').textContent='请长按复制上方口令，或分享当前页面链接。';}};
(async()=>{
 try{const r=await fetch('assets/brain-data.json');if(!r.ok)throw Error('坐标数据加载失败');geometry=await r.json();setupBrain();drawBrain();}catch(e){$('selection').textContent=e.message;}
 try{const results=await Promise.all([fetch('assets/replay.json'),fetch('assets/activity.bin')]);if(results.some(r=>!r.ok))throw Error('实录加载失败，请刷新页面');replay=await results[0].json();activity=new Uint8Array(await results[1].arrayBuffer());if(activity.length!==replay.activity_frames*replay.displayed_somas)throw Error('活动记录长度不匹配');updatePlayback();drawGame();lastActivity=-1;}catch(e){$('replay-status').textContent=e.message;}
 requestAnimationFrame(tick);
})();
