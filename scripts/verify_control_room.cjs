const {chromium}=require('../.runtime/browser/node_modules/playwright');
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:process.env.STUDIO_BROWSER || 'C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe'});
  const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
  async function goTo(surface) {
    if(await page.locator('#mobile-menu').isVisible() && await page.locator('#mobile-menu').getAttribute('aria-expanded') !== 'true') await page.locator('#mobile-menu').click();
    await page.locator(`nav [data-view=${surface}]`).click();
  }
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8017/#sources');
  await page.getByText('● Connected',{exact:true}).waitFor();
  await page.locator('[data-document]').filter({hasText:/demo/i}).first().click();
  await page.locator('#setup-plan:not([disabled])').waitFor();
  await page.locator('#setup-plan').click();
  await page.locator('#setup-form [name=subject]').fill('Biology');
  await page.locator('#setup-form [name=class_id]').fill('BROWSER-SETUP');
  await page.locator('#setup-form [name=term_start]').fill('2026-11-02');
  await page.locator('#setup-form [name=term_end]').fill('2026-11-27');
  await page.screenshot({path:'.runtime/studio-setup.png',fullPage:true});
  await page.locator('#setup-form [type=submit]').click();
  await page.waitForFunction(()=>!document.getElementById('setup-dialog').open,{timeout:30000});
  await page.locator('#overview-content').getByText('Biology / BROWSER-SETUP',{exact:true}).waitFor();
  if((await page.locator('#plan-switcher').innerText()).includes('Invalid Date'))throw new Error('Invalid plan timestamps');
  const saved=await page.locator('#plan-switcher').inputValue();
  const ids=await page.locator('#plan-switcher option').evaluateAll(opts=>opts.map(o=>o.value));
  await page.locator('#plan-switcher').selectOption(ids.find(id=>id!==saved));
  await page.waitForFunction(()=>!document.querySelector('#overview-content').textContent.includes('BROWSER-SETUP'));
  await page.locator('#plan-switcher').selectOption(saved);
  await page.locator('#overview-content').getByText('Biology / BROWSER-SETUP',{exact:true}).waitFor();
  await page.evaluate(()=>scrollTo(0,0));
  await page.screenshot({path:'.runtime/studio-overview-final.png'});
  await page.keyboard.press('Control+k');await page.locator('#palette[open]').waitFor();await page.keyboard.press('Escape');
  for(const surface of ['overview','plan','sources','evidence']){
    await page.setViewportSize({width:390,height:844});await goTo(surface);
    if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw new Error(`Mobile overflow: ${surface}`);
  }
  await browser.close();if(errors.length)throw new Error(errors.join('\n'));
  console.log('Control room passed: source setup, saved-plan switching, timestamps, keyboard palette, all four mobile surfaces.');
})().catch(e=>{console.error(e);process.exit(1)});
