const {chromium}=require('C:/Users/MECHREVO/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{const browser=await chromium.launch({headless:true,ignoreDefaultArgs:['--hide-scrollbars'],executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
const page=await browser.newPage({viewport:{width:600,height:1000}});
await page.goto('file:///E:/Code/Bentley_Python_plugin/资料/型钢构件及支吊架模型生成工具-UI-原型-v4.html');
await page.evaluate(()=>showView('q1'));
await page.addStyleTag({content:'.view{animation:none!important;transform:none!important;opacity:1!important}'});
console.log(await page.evaluate(()=>Object.fromEntries(['.titlebar','#q1 .mhead','#q1 .mscroll','#q1 .dock','#q1 .card-h','#q1 .card-b','#q1 .res','#q1 .actions','.footer'].map(s=>{const r=document.querySelector(s).getBoundingClientRect(),w=document.querySelector('.win').getBoundingClientRect();return [s,{x:r.x-w.x,y:r.y-w.y,w:r.width,h:r.height}]}))));
await page.locator('.win').screenshot({path:'q1-prototype-400-880.png'});await browser.close();})();
