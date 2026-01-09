/**
 * Perpetua Goal Uploader - Direct API Version
 *
 * Creates goals via Perpetua's API instead of browser automation.
 * Much faster and more reliable than browser automation.
 *
 * Usage: node perpetua-api-uploader.js [--start-row=N] [--limit=N] [--dry-run]
 */

const fs = require('fs');
const path = require('path');
const csv = require('csv-parse/sync');

// Configuration
const CONFIG = {
  // API endpoints
  baseUrl: 'https://crispy.perpetua.io/engine/v3',
  companyId: '58088',

  // Auth token (from browser session - will need to refresh periodically)
  authToken: '520d5eceb627d3069a80c63847bc744ff4d4518c',

  // File paths
  csvPath: path.join(__dirname, 'agent_task_list.csv'),
  progressFile: path.join(__dirname, 'api_upload_progress.json'),
  productCachePath: path.join(__dirname, 'product_cache.json'),

  // Rate limiting
  delayBetweenRequests: 500, // ms
};

// Product ID cache (ASIN -> product_id mapping)
let productCache = {};

// Load product cache from file
function loadProductCache() {
  if (fs.existsSync(CONFIG.productCachePath)) {
    productCache = JSON.parse(fs.readFileSync(CONFIG.productCachePath, 'utf-8'));
    console.log(`Loaded ${Object.keys(productCache).length} cached product IDs`);
  }
}

// Save product cache to file
function saveProductCache() {
  fs.writeFileSync(CONFIG.productCachePath, JSON.stringify(productCache, null, 2));
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
function saveProgress(rowIndex, goalName, status, error = null) {
  const progress = {
    lastRowIndex: rowIndex,
    lastGoalName: goalName,
    status: status,
    error: error,
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
    limit: 0,
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

// Sleep helper
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// REST API request helper
async function apiRequest(endpoint, method = 'GET', body = null) {
  const url = `${CONFIG.baseUrl}/geo_companies/${CONFIG.companyId}${endpoint}`;

  const options = {
    method,
    headers: {
      'Authorization': `Token ${CONFIG.authToken}`,
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      'Origin': 'https://app.perpetua.io',
      'Referer': 'https://app.perpetua.io/',
    },
  };

  if (body) {
    options.body = JSON.stringify(body);
  }

  const response = await fetch(url, options);

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`API error ${response.status}: ${errorText}`);
  }

  return response.json();
}

// GraphQL API request helper (for product search)
async function graphqlRequest(query, variables) {
  const url = 'https://apollo.perpetua.io/';

  const options = {
    method: 'POST',
    headers: {
      'Authorization': `Token ${CONFIG.authToken}`,
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      'Origin': 'https://app.perpetua.io',
      'Referer': 'https://app.perpetua.io/',
    },
    body: JSON.stringify({
      operationName: 'SPChildProductPerfList',
      query,
      variables,
    }),
  };

  const response = await fetch(url, options);

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`GraphQL error ${response.status}: ${errorText}`);
  }

  return response.json();
}

// GraphQL query for product search (simplified)
const PRODUCT_SEARCH_QUERY = `query SPChildProductPerfList($geoCompanyId: Int!, $startDate: Date, $endDate: Date, $offset: Int, $limit: Int, $search: String) {
  childProductListPerformance(
    geoCompanyId: $geoCompanyId
    startDate: $startDate
    endDate: $endDate
    offset: $offset
    limit: $limit
    search: $search
  ) {
    totalCount
    edges {
      node {
        productId
        asin
        title
      }
    }
  }
}`;

// Search for product by ASIN to get product_id
async function getProductId(asin) {
  // Check cache first
  if (productCache[asin]) {
    return productCache[asin];
  }

  console.log(`    Looking up product ID for ASIN: ${asin}...`);

  try {
    // Get date range for the query (last 7 days)
    const endDate = new Date().toISOString().split('T')[0];
    const startDate = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];

    const variables = {
      geoCompanyId: parseInt(CONFIG.companyId, 10),
      startDate,
      endDate,
      offset: 0,
      limit: 25,
      search: asin,
    };

    const result = await graphqlRequest(PRODUCT_SEARCH_QUERY, variables);

    // Debug: show what we got
    const totalCount = result.data?.childProductListPerformance?.totalCount || 0;
    const edgeCount = result.data?.childProductListPerformance?.edges?.length || 0;
    console.log(`    Search returned ${totalCount} total, ${edgeCount} edges`);

    if (result.data?.childProductListPerformance?.edges?.length > 0) {
      // Find the exact ASIN match
      const match = result.data.childProductListPerformance.edges.find(
        edge => edge.node.asin === asin
      );

      if (match) {
        const productId = match.node.productId;
        productCache[asin] = productId;
        saveProductCache();
        console.log(`    Found product_id: ${productId} (${match.node.title?.substring(0, 40)}...)`);
        return productId;
      }

      // If no exact match, use the first result
      const firstResult = result.data.childProductListPerformance.edges[0].node;
      const productId = firstResult.productId;
      productCache[asin] = productId;
      saveProductCache();
      console.log(`    Found product_id: ${productId} (${firstResult.title?.substring(0, 40)}...)`);
      return productId;
    }
  } catch (error) {
    console.log(`    Warning: Could not look up product ID: ${error.message}`);
  }

  return null;
}

// Create a goal via API
async function createGoal(goalData) {
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

  // Get product ID from ASIN
  const productId = await getProductId(asin);
  if (!productId) {
    return { skipped: true, reason: `Product not found for ASIN: ${asin}` };
  }

  // Parse keywords into the API format
  const searchSpaceKeywords = [];
  if (keywords) {
    const keywordList = keywords.split(',').map(k => k.trim()).filter(k => k);
    for (const kw of keywordList) {
      searchSpaceKeywords.push({
        keyword_text: kw,
        match_type: matchType || 'EXACT',
      });
    }
  }

  // Parse negative keywords
  const negativeKeywordOverrides = [];

  // Add exact match negatives
  if (negativeExact) {
    const negExactList = negativeExact.split(',').map(k => k.trim()).filter(k => k);
    for (const kw of negExactList) {
      negativeKeywordOverrides.push({
        keyword_text: kw,
        match_type: 'EXACT',
      });
    }
  }

  // Add phrase match negatives
  if (negativePhrase) {
    const negPhraseList = negativePhrase.split(',').map(k => k.trim()).filter(k => k);
    for (const kw of negPhraseList) {
      negativeKeywordOverrides.push({
        keyword_text: kw,
        match_type: 'PHRASE',
      });
    }
  }

  // Parse negative ASINs (for PAT campaigns)
  const negativeAsinList = [];
  if (negativeAsins) {
    const asinList = negativeAsins.split(',').map(a => a.trim()).filter(a => a);
    for (const asinVal of asinList) {
      negativeAsinList.push(asinVal);
    }
  }

  // Build the API payload
  const payload = {
    title: goalName,
    enabled: true,
    campaign_bidding_strategy: 'BIDDING_STRATEGY_LEGACY_FOR_SALES',
    max_budget: parseInt(dailyBudget, 10) || 10,
    target_acos: (parseInt(targetAcos, 10) || 30) / 100, // Convert percentage to decimal
    products: [{ product_id: productId }],
    search_space_keywords: searchSpaceKeywords,
    negative_keyword_overrides: negativeKeywordOverrides,
    optimization_objective_state: {
      optimization_objective: 'ACOS_COMPLIANCE',
    },
    placement_optimization: {},
  };

  // Add keyword harvesting settings for keyword campaigns (not PAT)
  // BRANDED campaigns: DISABLED (protect from non-branded contamination)
  // COMPETITOR/MANUAL campaigns: AUTOMATICALLY_ADD (allow harvesting)
  const isPATCampaign = campaignType === 'SingleCampaign_PAT' || matchType === 'PAT';
  if (!isPATCampaign) {
    const isBrandedCampaign = goalName.includes('BRANDED');
    const harvestingMode = isBrandedCampaign ? 'MANUALLY_APPROVE' : 'AUTOMATICALLY_ADD';

    payload.keyword_harvesting = {
      harvesting_mode: harvestingMode,
      user_enabled_match_types: [matchType || 'EXACT'],
      harvesting_criteria: {
        type: 'keyword_targeting_simple',
        conversion_threshold: 1,
        phrases: [],
      },
    };

    console.log(`    Harvesting: ${harvestingMode} (${isBrandedCampaign ? 'branded' : 'non-branded'})`);
  }

  // Handle PAT campaigns - targets go in search_space_keywords with TARGETING_EXPRESSION match type
  const isPAT = campaignType === 'SingleCampaign_PAT' || matchType === 'PAT';
  if (isPAT && patTargets) {
    // Parse PAT targets (ASINs to target) - use lowercase ASINs
    const targetList = patTargets.split(',').map(t => t.trim().toLowerCase()).filter(t => t);
    payload.search_space_keywords = targetList.map(asinTarget => ({
      keyword_text: asinTarget,
      match_type: 'TARGETING_EXPRESSION',
    }));

    console.log(`    PAT Campaign: ${targetList.length} product targets`);
  }

  // Add negative ASINs as TARGETING_EXPRESSION in negative_keyword_overrides
  if (negativeAsinList.length > 0) {
    for (const negAsin of negativeAsinList) {
      negativeKeywordOverrides.push({
        keyword_text: negAsin.toLowerCase(),
        match_type: 'TARGETING_EXPRESSION',
      });
    }
    // Update the payload with the combined negatives
    payload.negative_keyword_overrides = negativeKeywordOverrides;
  }

  console.log(`  Creating goal: ${goalName}`);
  console.log(`    Budget: $${payload.max_budget}, ACOS: ${targetAcos}%, Keywords: ${payload.search_space_keywords.length}, Negatives: ${payload.negative_keyword_overrides.length}`);
  console.log(`    Raw keywords from CSV: "${keywords}"`);
  console.log(`    Raw negExact: "${negativeExact || ''}"`);
  console.log(`    Raw negPhrase: "${negativePhrase || ''}"`);

  const result = await apiRequest('/uni_goals/MULTI_AD_GROUP_CUSTOM_GOAL/', 'POST', payload);

  return result;
}

// Main execution
async function main() {
  const args = parseArgs();

  console.log('===========================================');
  console.log('  Perpetua API Goal Uploader');
  console.log('===========================================\n');

  // Load product cache
  loadProductCache();

  // Load goals from CSV
  const goals = loadGoals();
  console.log(`Loaded ${goals.length} goals from CSV\n`);

  // Check for existing progress
  const progress = loadProgress();
  if (progress && args.startRow === 0) {
    console.log(`Found previous progress at row ${progress.lastRowIndex} (${progress.lastGoalName})`);
    console.log(`Status: ${progress.status}`);
    if (progress.error) console.log(`Error: ${progress.error}`);
    console.log('');

    const readline = require('readline');
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
    const answer = await new Promise(resolve => rl.question('Resume from next row? (y/n): ', resolve));
    rl.close();

    if (answer.toLowerCase() === 'y') {
      args.startRow = progress.lastRowIndex + 1;
    }
  }

  if (args.startRow > 0) {
    console.log(`Starting from row ${args.startRow}\n`);
  }

  // Dry run mode
  if (args.dryRun) {
    console.log('[DRY RUN MODE - No API calls will be made]\n');
    console.log('Sample goals that would be created:\n');

    const endRow = args.limit > 0 ? Math.min(args.startRow + args.limit, goals.length) : Math.min(args.startRow + 5, goals.length);
    for (let i = args.startRow; i < endRow; i++) {
      const g = goals[i];
      console.log(`  ${i + 1}. ${g['Goal Name']}`);
      console.log(`     ASIN: ${g['ASIN']}, Budget: $${g['Daily Budget']}, ACOS: ${g['Target ACOS']}%`);
      console.log(`     Match Type: ${g['Match Type']}, Keywords: ${(g['Keywords'] || '').split(',').length}`);
      console.log('');
    }

    console.log(`Total goals to create: ${goals.length - args.startRow}`);
    return;
  }

  // Calculate end row
  const endRow = args.limit > 0 ? Math.min(args.startRow + args.limit, goals.length) : goals.length;
  console.log(`Processing goals ${args.startRow + 1} to ${endRow} (${endRow - args.startRow} total)\n`);

  let successCount = 0;
  let errorCount = 0;
  let skippedCount = 0;

  // Process each goal
  for (let i = args.startRow; i < endRow; i++) {
    const goal = goals[i];
    console.log(`\n[${i + 1}/${goals.length}] Processing...`);

    try {
      const result = await createGoal(goal);

      // Handle skipped products
      if (result?.skipped) {
        console.log(`  SKIPPED: ${result.reason}`);
        saveProgress(i, goal['Goal Name'], 'skipped', result.reason);
        skippedCount++;
        continue;
      }

      saveProgress(i, goal['Goal Name'], 'success');
      successCount++;
      console.log(`  Success!`);
    } catch (error) {
      console.error(`  ERROR: ${error.message}`);
      saveProgress(i, goal['Goal Name'], 'error', error.message);
      errorCount++;

      // Only ask for real errors, not skips
      if (error.message.includes('401') || error.message.includes('403')) {
        console.log('\n  Auth token may have expired. Get a fresh token from DevTools.');
        break;
      }
      // Continue automatically for other errors
    }

    // Rate limiting
    await sleep(CONFIG.delayBetweenRequests);
  }

  console.log('\n===========================================');
  console.log('  Upload Complete!');
  console.log(`  Success: ${successCount}, Skipped: ${skippedCount}, Errors: ${errorCount}`);
  console.log('===========================================');
}

main().catch(console.error);
