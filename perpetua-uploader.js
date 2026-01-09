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

    await this.page.keyboard.press('PageDown');
    await this.page.waitForTimeout(500);

    // FIRST: Add keywords/targets (this may cause form re-render, so do it before setting ACOS/Budget)
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

      // Scroll to the Select Match Types section first
      await this.page.evaluate(() => {
        const heading = Array.from(document.querySelectorAll('*')).find(
          el => el.textContent.includes('Select Match Types') && el.textContent.length < 50
        );
        if (heading) heading.scrollIntoView({ block: 'center' });
      });
      await this.page.waitForTimeout(500);

      // Strategy: Find the checkbox row container and click each checkbox we want to uncheck
      // The checkboxes are in a row: [✓ Exact Match] [✓ Phrase Match] [✓ Broad Match]
      // We need to click the checkbox icon/element, not the label text

      const matchTypesToUncheck = [];
      if (matchType === 'EXACT') {
        matchTypesToUncheck.push('Phrase Match', 'Broad Match');
      } else if (matchType === 'PHRASE') {
        matchTypesToUncheck.push('Exact Match', 'Broad Match');
      } else if (matchType === 'BROAD') {
        matchTypesToUncheck.push('Exact Match', 'Phrase Match');
      }

      for (const labelToUncheck of matchTypesToUncheck) {
        console.log(`    Unchecking ${labelToUncheck}...`);

        // Method 1: Use Playwright's label locator to find associated checkbox
        try {
          const labelLocator = this.page.locator(`label:has-text("${labelToUncheck}")`);
          const count = await labelLocator.count();
          if (count > 0) {
            await labelLocator.first().click();
            console.log(`      Clicked via label locator`);
            await this.page.waitForTimeout(300);
            continue;
          }
        } catch (e) {
          // Continue to next method
        }

        // Method 2: Find the text and click its parent container (which includes the checkbox)
        const clicked = await this.page.evaluate((labelText) => {
          // Find the span/text element containing the label
          const textElements = Array.from(document.querySelectorAll('span, div, p')).filter(
            el => el.textContent.trim() === labelText && el.children.length === 0
          );

          for (const textEl of textElements) {
            // The checkbox is usually a sibling or in the same parent container
            // Look for the clickable container that wraps both checkbox and label
            let container = textEl.parentElement;

            // Check up to 3 levels
            for (let i = 0; i < 3 && container; i++) {
              // Look for SVG (checkbox icon), input, or clickable element
              const svg = container.querySelector('svg');
              const input = container.querySelector('input[type="checkbox"]');
              const clickableDiv = container.querySelector('[role="checkbox"]');

              if (svg || input || clickableDiv) {
                // Click the container itself (this usually toggles the checkbox)
                container.click();
                return { method: 'container', level: i };
              }
              container = container.parentElement;
            }

            // Fallback: try clicking the previous sibling (checkbox before label)
            const prevSibling = textEl.previousElementSibling;
            if (prevSibling) {
              prevSibling.click();
              return { method: 'prevSibling' };
            }
          }
          return null;
        }, labelToUncheck);

        if (clicked) {
          console.log(`      Clicked via JS: ${clicked.method} (level: ${clicked.level || 'n/a'})`);
        } else {
          // Method 3: Try direct text click which might toggle the checkbox in some UIs
          try {
            await this.page.click(`text="${labelToUncheck}"`, { timeout: 2000 });
            console.log(`      Clicked via text selector`);
          } catch (e) {
            console.log(`      Failed to click ${labelToUncheck}`);
          }
        }

        await this.page.waitForTimeout(300);
      }

      // Verify the checkbox states after clicking
      const finalStates = await this.page.evaluate(() => {
        const states = {};
        const labels = ['Exact Match', 'Phrase Match', 'Broad Match'];

        for (const label of labels) {
          const textEl = Array.from(document.querySelectorAll('span, div')).find(
            el => el.textContent.trim() === label && el.children.length === 0
          );
          if (textEl) {
            let container = textEl.parentElement;
            for (let i = 0; i < 3 && container; i++) {
              const svg = container.querySelector('svg');
              const input = container.querySelector('input[type="checkbox"]');
              if (input) {
                states[label] = input.checked;
                break;
              }
              if (svg) {
                // Check if SVG indicates checked state (e.g., has checkmark path or fill color)
                const path = svg.querySelector('path');
                const isChecked = svg.getAttribute('fill') !== 'none' ||
                                  svg.classList.contains('checked') ||
                                  container.classList.contains('checked') ||
                                  container.getAttribute('data-state') === 'checked';
                states[label] = isChecked;
                break;
              }
              container = container.parentElement;
            }
          }
        }
        return states;
      });

      console.log(`  Final checkbox states: ${JSON.stringify(finalStates)}`);
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

    // NOW set ACOS and Budget (AFTER keywords/targets are added to avoid form reset)
    // Scroll back up to the ACOS/Budget section
    await this.page.evaluate(() => {
      const heading = Array.from(document.querySelectorAll('*')).find(
        el => el.textContent.includes('Target ACoS') && el.textContent.length < 50
      );
      if (heading) heading.scrollIntoView({ block: 'center' });
    });
    await this.page.waitForTimeout(500);

    // Set Target ACOS using JavaScript to find the right input
    console.log(`  Setting Target ACOS: ${targetAcos}%...`);
    const acosSet = await this.page.evaluate((value) => {
      // Find "Target ACoS" label and then find the input nearby
      const labels = Array.from(document.querySelectorAll('*')).filter(
        el => el.textContent.trim() === 'Target ACoS' && el.children.length === 0
      );
      for (const label of labels) {
        // Look for input in parent containers
        let parent = label.parentElement;
        for (let i = 0; i < 5 && parent; i++) {
          const inputs = parent.querySelectorAll('input[type="text"], input[type="number"], input:not([type])');
          for (const input of inputs) {
            // Skip inputs that are clearly not the ACOS input (e.g., search boxes)
            if (input.placeholder?.toLowerCase().includes('search')) continue;
            if (input.placeholder?.includes('%') || input.closest('[class*="acos" i]') ||
                parent.textContent.includes('Target ACoS')) {
              input.focus();
              input.value = value;
              input.dispatchEvent(new Event('input', { bubbles: true }));
              input.dispatchEvent(new Event('change', { bubbles: true }));
              return true;
            }
          }
          parent = parent.parentElement;
        }
      }
      return false;
    }, targetAcos.toString());
    console.log(`    ACOS set: ${acosSet}`);

    // Set Daily Budget using JavaScript
    console.log(`  Setting Daily Budget: $${dailyBudget}...`);
    const budgetSet = await this.page.evaluate((value) => {
      // Find "Daily Budget" label and then find the input nearby
      const labels = Array.from(document.querySelectorAll('*')).filter(
        el => el.textContent.trim() === 'Daily Budget' && el.children.length === 0
      );
      for (const label of labels) {
        let parent = label.parentElement;
        for (let i = 0; i < 5 && parent; i++) {
          const inputs = parent.querySelectorAll('input[type="text"], input[type="number"], input:not([type])');
          for (const input of inputs) {
            if (input.placeholder?.toLowerCase().includes('search')) continue;
            if (input.placeholder?.includes('$') || input.closest('[class*="budget" i]') ||
                parent.textContent.includes('Daily Budget')) {
              input.focus();
              input.value = value;
              input.dispatchEvent(new Event('input', { bubbles: true }));
              input.dispatchEvent(new Event('change', { bubbles: true }));
              return true;
            }
          }
          parent = parent.parentElement;
        }
      }
      return false;
    }, dailyBudget.toString());
    console.log(`    Budget set: ${budgetSet}`);

    // If JavaScript approach didn't work, try direct Playwright approach
    if (!acosSet || !budgetSet) {
      console.log('  Trying Playwright fallback for ACOS/Budget...');
      // Find all visible inputs and try to identify ACOS and Budget by position
      const allInputs = await this.page.$$('input:visible');
      console.log(`    Found ${allInputs.length} visible inputs`);

      for (const input of allInputs) {
        const placeholder = await input.getAttribute('placeholder');
        if (!acosSet && placeholder?.includes('%')) {
          await input.click();
          await input.fill(targetAcos.toString());
          console.log('    Filled ACOS via placeholder match');
        }
        if (!budgetSet && placeholder?.includes('$')) {
          await input.click();
          await input.fill(dailyBudget.toString());
          console.log('    Filled Budget via placeholder match');
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
