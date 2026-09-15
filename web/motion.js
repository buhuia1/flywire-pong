/* Presentation only: predict between server samples; server decides all scores. */
(function(root){
 'use strict';
 function projectBall(game,seconds){
  const b=game.ball;if(game.waiting_serve)return {...b};
  let t=Math.max(0,Math.min(.2,seconds));
  // Do not predict an unknown paddle collision or score.
  const face=b.vx<0?.067:game.opponent==='human'?.933:.988;
  if(b.vx!==0)t=Math.min(t,Math.max(0,(face-b.x)/b.vx));
  const span=.976,period=span*2;
  let folded=((b.y+b.vy*t-.012)%period+period)%period;
  const y=.012+(folded<=span?folded:period-folded);
  return {...b,x:b.x+b.vx*t,y};
 }
 const api={projectBall};
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
 else root.PongMotion=api;
})(typeof window!=='undefined'?window:globalThis);
