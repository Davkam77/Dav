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

const topic = process.argv[2]?.toLowerCase() || "";
const minPrice = parseInt(process.argv[3]) || 0;
const topicTranslations = {
  'программирование': 'programming',
  'дизайн': 'design',
  'перевод': 'translation'
};
const searchTopic = topicTranslations[topic] || topic;

async function wait(ms, msg = "") {
  if (msg) logger.info(msg);
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function simulateHumanBehavior(page) {
  const viewport = page.viewport();
  const width = viewport?.width || 1280;
  const height = viewport?.height || 800;
  for (let i = 0; i < 3; i++) {
    await page.mouse.move(Math.random() * width, Math.random() * height);
    await wait(Math.random() * 500 + 200, 'Случайное движение мыши');
  }
  await page.evaluate(() => window.scrollBy(0, Math.random() * 500));
  await wait(1000, 'Случайная прокрутка');
}

async function scrollPage(page) {
  let previousHeight = 0;
  for (let i = 0; i < 10; i++) {
    await page.evaluate(() => window.scrollBy(0, window.innerHeight));
    await wait(2000, `🔽 Прокрутка ${i + 1}`);
    const currentHeight = await page.evaluate(() => document.body.scrollHeight);
    if (currentHeight === previousHeight) break;
    previousHeight = currentHeight;
  }
}

function parseBudget(text) {
  if (!text || typeof text !== 'string') return NaN;
  text = text.replace(/[^\d,.-]/g, '');
  const rangeMatch = text.match(/(\d+,?\d*)-(\d+,?\d*)/);
  if (rangeMatch) {
    return parseFloat(rangeMatch[1].replace(/,/g, ''));
  }
  const singleMatch = text.match(/(\d+,?\d*)/);
  if (singleMatch) {
    return parseFloat(singleMatch[1].replace(/,/g, ''));
  }
  return NaN;
}

async function gotoWithRetry(page, url, options, retries = 3) {
  for (let i = 0; i < retries; i++) {
    try {
      return await page.goto(url, options);
    } catch (e) {
      logger.warn(`Попытка ${i + 1} не удалась: ${e.message}`);
      await wait(5000, 'Повтор через 5 секунд');
    }
  }
  throw new Error(`Не удалось загрузить ${url} после ${retries} попыток`);
}

(async () => {
  const TIMEOUT_LIMIT = 180000;
  const jobs = [];
  let browser;

  try {
    await Promise.race([
      (async () => {
        logger.info('🚀 Запуск Puppeteer для Upwork');
        browser = await puppeteer.launch({ headless: false });
        const page = await browser.newPage();
        await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');

        const searchUrl = `https://www.upwork.com/nx/jobs/search/?q=${encodeURIComponent(searchTopic)}`;
        logger.info(`🌐 Открываем: ${searchUrl}`);
        await gotoWithRetry(page, searchUrl, { waitUntil: 'networkidle2', timeout: 40000 });

        await wait(3000, '⏳ Перед скроллингом');
        await simulateHumanBehavior(page);
        await scrollPage(page);
        await wait(3000, '⏳ После скроллинга');

        const jobLinks = await page.$$eval('a[href*="/jobs/"]', links =>
          [...new Set(links.map(a => a.href))].filter(href => href.includes('/jobs/'))
        );
        logger.info(`🔗 Найдено ${jobLinks.length} ссылок`);

        for (const link of jobLinks) {
          try {
            logger.info(`➡ Открываем карточку: ${link}`);
            await gotoWithRetry(page, link, { waitUntil: 'domcontentloaded', timeout: 30000 });
            await simulateHumanBehavior(page);
            await page.waitForNetworkIdle({ idleTime: 1000, timeout: 30000 }).catch(() => logger.warn('Сеть не стабилизировалась'));

            const title = await page.$eval('h1', el => el.innerText).catch(() => 'Без названия');
            const description = await page.$eval('.text-body-sm', el => el.innerText).catch(() => 'Нет описания');
            const duration = await page.$eval('li[data-cy="duration4"] strong', el => el.innerText).catch(() => '—');
            const experience = await page.$eval('li[data-cy="expertise"] strong', el => el.innerText).catch(() => '—');
            const hours_per_week = await page.$eval('li[data-cy="clock-hourly"] strong', el => el.innerText).catch(() => '—');
            const location = await page.$eval('.text-light-on-muted span', el => el.innerText).catch(() => '—');

            const priceMin = await page.$$eval(
              'div[data-test="BudgetAmount"] strong, li[data-cy="fixed-price"] strong, li[data-cy="clock-timelog"] strong',
              els => els.map(e => e.innerText).filter(text => text.includes('$'))
            ).catch(() => []);

            const budgetText = priceMin.length ? `$${priceMin[0]}${priceMin[1] ? ' - ' + priceMin[1] : ''}` : '—';
            const parsedPrice = parseBudget(priceMin[0]);

            if (isNaN(parsedPrice)) {
              jobs.push({
                id: link,
                title: `Upwork: ${title}`,
                budget: budgetText,
                description,
                duration,
                experience,
                hours_per_week,
                location,
                link,
                note: 'Бюджет не распознан'
              });
              logger.warn(`⚠️ Добавлено с нераспознанным бюджетом: ${title}`);
            } else if (parsedPrice >= minPrice) {
              jobs.push({
                id: link,
                title: `Upwork: ${title}`,
                budget: budgetText,
                description,
                duration,
                experience,
                hours_per_week,
                location,
                link
              });
              logger.info(`✅ Добавлено: ${title} за ${budgetText}`);
            } else {
              logger.info(`⛔ Пропущено: ${title} — $${parsedPrice} < $${minPrice}`);
            }
          } catch (e) {
            logger.warn(`⚠️ Ошибка карточки ${link}: ${e.message}`);
          }
        }

        const outputPath = path.resolve(__dirname, '../results/upwork.json');
        await fs.mkdir(path.dirname(outputPath), { recursive: true });
        await fs.writeFile(outputPath, JSON.stringify(jobs, null, 2), 'utf-8');
        logger.info('💾 Сохранено в upwork.json');
        console.log(JSON.stringify(jobs));
      })(),
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error("⏳ Парсинг превысил лимит 2 минуты")), TIMEOUT_LIMIT)
      )
    ]);
  } catch (err) {
    logger.error(`❌ Глобальная ошибка: ${err.message}`);
  } finally {
    if (browser) {
      await wait(3000, '🕒 Завершение сессии');
      await browser.close();
      logger.info('🔒 Браузер закрыт');
    }
  }
})();