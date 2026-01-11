/**
 * Perpetua Simplified Goal Uploader
 *
 * Creates ONE goal per ASIN with all unbranded keywords (EXACT, PHRASE, BROAD).
 * All match types combined in a single campaign.
 *
 * Usage: node perpetua-simplified-uploader.js [--dry-run] [--limit=N]
 */

const fs = require('fs');
const path = require('path');

// Configuration
const CONFIG = {
  // API endpoints
  baseUrl: 'https://crispy.perpetua.io/engine/v3',
  companyId: '58088',

  // Auth token (from browser session - refresh from DevTools when expired)
  authToken: '520d5eceb627d3069a80c63847bc744ff4d4518c',

  // File paths
  keywordsPath: path.join(__dirname, 'unbranded_keywords.json'),
  progressFile: path.join(__dirname, 'simplified_upload_progress.json'),
  productCachePath: path.join(__dirname, 'product_cache.json'),

  // Goal settings
  dailyBudget: 50,  // $50 per goal
  targetAcos: 60,   // 60% ACOS

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

// Load keywords data
function loadKeywords() {
  const content = fs.readFileSync(CONFIG.keywordsPath, 'utf-8');
  return JSON.parse(content);
}

// Save progress
function saveProgress(asin, status, error = null) {
  const progress = loadProgress() || { completed: [], failed: [] };

  if (status === 'success') {
    if (!progress.completed.includes(asin)) {
      progress.completed.push(asin);
    }
  } else if (status === 'error') {
    progress.failed.push({ asin, error, timestamp: new Date().toISOString() });
  }

  fs.writeFileSync(CONFIG.progressFile, JSON.stringify(progress, null, 2));
}

// Load progress
function loadProgress() {
  if (fs.existsSync(CONFIG.progressFile)) {
    return JSON.parse(fs.readFileSync(CONFIG.progressFile, 'utf-8'));
  }
  return { completed: [], failed: [] };
}

// Parse command line arguments
function parseArgs() {
  const args = {
    dryRun: false,
    limit: 0,
  };

  for (const arg of process.argv.slice(2)) {
    if (arg.startsWith('--limit=')) {
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

// GraphQL query for product search
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

    if (result.data?.childProductListPerformance?.edges?.length > 0) {
      const match = result.data.childProductListPerformance.edges.find(
        edge => edge.node.asin === asin
      );

      if (match) {
        const productId = match.node.productId;
        productCache[asin] = productId;
        saveProductCache();
        console.log(`    Found product_id: ${productId}`);
        return productId;
      }
    }
  } catch (error) {
    console.log(`    Warning: Could not look up product ID: ${error.message}`);
  }

  return null;
}

// Create a simplified goal via API
async function createGoal(asin, sku, keywords) {
  // Get product ID from ASIN
  const productId = await getProductId(asin);
  if (!productId) {
    return { skipped: true, reason: `Product not found for ASIN: ${asin}` };
  }

  // Build search_space_keywords with all match types
  const searchSpaceKeywords = [];

  // Add exact keywords
  for (const kw of keywords.exact || []) {
    searchSpaceKeywords.push({ keyword_text: kw, match_type: 'EXACT' });
  }

  // Add phrase keywords
  for (const kw of keywords.phrase || []) {
    searchSpaceKeywords.push({ keyword_text: kw, match_type: 'PHRASE' });
  }

  // Add broad keywords
  for (const kw of keywords.broad || []) {
    searchSpaceKeywords.push({ keyword_text: kw, match_type: 'BROAD' });
  }

  if (searchSpaceKeywords.length === 0) {
    return { skipped: true, reason: 'No keywords found' };
  }

  // Goal name format: SKU -JN[SP_NON-BRANDED]
  const goalName = `${sku} -JN[SP_NON-BRANDED]`.substring(0, 60);

  // Build the API payload
  const payload = {
    title: goalName,
    enabled: true,
    campaign_bidding_strategy: 'BIDDING_STRATEGY_LEGACY_FOR_SALES',
    max_budget: CONFIG.dailyBudget,
    target_acos: CONFIG.targetAcos / 100, // Convert percentage to decimal
    products: [{ product_id: productId }],
    search_space_keywords: searchSpaceKeywords,
    negative_keyword_overrides: [],
    optimization_objective_state: {
      optimization_objective: 'ACOS_COMPLIANCE',
    },
    placement_optimization: {},
    keyword_harvesting: {
      harvesting_mode: 'AUTOMATICALLY_ADD',
      user_enabled_match_types: ['EXACT', 'PHRASE', 'BROAD'],
      harvesting_criteria: {
        type: 'keyword_targeting_simple',
        conversion_threshold: 1,
        phrases: [],
      },
    },
  };

  console.log(`  Creating goal: ${goalName}`);
  console.log(`    Budget: $${CONFIG.dailyBudget}, ACOS: ${CONFIG.targetAcos}%`);
  console.log(`    Keywords: ${keywords.exact?.length || 0} exact, ${keywords.phrase?.length || 0} phrase, ${keywords.broad?.length || 0} broad`);

  const result = await apiRequest('/uni_goals/MULTI_AD_GROUP_CUSTOM_GOAL/', 'POST', payload);

  return result;
}

// Main execution
async function main() {
  const args = parseArgs();

  console.log('===========================================');
  console.log('  Perpetua Simplified Goal Uploader');
  console.log('  (1 campaign per ASIN, all match types)');
  console.log('===========================================\n');

  // Load product cache
  loadProductCache();

  // Load keywords from JSON
  const allKeywords = loadKeywords();
  const asins = Object.keys(allKeywords);
  console.log(`Loaded keywords for ${asins.length} ASINs\n`);

  // Check for existing progress
  const progress = loadProgress();
  const completedAsins = new Set(progress.completed || []);
  const remainingAsins = asins.filter(asin => !completedAsins.has(asin));

  console.log(`Already completed: ${completedAsins.size}`);
  console.log(`Remaining: ${remainingAsins.length}\n`);

  // Dry run mode
  if (args.dryRun) {
    console.log('[DRY RUN MODE - No API calls will be made]\n');
    console.log('Sample goals that would be created:\n');

    const sampleCount = Math.min(5, remainingAsins.length);
    for (let i = 0; i < sampleCount; i++) {
      const asin = remainingAsins[i];
      const data = allKeywords[asin];
      console.log(`  ${i + 1}. ${data.sku} - ${asin}`);
      console.log(`     Keywords: ${data.exact?.length || 0} exact, ${data.phrase?.length || 0} phrase, ${data.broad?.length || 0} broad`);
      console.log('');
    }

    console.log(`Total goals to create: ${remainingAsins.length}`);
    return;
  }

  // Calculate end index
  const endIndex = args.limit > 0 ? Math.min(args.limit, remainingAsins.length) : remainingAsins.length;
  console.log(`Processing ${endIndex} ASINs\n`);

  let successCount = 0;
  let errorCount = 0;
  let skippedCount = 0;

  // Process each ASIN
  for (let i = 0; i < endIndex; i++) {
    const asin = remainingAsins[i];
    const data = allKeywords[asin];

    console.log(`\n[${i + 1}/${endIndex}] Processing ${asin} (${data.sku})...`);

    try {
      const result = await createGoal(asin, data.sku, data);

      if (result?.skipped) {
        console.log(`  SKIPPED: ${result.reason}`);
        skippedCount++;
        continue;
      }

      saveProgress(asin, 'success');
      successCount++;
      console.log(`  Success!`);
    } catch (error) {
      console.error(`  ERROR: ${error.message}`);
      saveProgress(asin, 'error', error.message);
      errorCount++;

      if (error.message.includes('401') || error.message.includes('403')) {
        console.log('\n  Auth token may have expired. Get a fresh token from DevTools.');
        break;
      }

      if (error.message.includes('cannot create any more')) {
        console.log('\n  Account has reached goal limit. Contact Perpetua to increase limit.');
        break;
      }
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
