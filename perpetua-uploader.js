/**
 * Perpetua Goal Uploader - Browser Automation Script
 *
 * Automates the creation of goals in Perpetua using Playwright.
 * Reads from agent_task_list.csv and creates goals through the UI.
 *
 * Usage: node perpetua-uploader.js [--start-row=N] [--dry-run]
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const readline = require('readline');
const csv = require('csv-parse/sync');

// Configuration
const CONFIG = {
  loginUrl: 'https://app.perpetua.io/login/',
  baseUrl: 'https://app.perpetua.io',
  csvPath: path.join(__dirname, 'agent_task_list.csv'),
  progressFile: path.join(__dirname, 'upload_progress.json'),
  slowMo: 100, // Slow down actions by 100ms for reliability
  timeout: 60000, // 60 second timeout for operations
  // Preset credentials (set to null to prompt)
  email: 'jana@pipingrock.com',
  password: '%Qj#N!PG7Uu9Yxj$FrG3Tw',
};

// Prompt for user input
async function prompt(question) {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });
  return new Promise((resolve) => {
    rl.question(question, (answer) => {
      rl.close();
      resolve(answer);
    });
  });
}

// Prompt for password (hidden)
async function promptPassword(question) {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  return new Promise((resolve) => {
    process.stdout.write(question);
    let password = '';

    process.stdin.setRawMode(true);
    process.stdin.resume();
    process.stdin.setEncoding('utf8');

    const onData = (char) => {
      if (char === '\n' || char === '\r' || char === '\u0004') {
        process.stdin.setRawMode(false);
        process.stdin.removeListener('data', onData);
        rl.close();
        console.log();
        resolve(password);
      } else if (char === '\u007F' || char === '\b') {
        // Backspace
        if (password.length > 0) {
          password = password.slice(0, -1);
          process.stdout.write('\b \b');
        }
      } else if (char === '\u0003') {
        // Ctrl+C
        process.exit();
      } else {
        password += char;
        process.stdout.write('*');
      }
    };

    process.stdin.on('data', onData);
  });
}

// Load CSV data
function loadGoals() {
  const content = fs.readFileSync(CONFIG.csvPath, 'utf-8');
  const records = csv.parse(content, {
    columns: true,
    skip_empty_lines: true,
    trim: true,
  });
  return records;
}

// Save progress
function saveProgress(rowIndex, goalName, status) {
  const progress = {
    lastRowIndex: rowIndex,
    lastGoalName: goalName,
    status: status,
    timestamp: new Date().toISOString(),
  };
  fs.writeFileSync(CONFIG.progressFile, JSON.stringify(progress, null, 2));
}

// Load progress
function loadProgress() {
  if (fs.existsSync(CONFIG.progressFile)) {
    return JSON.parse(fs.readFileSync(CONFIG.progressFile, 'utf-8'));
  }
  return null;
}

// Parse command line arguments
function parseArgs() {
  const args = {
    startRow: 0,
    dryRun: false,
    limit: 0, // 0 = no limit
  };

  for (const arg of process.argv.slice(2)) {
    if (arg.startsWith('--start-row=')) {
      args.startRow = parseInt(arg.split('=')[1], 10);
    } else if (arg.startsWith('--limit=')) {
      args.limit = parseInt(arg.split('=')[1], 10);
    } else if (arg === '--dry-run') {
      args.dryRun = true;
    }
  }

  return args;
}

// Main automation class
class PerpetuaUploader {
  constructor(page) {
    this.page = page;
  }

  async login(email, password) {
    console.log('Logging in to Perpetua...');
    await this.page.goto(CONFIG.loginUrl);

    // Wait for page to fully load (SPA)
    console.log('  Waiting for page to load...');
    await this.page.waitForLoadState('domcontentloaded');
    await this.page.waitForTimeout(3000); // Give React/SPA time to render

    // Debug: show what inputs are on the page
    const inputs = await this.page.$$('input');
    console.log(`  Found ${inputs.length} input fields on page`);

    // Try multiple selector strategies
    console.log('  Looking for email field...');
    let emailInput = await this.page.$('input[type="email"]');
    if (!emailInput) emailInput = await this.page.$('input[name="email"]');
    if (!emailInput) emailInput = await this.page.$('input[placeholder*="email" i]');
    if (!emailInput) emailInput = await this.page.$('input[autocomplete="email"]');
    if (!emailInput) emailInput = await this.page.$('input:first-of-type');

    if (!emailInput) {
      console.log('  ERROR: Could not find email input. Taking screenshot...');
      await this.page.screenshot({ path: 'debug-login.png' });
      throw new Error('Could not find email input field');
    }

    console.log('  Filling email...');
    await emailInput.click();
    await emailInput.fill(email);
    await this.page.waitForTimeout(500);

    // Fill password
    console.log('  Looking for password field...');
    let passwordInput = await this.page.$('input[type="password"]');
    if (!passwordInput) passwordInput = await this.page.$('input[name="password"]');

    if (!passwordInput) {
      console.log('  ERROR: Could not find password input. Taking screenshot...');
      await this.page.screenshot({ path: 'debug-login.png' });
      throw new Error('Could not find password input field');
    }

    console.log('  Filling password...');
    await passwordInput.click();
    await passwordInput.fill(password);
    await this.page.waitForTimeout(500);

    // Click login button
    console.log('  Looking for login button...');
    let loginButton = await this.page.$('button[type="submit"]');
    if (!loginButton) loginButton = await this.page.$('button:has-text("Log in")');
    if (!loginButton) loginButton = await this.page.$('button:has-text("Sign in")');
    if (!loginButton) loginButton = await this.page.$('button:has-text("Login")');
    if (!loginButton) loginButton = await this.page.$('input[type="submit"]');
    if (!loginButton) loginButton = await this.page.$('button');

    if (!loginButton) {
      console.log('  ERROR: Could not find login button. Taking screenshot...');
      await this.page.screenshot({ path: 'debug-login.png' });
      throw new Error('Could not find login button');
    }

    console.log('  Clicking login button...');
    await loginButton.click();

    // Wait for navigation to complete
    console.log('  Waiting for login to complete...');
    await this.page.waitForURL('**/am/**', { timeout: CONFIG.timeout });
    console.log('Login successful!');
  }

  async navigateToGoals() {
    console.log('Navigating to Goals...');
    await this.page.waitForTimeout(2000); // Let dashboard load

    // Click Sponsored Products (Goals is the default page after clicking)
    console.log('  Looking for Sponsored Products...');
    try {
      await this.page.click('text="Sponsored Products"', { timeout: 10000 });
    } catch {
      const spLink = await this.page.$('a:has-text("Sponsored Products"), [href*="sp"], button:has-text("Sponsored Products")');
      if (spLink) {
        await spLink.click();
      } else {
        console.log('  Taking screenshot for debugging...');
        await this.page.screenshot({ path: 'debug-nav.png' });
        throw new Error('Could not find Sponsored Products link');
      }
    }
    console.log('  Clicked Sponsored Products - Goals page should load by default');
    await this.page.waitForTimeout(3000); // Just wait instead of networkidle
    console.log('On Goals page');
  }

  async createGoal(goalData) {
    const {
      'Goal Name': goalName,
      'Campaign Type': campaignType,
      'ASIN': asin,
      'Match Type': matchType,
      'Daily Budget': dailyBudget,
      'Target ACOS': targetAcos,
      'Keywords': keywords,
      'PAT Targets': patTargets,
      'Negative Keywords (Exact)': negativeExact,
      'Negative Keywords (Phrase)': negativePhrase,
      'Negative ASINs': negativeAsins,
    } = goalData;

    const isPAT = campaignType.includes('PAT') || patTargets;

    console.log(`\nCreating goal: ${goalName}`);
    console.log(`  Type: ${isPAT ? 'PAT' : 'Keyword'}, Match: ${matchType}, Budget: $${dailyBudget}, ACOS: ${targetAcos}%`);

    // Click New Goal button
    console.log('  Looking for New Goal button...');
    let newGoalBtn = await this.page.$('button:has-text("New Goal")');
    if (!newGoalBtn) newGoalBtn = await this.page.$('[data-testid="new-goal-button"]');
    if (!newGoalBtn) newGoalBtn = await this.page.$('a:has-text("New Goal")');
    if (!newGoalBtn) newGoalBtn = await this.page.$('text="New Goal"');

    if (!newGoalBtn) {
      console.log('  ERROR: Could not find New Goal button. Taking screenshot...');
      await this.page.screenshot({ path: 'debug-newgoal.png' });
      throw new Error('Could not find New Goal button');
    }

    console.log('  Clicking New Goal...');
    await newGoalBtn.click();
    await this.page.waitForTimeout(3000); // Wait for new goal page to load

    // FIRST: Select Custom (under Single Campaign) - must be done before entering goal name
    console.log('  Selecting Custom goal format...');
    await this.page.waitForSelector('input', { timeout: 10000 });
    await this.page.click('text="Custom"').catch(() => {});
    await this.page.waitForTimeout(1500);

    // THEN: Find and fill goal title (must find AFTER clicking Custom as DOM changes)
    console.log('  Looking for goal title input...');
    let titleInput = await this.page.$('input[type="text"]');
    if (!titleInput) {
      titleInput = await this.page.$('text="Goal Name" >> xpath=following::input[1]');
    }
    if (!titleInput) {
      const allInputs = await this.page.$$('input[type="text"]');
      console.log(`  Found ${allInputs.length} text inputs`);
      if (allInputs.length > 0) {
        titleInput = allInputs[0];
      }
    }

    if (!titleInput) {
      console.log('  ERROR: Could not find title input. Taking screenshot...');
      await this.page.screenshot({ path: 'debug-title.png' });
      throw new Error('Could not find goal title input');
    }

    console.log('  Filling goal title...');
    await titleInput.click();
    await this.page.waitForTimeout(300);
    await titleInput.fill(goalName);
    await this.page.waitForTimeout(500);

    // Search for ASIN in product search
    console.log(`  Searching for ASIN: ${asin}...`);
    const productSearch = await this.page.$('input[placeholder*="Search"]');
    if (productSearch) {
      await productSearch.click();
      await productSearch.fill(asin);
      await this.page.waitForTimeout(3000); // Wait for search results to load

      // Click the blue "Select" link
      console.log('  Looking for Select link...');

      // The Select link appears after the product info - find it and click
      // First, make sure we're not scrolling around
      await this.page.mouse.move(0, 0);
      await this.page.waitForTimeout(500);

      // Use JavaScript to find and click the Select element
      const clicked = await this.page.evaluate(() => {
        // Find all elements that contain exactly "Select" as text
        const walker = document.createTreeWalker(
          document.body,
          NodeFilter.SHOW_TEXT,
          null,
          false
        );

        let node;
        while (node = walker.nextNode()) {
          if (node.textContent.trim() === 'Select') {
            const parent = node.parentElement;
            if (parent && parent.offsetParent !== null) {
              // Scroll into view first
              parent.scrollIntoView({ block: 'center' });
              // Click it
              parent.click();
              return true;
            }
          }
        }
        return false;
      });

      if (clicked) {
        console.log('  Clicked Select via JavaScript');
      } else {
        // Fallback: try Playwright click
        console.log('  Trying Playwright click...');
        try {
          await this.page.click('text=Select', { timeout: 5000 });
        } catch (e) {
          console.log('  WARNING: Could not click Select');
          await this.page.screenshot({ path: 'debug-select.png' });
        }
      }

      await this.page.waitForTimeout(1500);
    }

    // Select targeting type (Keyword Targeting or Product Attributed Targeting)
    console.log(`  Selecting targeting type: ${isPAT ? 'PAT' : 'Keyword'}...`);
    if (isPAT) {
      await this.page.click('text="Product Attributed Targeting"').catch(() => {});
    } else {
      await this.page.click('text="Keyword Targeting"').catch(() => {});
    }
    await this.page.waitForTimeout(500);

    // Set Target ACOS - the input is after the "%" symbol in the Target ACoS section
    console.log(`  Setting Target ACOS: ${targetAcos}%...`);
    // Find the input in the Target ACoS section (it's the second input after "Target ACoS" text)
    const acosSection = await this.page.$('text="Target ACoS" >> xpath=ancestor::div[1]');
    if (acosSection) {
      const acosInput = await acosSection.$('input:last-of-type');
      if (acosInput) {
        await acosInput.click();
        await acosInput.fill(targetAcos.toString());
      }
    } else {
      // Fallback: find input with % placeholder nearby
      await this.page.fill('text="Target ACoS" >> xpath=following::input[2]', targetAcos.toString()).catch(() => {});
    }

    // Set Daily Budget - the input is after the "$" symbol
    console.log(`  Setting Daily Budget: $${dailyBudget}...`);
    const budgetSection = await this.page.$('text="Daily Budget" >> xpath=ancestor::div[1]');
    if (budgetSection) {
      const budgetInput = await budgetSection.$('input:last-of-type');
      if (budgetInput) {
        await budgetInput.click();
        await budgetInput.fill(dailyBudget.toString());
      }
    } else {
      // Fallback
      await this.page.fill('text="Daily Budget" >> xpath=following::input[2]', dailyBudget.toString()).catch(() => {});
    }

    await this.page.keyboard.press('PageDown');
    await this.page.waitForTimeout(500);

    if (isPAT) {
      // PAT: Click "Add Products" and paste targets
      console.log('  Adding PAT targets...');
      if (patTargets) {
        await this.page.click('button:has-text("Add Products")').catch(() => {});
        await this.page.waitForTimeout(1000);

        const textarea = await this.page.$('textarea');
        if (textarea) {
          await textarea.fill(patTargets);
          await this.page.click('button:has-text("Add")').catch(() => {});
        }
        await this.page.waitForTimeout(500);
      }
    } else {
      // Keywords: Configure match types in "Select Match Types" section
      console.log(`  Configuring match type: ${matchType}...`);

      // Click to uncheck/check the appropriate match types
      // Based on screenshot: checkboxes are labeled "Exact Match", "Phrase Match", "Broad Match"

      if (matchType === 'EXACT') {
        // Uncheck Phrase and Broad, ensure Exact is checked
        await this.page.click('text="Phrase Match"').catch(() => {});
        await this.page.waitForTimeout(200);
        await this.page.click('text="Broad Match"').catch(() => {});
        await this.page.waitForTimeout(200);
      } else if (matchType === 'PHRASE') {
        // Uncheck Exact and Broad, ensure Phrase is checked
        await this.page.click('text="Exact Match"').catch(() => {});
        await this.page.waitForTimeout(200);
        await this.page.click('text="Broad Match"').catch(() => {});
        await this.page.waitForTimeout(200);
      } else if (matchType === 'BROAD') {
        // Uncheck Exact and Phrase, ensure Broad is checked
        await this.page.click('text="Exact Match"').catch(() => {});
        await this.page.waitForTimeout(200);
        await this.page.click('text="Phrase Match"').catch(() => {});
        await this.page.waitForTimeout(200);
      }

      console.log(`  Match type set to ${matchType} only`);
      await this.page.waitForTimeout(500);

      // Add keywords if provided - convert commas to newlines
      if (keywords) {
        console.log('  Adding keywords...');
        // Convert comma-separated to newline-separated
        const keywordsNewline = keywords.split(',').map(k => k.trim()).join('\n');

        // Find the keyword textarea
        const keywordTextarea = await this.page.$('textarea');
        if (keywordTextarea) {
          await keywordTextarea.click();
          await keywordTextarea.fill(keywordsNewline);
          await this.page.waitForTimeout(500);

          // Click "Add Keyword Targets" button
          console.log('  Clicking Add Keyword Targets...');
          await this.page.click('text="Add Keyword Targets"').catch(async () => {
            await this.page.click('button:has-text("Add Keyword")').catch(() => {});
          });
          await this.page.waitForTimeout(1000);
        }
      }
    }

    // Skip harvesting and negatives for now - go straight to Launch Goal
    console.log('  Skipping Harvesting and Negatives (to be configured manually)...');

    // Click Launch Goal button (top right)
    console.log('  Launching goal...');
    await this.page.click('button:has-text("Launch Goal")').catch(async () => {
      await this.page.click('text="Launch Goal"').catch(() => {});
    });
    await this.page.waitForTimeout(3000);

    console.log(`  Goal created successfully!`);
  }
}

// Main execution
async function main() {
  const args = parseArgs();

  console.log('===========================================');
  console.log('  Perpetua Goal Uploader');
  console.log('===========================================\n');

  // Load goals from CSV
  const goals = loadGoals();
  console.log(`Loaded ${goals.length} goals from CSV\n`);

  // Check for existing progress
  const progress = loadProgress();
  if (progress && args.startRow === 0) {
    const resume = await prompt(`Found previous progress at row ${progress.lastRowIndex} (${progress.lastGoalName}). Resume? (y/n): `);
    if (resume.toLowerCase() === 'y') {
      args.startRow = progress.lastRowIndex + 1;
    }
  }

  if (args.startRow > 0) {
    console.log(`Starting from row ${args.startRow}\n`);
  }

  // Dry run - just show what would be created
  if (args.dryRun) {
    console.log('[DRY RUN MODE - No actions will be taken]\n');
    console.log('Sample of goals that would be created:\n');
    for (let i = args.startRow; i < Math.min(args.startRow + 10, goals.length); i++) {
      const g = goals[i];
      const type = g['Campaign Type'].includes('PAT') ? 'PAT' : 'Keyword';
      console.log(`  ${i + 1}. ${g['Goal Name']}`);
      console.log(`     Type: ${type}, Match: ${g['Match Type']}, Budget: $${g['Daily Budget']}, ACOS: ${g['Target ACOS']}%`);
    }
    if (goals.length - args.startRow > 10) {
      console.log(`\n  ... and ${goals.length - args.startRow - 10} more goals`);
    }
    console.log(`\nTotal goals to create: ${goals.length - args.startRow}`);
    return;
  }

  // Get credentials (use preset or prompt)
  const email = CONFIG.email || await prompt('Perpetua Email: ');
  const password = CONFIG.password || await promptPassword('Perpetua Password: ');
  console.log(`Using account: ${email}`);

  // Launch browser
  console.log('\nLaunching browser...');
  const browser = await chromium.launch({
    headless: false,
    slowMo: CONFIG.slowMo,
  });

  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
  });

  const page = await context.newPage();
  page.setDefaultTimeout(CONFIG.timeout);

  const uploader = new PerpetuaUploader(page);

  try {
    // Login
    await uploader.login(email, password);

    // Navigate to Goals
    await uploader.navigateToGoals();

    // Calculate end row based on limit
    const endRow = args.limit > 0 ? Math.min(args.startRow + args.limit, goals.length) : goals.length;
    console.log(`\nProcessing goals ${args.startRow + 1} to ${endRow} (${endRow - args.startRow} total)\n`);

    // Process each goal
    for (let i = args.startRow; i < endRow; i++) {
      const goal = goals[i];
      console.log(`\n[${i + 1}/${goals.length}] Processing...`);

      try {
        await uploader.createGoal(goal);
        saveProgress(i, goal['Goal Name'], 'success');
      } catch (error) {
        console.error(`  ERROR: ${error.message}`);
        saveProgress(i, goal['Goal Name'], 'error');

        const cont = await prompt('Continue to next goal? (y/n): ');
        if (cont.toLowerCase() !== 'y') {
          break;
        }

        // Navigate back to goals page
        await uploader.navigateToGoals();
      }

      // Small delay between goals
      await page.waitForTimeout(500);
    }

    console.log('\n===========================================');
    console.log('  Upload Complete!');
    console.log('===========================================');

  } catch (error) {
    console.error('Fatal error:', error);
  } finally {
    // Keep browser open for review
    console.log('\nBrowser will stay open. Press Ctrl+C to close.');
    await new Promise(() => {}); // Keep alive
  }
}

main().catch(console.error);
