const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs').promises;
const path = require('path');

puppeteer.use(StealthPlugin());

(async () => {
  const browser = await puppeteer.launch({ headless: false });
  const page = await browser.newPage();

  // Переход на страницу логина Upwork
  await page.goto('https://www.upwork.com/ab/account-security/login', { waitUntil: 'networkidle2' });

  console.log('🔐 Войдите вручную в Upwork, затем нажмите ENTER в терминале');

  process.stdin.once('data', async () => {
    const cookies = await page.cookies();
    const cookiesPath = path.resolve(__dirname, 'upwork_cookies.json');
    await fs.writeFile(cookiesPath, JSON.stringify(cookies, null, 2));
    console.log('✅ Cookies сохранены в upwork_cookies.json');
    await browser.close();
    process.exit(1);
  });
})();
