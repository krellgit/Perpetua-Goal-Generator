const fs = require('fs');
const path = require('path');

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
  }
}

function saveProductCache() {
  fs.writeFileSync(CONFIG.productCachePath, JSON.stringify(productCache, null, 2));
}

function loadKeywords() {
  return JSON.parse(fs.readFileSync(CONFIG.keywordsPath, 'utf-8'));
}

function saveProgress(asin, status, error = null) {
  const progress = loadProgress();
  if (status === 'success' && !progress.completed.includes(asin)) {
    progress.completed.push(asin);
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

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function apiRequest(endpoint, method = 'GET', body = null) {
  const url = CONFIG.baseUrl + '/geo_companies/' + CONFIG.companyId + endpoint;
  const opts = {
    method,
    headers: {
      'Authorization': 'Token ' + CONFIG.authToken,
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      'Origin': 'https://app.perpetua.io',
      'Referer': 'https://app.perpetua.io/',
    },
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(url, opts);
  if (!res.ok) throw new Error('API error ' + res.status + ': ' + (await res.text()));
  return res.json();
}

async function graphqlRequest(query, variables) {
  const res = await fetch('https://apollo.perpetua.io/', {
    method: 'POST',
    headers: {
      'Authorization': 'Token ' + CONFIG.authToken,
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      'Origin': 'https://app.perpetua.io',
      'Referer': 'https://app.perpetua.io/',
    },
    body: JSON.stringify({ operationName: 'SPChildProductPerfList', query, variables }),
  });
  if (!res.ok) throw new Error('GraphQL error ' + res.status + ': ' + (await res.text()));
  return res.json();
}

const QUERY = 'query SPChildProductPerfList($geoCompanyId: Int!, $startDate: Date, $endDate: Date, $offset: Int, $limit: Int, $search: String) { childProductListPerformance(geoCompanyId: $geoCompanyId, startDate: $startDate, endDate: $endDate, offset: $offset, limit: $limit, search: $search) { edges { node { productId asin } } } }';

async function getProductId(asin) {
  if (productCache[asin]) return productCache[asin];
  const endDate = new Date().toISOString().split('T')[0];
  const startDate = new Date(Date.now() - 7*24*60*60*1000).toISOString().split('T')[0];
  const result = await graphqlRequest(QUERY, { geoCompanyId: 58088, startDate, endDate, offset: 0, limit: 25, search: asin });
  const edges = result.data && result.data.childProductListPerformance && result.data.childProductListPerformance.edges;
  if (edges) {
    const match = edges.find(function(e) { return e.node.asin === asin; });
    if (match) {
      productCache[asin] = match.node.productId;
      saveProductCache();
      return match.node.productId;
    }
  }
  return null;
}

async function createGoal(asin, sku, keywords) {
  const productId = await getProductId(asin);
  if (!productId) return { skipped: true, reason: 'Product not found: ' + asin };

  const searchSpaceKeywords = [];
  var broadKws = keywords.broad || [];
  for (var i = 0; i < broadKws.length; i++) {
    searchSpaceKeywords.push({ keyword_text: broadKws[i], match_type: 'BROAD' });
  }

  var goalName = sku + ' -JN[SP_NON-BRANDED]';
  if (goalName.length > 60) goalName = goalName.substring(0, 60);

  const payload = {
    title: goalName,
    enabled: true,
    campaign_bidding_strategy: 'BIDDING_STRATEGY_LEGACY_FOR_SALES',
    max_budget: CONFIG.dailyBudget,
    target_acos: CONFIG.targetAcos / 100,
    products: [{ product_id: productId }],
    search_space_keywords: searchSpaceKeywords,
    negative_keyword_overrides: [],
    optimization_objective_state: { optimization_objective: 'ACOS_COMPLIANCE' },
    placement_optimization: {},
    keyword_harvesting: {
      harvesting_mode: 'AUTOMATICALLY_ADD',
      user_enabled_match_types: ['EXACT', 'PHRASE', 'BROAD'],
      harvesting_criteria: { type: 'keyword_targeting_simple', conversion_threshold: 1, phrases: [] },
    },
  };

  console.log('  Creating: ' + payload.title + ' (seed: "' + (searchSpaceKeywords[0] ? searchSpaceKeywords[0].keyword_text : 'none') + '")');
  return await apiRequest('/uni_goals/MULTI_AD_GROUP_CUSTOM_GOAL/', 'POST', payload);
}

async function main() {
  console.log('=== Harvesting Goals Upload ===\n');
  loadProductCache();

  const allKeywords = loadKeywords();
  const asins = Object.keys(allKeywords);
  const progress = loadProgress();
  const remaining = asins.filter(function(a) { return !progress.completed.includes(a); });

  console.log('Total: ' + asins.length + ', Remaining: ' + remaining.length + '\n');

  var success = 0, skipped = 0, errors = 0;

  for (var i = 0; i < remaining.length; i++) {
    const asin = remaining[i];
    const data = allKeywords[asin];
    console.log('[' + (i+1) + '/' + remaining.length + '] ' + asin + ' (' + data.sku + ')');

    try {
      const result = await createGoal(asin, data.sku, data);
      if (result && result.skipped) {
        console.log('  SKIPPED: ' + result.reason);
        skipped++;
      } else {
        saveProgress(asin, 'success');
        success++;
        console.log('  Success!');
      }
    } catch (e) {
      console.log('  ERROR: ' + e.message);
      saveProgress(asin, 'error', e.message);
      errors++;
      if (e.message.indexOf('401') >= 0 || e.message.indexOf('403') >= 0) break;
    }
    await sleep(CONFIG.delayBetweenRequests);
  }

  console.log('\n=== Done! Success: ' + success + ', Skipped: ' + skipped + ', Errors: ' + errors + ' ===');
}

main().catch(console.error);
