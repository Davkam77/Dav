require('dotenv').config({ path: require('path').resolve(__dirname, '../.env') });
const fs = require('fs').promises;
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const path = require('path');
const winston = require('winston');

puppeteer.use(StealthPlugin());

const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.printf(({ timestamp, level, message }) => `${timestamp} - ${level.toUpperCase()} - ${message}`)
  ),
  transports: [
    new winston.transports.File({ filename: 'logs/app.log' }),
    new winston.transports.Console()
  ]
});

const topic = (process.argv[2] || '').toLowerCase();
const minPrice = parseInt(process.argv[3]) || 0;
const jobs = [];

function wait(ms, msg) {
  if (msg) logger.info(msg);
  return new Promise(r => setTimeout(r, ms));
}

function parseBudget(text) {
  const match = text?.match(/\$[\s]*([\d,.]+)/);
  return match ? parseFloat(match[1].replace(/,/g, '')) : NaN;
}

(async () => {
  let browser;
  try {
    logger.info('🚀 Запуск Puppeteer для Upwork');
    browser = await puppeteer.launch({ headless: false });
    const page = await browser.newPage();
    await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64)...');

    const url = `https://www.upwork.com/nx/jobs/search/?q=${encodeURIComponent(topic)}`;
    logger.info(`🌐 Переход на: ${url}`);
    await page.goto(url, { waitUntil: 'networkidle2', timeout: 60000 });

    let lastHeight = await page.evaluate('document.body.scrollHeight');
    for (let i = 0; i < 5; i++) {
      await page.evaluate('window.scrollTo(0, document.body.scrollHeight)');
      await wait(2000, '📜 Прокрутили страницу вниз');
      const newHeight = await page.evaluate('document.body.scrollHeight');
      if (newHeight === lastHeight) break;
      lastHeight = newHeight;
    }

    const links = await page.$$eval('a[data-test="job-tile-title-link UpLink"]', els =>
      [...new Set(els.map(el => el.href))]);

    logger.info(`🔗 Найдено ссылок: ${links.length}`);

    for (const link of links) {
      try {
        await page.goto(link, { waitUntil: 'domcontentloaded', timeout: 60000 });
        await wait(10000, `📄 Чтение карточки: ${link}`);

        const title = await page.$eval('h1', el => el.innerText).catch(() => 'Без названия');

        const description = await page.$$eval('p', els =>
          els.map(el => el.innerText).join('\n')
        ).catch(() => 'Нет описания');

        const budgetText = await page.$$eval('*', els =>
          els.map(el => el.innerText).find(txt => /\$\s*\d+/.test(txt)) || '—'
        ).catch(() => '—');

        const parsedPrice = parseBudget(budgetText);

        if (isNaN(parsedPrice)) {
          logger.warn(`⚠️ Цена не найдена: ${budgetText}`);
          jobs.push({ title: `Upwork: ${title}`, budget: 'неизвестно', description, link });
        } else if (parsedPrice >= minPrice) {
          jobs.push({ title: `Upwork: ${title}`, budget: `$${parsedPrice}`, description, link });
          logger.info(`✅ Добавлено: ${title} ($${parsedPrice})`);
        } else {
          logger.info(`⛔ Пропущено: $${parsedPrice} < $${minPrice}`);
        }

      } catch (err) {
        logger.warn(`⚠️ Ошибка карточки: ${link} — ${err.message}`);
      }
    }

    const outputPath = path.resolve(__dirname, '../results/upwork.json');
    await fs.mkdir(path.dirname(outputPath), { recursive: true });
    await fs.writeFile(outputPath, JSON.stringify(jobs, null, 2), 'utf-8');
    logger.info('📦 Сохранено в upwork.json');
    console.log(JSON.stringify(jobs));

  } catch (err) {
    logger.error(`❌ Ошибка: ${err.message}`);
  } finally {
    if (browser) {
      await wait(10000, '📴 Закрытие браузера');
      await browser.close();
    }
  }
})();