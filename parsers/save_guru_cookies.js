const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs').promises;
const path = require('path');

puppeteer.use(StealthPlugin());

(async () => {
  const browser = await puppeteer.launch({ headless: false });
  const page = await browser.newPage();
  await page.goto('https://www.guru.com/login.aspx', { waitUntil: 'networkidle2' });

  console.log('🔐 Войдите вручную, затем нажмите ENTER в терминале');
  process.stdin.once('data', async () => {
    const cookies = await page.cookies();
    const cookiesPath = path.resolve(__dirname, 'guru_cookies.json');
    await fs.writeFile(cookiesPath, JSON.stringify(cookies, null, 2));
    console.log('✅ Cookies сохранены в guru_cookies.json');
    await browser.close();
    process.exit(1);
  });
})();
