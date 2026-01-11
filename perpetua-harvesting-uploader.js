/**
 * Perpetua Harvesting-Only Goal Uploader
 *
 * Creates goals for ASINs without seed keywords, relying on keyword harvesting.
 * Same convention as simplified uploader: SKU -JN[SP_NON-BRANDED]
 */

const fs = require('fs');
const path = require('path');

// Configuration
const CONFIG = {
  baseUrl: 'https://crispy.perpetua.io/engine/v3',
  companyId: '58088',
  authToken: '520d5eceb627d3069a80c63847bc744ff4d4518c',
  keywordsPath: path.join(__dirname, 'harvesting_only_keywords.json'),
  progressFile: path.join(__dirname, 'harvesting_upload_progress.json'),
  productCachePath: path.join(__dirname, 'product_cache.json'),
  dailyBudget: 50,
  targetAcos: 60,
  delayBetweenRequests: 500,
};

let productCache = {};

function loadProductCache() {
  if (fs.existsSync(CONFIG.productCachePath)) {
    productCache = JSON.parse(fs.readFileSync(CONFIG.productCachePath, 'utf-8'));
    console.log(`Loaded ${Object.keys(productCache).length} cached product IDs`);
  }
}

function saveProductCache() {
  fs.writeFileSync(CONFIG.productCachePath, JSON.stringify(productCache, null, 2));
}

function loadKeywords() {
  const content = fs.readFileSync(CONFIG.keywordsPath, 'utf-8');
  return JSON.parse(content);
}

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

function loadProgress() {
  if (fs.existsSync(CONFIG.progressFile)) {
    return JSON.parse(fs.readFileSync(CONFIG.progressFile, 'utf-8'));
  }
  return { completed: [], failed: [] };
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

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

async function getProductId(asin) {
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

async function createGoal(asin, sku) {
  const productId = await getProductId(asin);
  if (!productId) {
    return { skipped: true, reason: `Product not found for ASIN: ${asin}` };
  }

  const goalName = `${sku} -JN[SP_NON-BRANDED]`.substring(0, 60);

  // Payload with NO seed keywords - harvesting only
  const payload = {
    title: goalName,
    enabled: true,
    campaign_bidding_strategy: 'BIDDING_STRATEGY_LEGACY_FOR_SALES',
    max_budget: CONFIG.dailyBudget,
    target_acos: CONFIG.targetAcos / 100,
    products: [{ product_id: productId }],
    search_space_keywords: [], // Empty - harvesting will find keywords
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
  console.log(`    Keywords: HARVESTING ONLY (no seed keywords)`);

  const result = await apiRequest('/uni_goals/MULTI_AD_GROUP_CUSTOM_GOAL/', 'POST', payload);
  return result;
}

async function main() {
  console.log('===========================================');
  console.log('  Perpetua Harvesting-Only Goal Uploader');
  console.log('  (No seed keywords - harvesting will find them)');
  console.log('===========================================\n');

  loadProductCache();

  const allKeywords = loadKeywords();
  const asins = Object.keys(allKeywords);
  console.log(`Loaded ${asins.length} ASINs for harvesting-only goals\n`);

  const progress = loadProgress();
  const completedAsins = new Set(progress.completed || []);
  const remainingAsins = asins.filter(asin => !completedAsins.has(asin));

  console.log(`Already completed: ${completedAsins.size}`);
  console.log(`Remaining: ${remainingAsins.length}\n`);

  let successCount = 0;
  let errorCount = 0;
  let skippedCount = 0;

  for (let i = 0; i < remainingAsins.length; i++) {
    const asin = remainingAsins[i];
    const data = allKeywords[asin];

    console.log(`\n[${i + 1}/${remainingAsins.length}] Processing ${asin} (${data.sku})...`);

    try {
      const result = await createGoal(asin, data.sku);

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
    }

    await sleep(CONFIG.delayBetweenRequests);
  }

  console.log('\n===========================================');
  console.log('  Upload Complete!');
  console.log(`  Success: ${successCount}, Skipped: ${skippedCount}, Errors: ${errorCount}`);
  console.log('===========================================');
}

main().catch(console.error);
