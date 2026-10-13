const {chromium}=require('C:/Users/MECHREVO/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{const browser=await chromium.launch({headless:true,ignoreDefaultArgs:["--hide-scrollbars"],executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
const page=await browser.newPage({viewport:{width:600,height:1000},deviceScaleFactor:1});
await page.goto('file:///E:/Code/Bentley_Python_plugin/资料/型钢构件及支吊架模型生成工具-UI-原型-v4.html');
console.log(await page.evaluate(()=>Object.fromEntries(['.titlebar','.header','.toolbar','.content','.footer','.sec-h','.r-item','.item','.stats'].map(s=>{const r=document.querySelector(s).getBoundingClientRect();return [s,{x:r.x,y:r.y,w:r.width,h:r.height}]}))));
await page.locator('.win').screenshot({path:'prototype-400-880.png'});
await browser.close();})();
