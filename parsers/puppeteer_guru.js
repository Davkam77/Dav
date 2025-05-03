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

const topic = process.argv[2].toLowerCase();
const minPrice = parseInt(process.argv[3]) || 0;

async function wait(ms, message) {
  if (message) logger.info(message);
  return new Promise(resolve => setTimeout(resolve, ms));
}

function parseBudget(text) {
  if (!text || typeof text !== 'string') return 0;
  const underMatch = text.match(/Under\s*\$\s*(\d+)/i);
  if (underMatch) return parseFloat(underMatch[1]);
  const dollarMatch = text.match(/\$\s*([\d,.]+)/);
  if (dollarMatch) return parseFloat(dollarMatch[1].replace(/,/g, ''));
  return 0;
}

(async () => {
  let browser;
  const jobs = [];

  try {
    logger.info('🚀 Запуск Puppeteer');
    browser = await puppeteer.launch({ headless: false });
    const page = await browser.newPage();
    await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64)...');

    // Загрузка cookies
    const cookiesPath = path.resolve(__dirname, 'guru_cookies.json');
    try {
      const cookies = JSON.parse(await fs.readFile(cookiesPath));
      await page.setCookie(...cookies);
      logger.info("✅ Cookies загружены");
    } catch {
      logger.warn("⚠️ Cookies не найдены");
    }

    await page.goto('https://www.guru.com/work/', { waitUntil: 'networkidle2', timeout: 60000 });
    logger.info('🟢 Открыт сайт guru.com');

    const input = await page.$('input[aria-label="Search freelance jobs"]');
    if (input) {
      await input.click({ clickCount: 3 });
      await input.type(topic, { delay: 50 });
    }

    const button = await page.$('[id="13_searchBtnTop"]');
    if (button) {
      await Promise.all([
        page.waitForNavigation({ waitUntil: 'domcontentloaded', timeout: 80000 }).catch(() => logger.warn('⚠️ Навигация не сработала')),
        button.click()
      ]);
    }

    await wait(3000, '📥 Ждём результаты');

    let lastHeight = await page.evaluate('document.body.scrollHeight');
    for (let i = 0; i < 5; i++) {
      await page.evaluate('window.scrollTo(0, document.body.scrollHeight)');
      await wait(2000, '📜 Прокрутили страницу вниз');
      const newHeight = await page.evaluate('document.body.scrollHeight');
      if (newHeight === lastHeight) break;
      lastHeight = newHeight;
    }

    const jobLinks = await page.$$eval('a[href^="/work/detail/"]', (links, topic) =>
      [...new Set(
        links.filter(a => a.innerText.toLowerCase().includes(topic)).map(a => "https://www.guru.com" + a.getAttribute("href"))
      )], topic);

    logger.info(`🧲 Найдено карточек: ${jobLinks.length}`);

    for (const link of jobLinks) {
      try {
        await page.goto(link, { waitUntil: 'domcontentloaded', timeout: 60000 });
        await wait(10000, `📄 Чтение карточки: ${link}`);

        const rawTitle = await page.$eval('h1.jobHeading__title', el => el.innerText).catch(() => 'Без названия');
        const title = rawTitle.trim();

        const description = await page.$$eval('p', els =>
          els.map(el => el.innerText).join('\n')
        ).catch(() => 'Нет описания');

        const budgetText = await page.$$eval('div', els =>
          els.map(el => el.innerText).find(text => /(\$\d+|\bUnder \$\d+)/.test(text)) || '—'
        ).catch(() => '—');

        const parsedPrice = parseBudget(budgetText);
        if (parsedPrice >= minPrice) {
          jobs.push({
            title: `Guru: ${title}`,
            budget: parsedPrice ? `$${parsedPrice}` : "неизвестно",
            description: description.slice(0, 1000),
            link
          });
          logger.info(`✅ Добавлено: ${title} ($${parsedPrice})`);
        } else {
          logger.info(`⛔ Пропущено: $${parsedPrice} < $${minPrice}`);
        }
      } catch (err) {
        logger.warn(`⚠️ Ошибка карточки: ${link} — ${err.message}`);
      }
    }

    const outputPath = path.resolve(__dirname, '../results/guru.json');
    await fs.mkdir(path.dirname(outputPath), { recursive: true });
    await fs.writeFile(outputPath, JSON.stringify(jobs, null, 2), 'utf-8');
    logger.info('📦 Результаты сохранены');
    console.log(JSON.stringify(jobs));

  } catch (e) {
    logger.error(`❌ Ошибка: ${e.message}`);
  } finally {
    if (browser) {
      await wait(10000, '📴 Закрытие браузера');
      await browser.close();
    }
  }
})();