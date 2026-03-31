<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { open } from "@tauri-apps/plugin-dialog";

  // --- Main state ---
  let folder    = $state("");
  let maxMb     = $state(5);
  let log       = $state("");
  let running   = $state(false);
  let activeTab = $state("split");

  // --- Filter state ---
  let filterFile     = $state("");
  let filterDomain   = $state("nav");
  let filterMinOut   = $state(50);
  let filterMinInstr = $state(10);
  let filterMaxRec   = $state(0);
  let filterDupes    = $state(true);
  let filterCode     = $state(false);
  let filterFormat   = $state("alpaca");
  let filterInclude  = $state("");
  let filterExclude  = $state("");

  // --- Smart Parse state ---
  let parseFile = $state("");

  // --- Augment state ---
  let varFile      = $state("");
  let varApiKey    = $state("");
  let varCount     = $state(3);
  let varMaxSource = $state(50);
  let varStyle     = $state("mixed");
  let varDelay     = $state(0.5);

  // --- Scraper state ---
  let scrapeUrl     = $state("");
  let scrapeToken   = $state("");
  let scrapeSplit   = $state("train");
  let scrapeMaxRows = $state(0);
  let scrapeRetries = $state(3);
  let scrapeHistory = $state<string[]>([]);

  const DOMAINS = [
    { id: "nav",     label: "🔵 No filter"  },
    { id: "svelte5", label: "🧡 Svelte 5"   },
    { id: "python",  label: "🐍 Python"     },
    { id: "coding",  label: "💻 Coding"     },
    { id: "webdev",  label: "🌐 Web Dev"    },
    { id: "blender", label: "🎨 Blender"    },
    { id: "zbrush",  label: "🗿 ZBrush"     },
    { id: "unreal",  label: "🎮 Unreal"     },
  ];

  const VAR_STYLES = [
    { id: "mixed",     label: "🎲 Mixed"      },
    { id: "rephrase",  label: "✏️ Rephrase"   },
    { id: "harder",    label: "💪 Harder"     },
    { id: "simpler",   label: "🌱 Simpler"    },
    { id: "different", label: "🔀 Different"  },
  ];

  const HF_EXAMPLES = [
    "iamtarun/python_code_instructions_18k_alpaca",
    "teknium/OpenHermes-2.5",
    "HuggingFaceH4/ultrachat_200k",
    "Open-Orca/OpenOrca",
    "codeparrot/github-code",
  ];

  // --- Helpers ---
  function appendLog(text: string) { log += text + "\n"; }
  function clearLog() { log = ""; }

  async function pickFolder() {
    const selected = await open({ directory: true, multiple: false });
    if (typeof selected === "string") folder = selected;
  }

  async function pickFile(setter: (v: string) => void) {
    const selected = await open({
      multiple: false,
      filters: [{ name: "JSON/JSONL", extensions: ["json", "jsonl"] }]
    });
    if (typeof selected === "string") {
      const parts = selected.split("\\");
      setter(parts.pop() || selected);
      if (!folder) folder = parts.join("\\");
    }
  }

  async function run(command: string, args: Record<string, any> = {}) {
    if (!folder.trim()) { appendLog("⚠️  Please select a working folder first!"); return; }
    running = true;
    clearLog();
    appendLog(`🚀 Running: ${command}...`);
    appendLog(`📁 Folder: ${folder}`);
    appendLog("─".repeat(44));
    try {
      const result = await invoke(command, { folder: folder.trim(), ...args });
      appendLog(result as string);
      appendLog("─".repeat(44));
      appendLog("✅ Done!");
    } catch (e) {
      appendLog(`❌ Error: ${e}`);
    }
    running = false;
  }

  async function runFilter() {
    if (!folder.trim())     { appendLog("⚠️  Select a folder!"); return; }
    if (!filterFile.trim()) { appendLog("⚠️  Select an input file!"); return; }
    running = true; clearLog();
    appendLog(`🔍 Filtering: ${filterFile}`);
    appendLog(`📁 Folder: ${folder}`);
    appendLog(`🎯 Domain: ${filterDomain} | Min output: ${filterMinOut} | Min instr: ${filterMinInstr}`);
    appendLog("─".repeat(44));
    try {
      const result = await invoke("filter_dataset", {
        folder, inputFile: filterFile, domain: filterDomain,
        minOutput: filterMinOut, minInstr: filterMinInstr,
        maxRecords: filterMaxRec, removeDupes: filterDupes,
        requireCode: filterCode, format: filterFormat,
        includeWords: filterInclude, excludeWords: filterExclude,
      });
      appendLog(result as string);
      appendLog("─".repeat(44));
      appendLog("✅ Saved: filtered_output.json");
    } catch (e) { appendLog(`❌ Error: ${e}`); }
    running = false;
  }

  async function runSmartParse() {
    if (!folder.trim())    { appendLog("⚠️  Select a folder!"); return; }
    if (!parseFile.trim()) { appendLog("⚠️  Select a file to analyze!"); return; }
    running = true; clearLog();
    appendLog(`🧠 Analyzing: ${parseFile}...`);
    appendLog("─".repeat(44));
    try {
      const result = await invoke("smart_parse", { folder, inputFile: parseFile });
      appendLog(result as string);
    } catch (e) { appendLog(`❌ Error: ${e}`); }
    running = false;
  }

  async function runVariations() {
    if (!folder.trim())    { appendLog("⚠️  Select a folder!"); return; }
    if (!varFile.trim())   { appendLog("⚠️  Select an input file!"); return; }
    if (!varApiKey.trim()) { appendLog("⚠️  Enter your Claude API key!"); return; }
    running = true; clearLog();
    const total = varMaxSource * varCount;
    appendLog(`🤖 Generating ~${total} variations...`);
    appendLog(`📄 File: ${varFile} | Source: ${varMaxSource} × ${varCount}`);
    appendLog("─".repeat(44));
    appendLog("⏳ Please wait — this may take several minutes...");
    try {
      const result = await invoke("generate_variations", {
        folder, inputFile: varFile, apiKey: varApiKey,
        count: varCount, maxSource: varMaxSource,
        style: varStyle, delay: varDelay,
      });
      appendLog(result as string);
      appendLog("✅ Saved: variations_output.json");
    } catch (e) { appendLog(`❌ Error: ${e}`); }
    running = false;
  }

  async function runScraper() {
    if (!scrapeUrl.trim()) { appendLog("⚠️  Enter a URL or HuggingFace dataset ID!"); return; }
    if (!folder.trim())    { appendLog("⚠️  Select an output folder!"); return; }
    running = true; clearLog();
    if (!scrapeHistory.includes(scrapeUrl)) {
      scrapeHistory = [scrapeUrl, ...scrapeHistory].slice(0, 8);
    }
    appendLog(`🌐 Scraper started...`);
    appendLog(`📡 URL: ${scrapeUrl}`);
    appendLog(`📁 Output: ${folder}`);
    if (scrapeMaxRows > 0) appendLog(`📊 Max rows: ${scrapeMaxRows}`);
    appendLog("─".repeat(44));
    appendLog("⏳ Downloading... (may take several minutes for large datasets)");
    try {
      const result = await invoke("scrape_dataset", {
        folder, url: scrapeUrl, hfToken: scrapeToken,
        split: scrapeSplit, maxRows: scrapeMaxRows, retries: scrapeRetries,
      });
      appendLog(result as string);
      appendLog("─".repeat(44));
      appendLog("✅ Download complete!");
      appendLog(`💡 Next steps: Analyze → Filter → Convert to Alpaca → Merge → Train!`);
    } catch (e) { appendLog(`❌ Error: ${e}`); }
    running = false;
  }
</script>

<main>
  <header>
    <span class="logo">🐂</span>
    <div class="header-text">
      <h1>Oxygen</h1>
      <span class="sub">ML Dataset Manager</span>
    </div>
  </header>

  <section class="folder-bar">
    <input type="text" placeholder="Select working folder..." bind:value={folder} />
    <button class="btn-pick" onclick={pickFolder} disabled={running}>📁 Folder</button>
  </section>

  <nav class="tabs">
    {#each [
      { id: "scrape",  label: "🌐 Scraper"   },
      { id: "split",   label: "✂️ Split"     },
      { id: "convert", label: "🔄 Convert"   },
      { id: "merge",   label: "🔗 Merge"     },
      { id: "filter",  label: "🔍 Filter"    },
      { id: "parse",   label: "🧠 Analyze"   },
      { id: "augment", label: "🤖 Augment"   },
    ] as tab}
      <button
        class="tab {activeTab === tab.id ? 'active' : ''} tab-{tab.id}"
        onclick={() => { activeTab = tab.id; clearLog(); }}
      >{tab.label}</button>
    {/each}
  </nav>

  <section class="content">

    <!-- SCRAPER -->
    {#if activeTab === "scrape"}
      <div class="card filter-card">
        <h2>🌐 Smart Dataset Scraper</h2>
        <p class="hint" style="color:#a0aec0">Download datasets from HuggingFace, GitHub or direct URLs. Auto-detects format, retries on failure, anti-blocking headers.</p>
        <div class="filter-section">
          <span class="filter-label">📡 URL or HuggingFace Dataset ID</span>
          <div class="url-row">
            <input type="text" class="filter-input url-input"
              placeholder="e.g. iamtarun/python_code_instructions_18k_alpaca or https://..."
              bind:value={scrapeUrl} />
          </div>
          <div class="quick-links">
            <span class="ql-label">⚡ Examples:</span>
            {#each HF_EXAMPLES as ex}
              <button class="ql-btn" onclick={() => scrapeUrl = ex}>{ex.split("/")[1]}</button>
            {/each}
          </div>
        </div>
        {#if scrapeHistory.length > 0}
          <div class="filter-section">
            <span class="filter-label">🕐 History</span>
            <div class="history-list">
              {#each scrapeHistory as h}
                <button class="history-btn" onclick={() => scrapeUrl = h}>
                  <span class="hist-icon">📋</span>
                  <span class="hist-url">{h.length > 55 ? h.slice(0,55) + "..." : h}</span>
                </button>
              {/each}
            </div>
          </div>
        {/if}
        <div class="filter-section">
          <span class="filter-label">⚙️ Settings</span>
          <div class="scrape-grid">
            <label class="row-label sm">
              <span>HF Token (private datasets)</span>
              <input type="password" class="filter-input" style="width:160px" placeholder="hf_xxx..." bind:value={scrapeToken} />
            </label>
            <label class="row-label sm">
              <span>Split</span>
              <select class="scrape-select" bind:value={scrapeSplit}>
                <option value="train">train</option>
                <option value="test">test</option>
                <option value="validation">validation</option>
                <option value="all">all</option>
              </select>
            </label>
            <label class="row-label sm">
              <span>Max rows (0 = all)</span>
              <input type="number" bind:value={scrapeMaxRows} min="0" style="width:80px" />
            </label>
            <label class="row-label sm">
              <span>Retries</span>
              <input type="number" bind:value={scrapeRetries} min="1" max="10" style="width:60px" />
            </label>
          </div>
        </div>
        <div class="shield-box">
          <div class="shield-item">🔄 <span>User-Agent rotation</span></div>
          <div class="shield-item">⏱️ <span>Retry with backoff</span></div>
          <div class="shield-item">🔑 <span>HF Token support</span></div>
          <div class="shield-item">📦 <span>Streaming mode</span></div>
          <div class="shield-item">🐙 <span>GitHub raw URL</span></div>
          <div class="shield-item">📡 <span>HF Datasets API</span></div>
        </div>
        <button class="btn-scrape" disabled={running || !scrapeUrl} onclick={runScraper}>
          {running ? "⏳ Downloading..." : "🚀 Start Download"}
        </button>
        <p class="hint">File saved to your folder. Then: <strong>Analyze → Filter → Convert → Merge → Train!</strong></p>
      </div>
    {/if}

    <!-- SPLIT -->
    {#if activeTab === "split"}
      <div class="card">
        <h2>✂️ Split Files</h2>
        <label class="row-label">
          <span>Max size (MB)</span>
          <input type="number" bind:value={maxMb} min="1" max="500" />
        </label>
        <div class="btn-row">
          <button class="btn-action" disabled={running} onclick={() => run("split_jsonl", { maxMb })}>📄 Split JSONL</button>
          <button class="btn-action" disabled={running} onclick={() => run("split_json",  { maxMb })}>📋 Split JSON</button>
        </div>
        <p class="hint">Splits large files into smaller chunks. Creates files named <code>_part0001</code>, <code>_part0002</code>, etc.</p>
      </div>
    {/if}

    <!-- CONVERT -->
    {#if activeTab === "convert"}
      <div class="card">
        <h2>🔄 Convert</h2>
        <div class="btn-row">
          <button class="btn-action" disabled={running} onclick={() => run("parquet_to_json")}>🗃️ Parquet → JSON</button>
          <button class="btn-action btn-blue" disabled={running} onclick={() => run("convert_to_alpaca")}>🦙 → Alpaca Format</button>
        </div>
        <p class="hint"><strong>Parquet → JSON</strong> — converts .parquet files to JSON.<br/><strong>→ Alpaca</strong> — converts any format to <code>instruction / input / output</code>.</p>
      </div>
    {/if}

    <!-- MERGE -->
    {#if activeTab === "merge"}
      <div class="card">
        <h2>🔗 Merge Files</h2>
        <button class="btn-action btn-blue" style="max-width:300px" disabled={running} onclick={() => run("merge_alpaca")}>🔗 Merge Alpaca Files</button>
        <p class="hint">Merges all JSON files in the folder into one <code>alpaca_merged.json</code>, automatically removing duplicate instructions.</p>
      </div>
    {/if}

    <!-- FILTER -->
    {#if activeTab === "filter"}
      <div class="card filter-card">
        <h2>🔍 Dataset Filter</h2>
        <div class="filter-row">
          <span class="filter-label">📄 Input file</span>
          <div class="file-pick-row">
            <input type="text" class="filter-input" placeholder="file.json" bind:value={filterFile} />
            <button class="btn-sm" onclick={() => pickFile(v => filterFile = v)}>📂</button>
          </div>
        </div>
        <div class="filter-section">
          <span class="filter-label">🎯 Domain</span>
          <div class="domain-grid">
            {#each DOMAINS as d}
              <button class="domain-btn {filterDomain === d.id ? 'domain-active' : ''}" onclick={() => filterDomain = d.id}>{d.label}</button>
            {/each}
          </div>
        </div>
        <div class="filter-section">
          <span class="filter-label">📊 Quality</span>
          <div class="quality-grid">
            <label class="row-label sm"><span>Min output (words)</span><input type="number" bind:value={filterMinOut} min="0" /></label>
            <label class="row-label sm"><span>Min instruction</span><input type="number" bind:value={filterMinInstr} min="0" /></label>
            <label class="row-label sm"><span>Max records (0=all)</span><input type="number" bind:value={filterMaxRec} min="0" /></label>
          </div>
        </div>
        <div class="filter-section">
          <span class="filter-label">⚙️ Options</span>
          <div class="check-row">
            <label class="check-label"><input type="checkbox" bind:checked={filterDupes} /><span>Remove duplicates</span></label>
            <label class="check-label"><input type="checkbox" bind:checked={filterCode} /><span>Require code in output</span></label>
          </div>
        </div>
        <div class="filter-section">
          <span class="filter-label">✏️ Custom filters</span>
          <div class="custom-grid">
            <div class="custom-field"><span class="field-label">✅ Required words (comma-separated)</span><input type="text" class="filter-input" placeholder="svelte, $state" bind:value={filterInclude} /></div>
            <div class="custom-field"><span class="field-label">❌ Excluded words (comma-separated)</span><input type="text" class="filter-input" placeholder="react, vue" bind:value={filterExclude} /></div>
          </div>
        </div>
        <div class="filter-section">
          <span class="filter-label">📦 Output format</span>
          <div class="format-row">
            {#each [{id:"alpaca",label:"🦙 Alpaca"},{id:"messages",label:"💬 Messages"},{id:"jsonl",label:"📄 JSONL"}] as f}
              <button class="fmt-btn {filterFormat === f.id ? 'fmt-active' : ''}" onclick={() => filterFormat = f.id}>{f.label}</button>
            {/each}
          </div>
        </div>
        <button class="btn-filter" disabled={running} onclick={runFilter}>{running ? "⏳ Filtering..." : "🔍 Filter Dataset"}</button>
        <p class="hint">Result saved as → <code>filtered_output.json</code></p>
      </div>
    {/if}

    <!-- SMART PARSE -->
    {#if activeTab === "parse"}
      <div class="card">
        <h2>🧠 Smart Parse — Dataset Analyzer</h2>
        <p class="hint" style="color:#a0aec0">Auto-detects JSON format, analyzes field structure, word count distribution, language, duplicates, and recommends optimal filter settings.</p>
        <div class="filter-row">
          <span class="filter-label">📄 File to analyze</span>
          <div class="file-pick-row">
            <input type="text" class="filter-input" placeholder="file.json or file.jsonl" bind:value={parseFile} />
            <button class="btn-sm" onclick={() => pickFile(v => parseFile = v)}>📂</button>
          </div>
        </div>
        <button class="btn-parse" disabled={running || !parseFile} onclick={runSmartParse}>{running ? "⏳ Analyzing..." : "🔬 Analyze File"}</button>
        <div class="parse-features">
          <div class="feature">📋 <strong>Format</strong><span>Alpaca, Messages, HF, problem/solution</span></div>
          <div class="feature">📏 <strong>Length</strong><span>Avg word count, min/max</span></div>
          <div class="feature">🔤 <strong>Language</strong><span>EN, LV, RU detection</span></div>
          <div class="feature">🔄 <strong>Duplicates</strong><span>Percentage found</span></div>
          <div class="feature">💻 <strong>Code</strong><span>% records with code blocks</span></div>
          <div class="feature">💡 <strong>Suggestions</strong><span>Optimal filter parameters</span></div>
        </div>
      </div>
    {/if}

    <!-- AUGMENT -->
    {#if activeTab === "augment"}
      <div class="card filter-card">
        <h2>🤖 Variation Generator</h2>
        <p class="hint" style="color:#a0aec0">Uses Claude API to generate new variations from existing records. Turn 100 records into 300-500 unique entries!</p>
        <div class="filter-row">
          <span class="filter-label">📄 Input file</span>
          <div class="file-pick-row">
            <input type="text" class="filter-input" placeholder="file.json" bind:value={varFile} />
            <button class="btn-sm" onclick={() => pickFile(v => varFile = v)}>📂</button>
          </div>
        </div>
        <div class="filter-row">
          <span class="filter-label">🔑 Claude API Key</span>
          <input type="password" class="filter-input" placeholder="sk-ant-api03-..." bind:value={varApiKey} />
        </div>
        <div class="filter-section">
          <span class="filter-label">⚙️ Settings</span>
          <div class="quality-grid">
            <label class="row-label sm"><span>Variations per record</span><input type="number" bind:value={varCount} min="1" max="10" /></label>
            <label class="row-label sm"><span>Max source records</span><input type="number" bind:value={varMaxSource} min="1" /></label>
            <label class="row-label sm"><span>API delay (s)</span><input type="number" bind:value={varDelay} min="0" step="0.1" /></label>
          </div>
        </div>
        <div class="filter-section">
          <span class="filter-label">🎨 Variation style</span>
          <div class="style-grid">
            {#each VAR_STYLES as s}
              <button class="style-btn {varStyle === s.id ? 'style-active' : ''}" onclick={() => varStyle = s.id}>{s.label}</button>
            {/each}
          </div>
        </div>
        <div class="estimate-box">
          <span>📊 Estimated output:</span>
          <strong>{varMaxSource} × {varCount} = ~{varMaxSource * varCount} records</strong>
          <span>⏱️ ~{Math.ceil(varMaxSource * varCount * varDelay / 60)} min</span>
        </div>
        <button class="btn-augment" disabled={running || !varFile || !varApiKey} onclick={runVariations}>{running ? "⏳ Generating..." : "🚀 Start Generation"}</button>
        <p class="hint">Result → <code>variations_output.json</code> | Then use <strong>Merge</strong> to combine!</p>
      </div>
    {/if}

  </section>

  <section class="log-section">
    <div class="log-header">
      <span>📋 Output</span>
      {#if running}<span class="spinner">⏳ Running...</span>{/if}
      <button class="btn-clear" onclick={clearLog}>🗑️ Clear</button>
    </div>
    <pre class="log">{log || "Script output will appear here..."}</pre>
  </section>
</main>

<style>
  :global(*) { box-sizing: border-box; margin: 0; padding: 0; }
  :global(body) { font-family: 'Segoe UI', system-ui, sans-serif; background: #0f1117; color: #e2e8f0; min-height: 100vh; user-select: none; }

  main { max-width: 920px; margin: 0 auto; padding: 16px 18px; display: flex; flex-direction: column; gap: 11px; }

  header { display:flex; align-items:center; gap:12px; padding-bottom:11px; border-bottom:1px solid #2d3748; }
  .logo { font-size:28px; }
  .header-text { display:flex; flex-direction:column; gap:2px; }
  h1 { font-size:19px; font-weight:700; color:#63b3ed; letter-spacing:1px; }
  .sub { font-size:10px; color:#4a5568; text-transform:uppercase; letter-spacing:1.5px; }

  .folder-bar { display:flex; gap:8px; }
  .folder-bar input { flex:1; background:#1a202c; border:1px solid #2d3748; border-radius:8px; padding:8px 13px; color:#e2e8f0; font-size:13px; outline:none; }
  .folder-bar input:focus { border-color:#4299e1; }
  .folder-bar input::placeholder { color:#4a5568; }
  .btn-pick { background:#2d3748; color:#e2e8f0; border:1px solid #4a5568; border-radius:8px; padding:8px 14px; cursor:pointer; font-size:13px; white-space:nowrap; transition:all 0.2s; }
  .btn-pick:hover:not(:disabled) { background:#4a5568; }
  .btn-pick:disabled { opacity:0.4; cursor:not-allowed; }

  .tabs { display:flex; gap:2px; background:#1a202c; padding:3px; border-radius:10px; border:1px solid #2d3748; }
  .tab { flex:1; padding:7px 2px; border:none; border-radius:7px; background:transparent; color:#718096; cursor:pointer; font-size:10.5px; font-weight:500; transition:all 0.2s; text-align:center; }
  .tab.active { color:#fff; }
  .tab:hover:not(.active) { background:#2d3748; color:#e2e8f0; }
  .tab-scrape.active  { background:#1a5276; }
  .tab-split.active   { background:#2b6cb0; }
  .tab-convert.active { background:#276749; }
  .tab-merge.active   { background:#553c9a; }
  .tab-filter.active  { background:#744210; }
  .tab-parse.active   { background:#1d4e89; }
  .tab-augment.active { background:#702459; }

  .card { background:#1a202c; border:1px solid #2d3748; border-radius:12px; padding:16px; display:flex; flex-direction:column; gap:12px; min-height:120px; }
  .card h2 { font-size:14px; color:#90cdf4; font-weight:600; }
  .filter-card { gap:12px; }

  .row-label { display:flex; align-items:center; gap:10px; font-size:13px; color:#a0aec0; }
  .row-label.sm { font-size:11px; }
  .row-label input[type="number"] { width:70px; background:#2d3748; border:1px solid #4a5568; border-radius:6px; padding:5px 8px; color:#e2e8f0; font-size:12px; outline:none; }

  .btn-row { display:flex; gap:10px; flex-wrap:wrap; }
  .btn-action { flex:1; min-width:140px; padding:10px 14px; background:#2d3748; border:1px solid #4a5568; border-radius:8px; color:#e2e8f0; font-size:13px; font-weight:500; cursor:pointer; transition:all 0.2s; }
  .btn-action:hover:not(:disabled) { background:#4a5568; border-color:#63b3ed; }
  .btn-action:disabled { opacity:0.4; cursor:not-allowed; }
  .btn-blue { background:#2b6cb0; border-color:#4299e1; }
  .btn-blue:hover:not(:disabled) { background:#2c5282; }

  .hint { font-size:11.5px; color:#4a5568; line-height:1.6; }
  .hint strong { color:#718096; }
  .hint code { background:#2d3748; padding:1px 5px; border-radius:4px; font-family:monospace; font-size:11px; color:#68d391; }

  .url-row { display:flex; gap:8px; }
  .url-input { font-size:12px; }
  .quick-links { display:flex; align-items:center; gap:6px; flex-wrap:wrap; margin-top:4px; }
  .ql-label { font-size:11px; color:#4a5568; white-space:nowrap; }
  .ql-btn { background:#1a1f2e; border:1px solid #2d3748; border-radius:5px; padding:3px 8px; color:#63b3ed; cursor:pointer; font-size:10px; transition:all 0.15s; }
  .ql-btn:hover { background:#2d3748; border-color:#63b3ed; }

  .history-list { display:flex; flex-direction:column; gap:4px; }
  .history-btn { display:flex; align-items:center; gap:8px; background:#0d1117; border:1px solid #2d3748; border-radius:6px; padding:6px 10px; color:#718096; cursor:pointer; font-size:11px; transition:all 0.15s; text-align:left; }
  .history-btn:hover { background:#1a202c; border-color:#4a5568; color:#e2e8f0; }
  .hist-icon { font-size:12px; }
  .hist-url { flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }

  .scrape-grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
  .scrape-select { background:#2d3748; border:1px solid #4a5568; border-radius:6px; padding:5px 8px; color:#e2e8f0; font-size:12px; outline:none; cursor:pointer; }

  .shield-box { display:grid; grid-template-columns:repeat(3,1fr); gap:6px; }
  .shield-item { background:#0d1117; border:1px solid #1a3a1a; border-radius:7px; padding:8px 10px; font-size:11px; color:#68d391; display:flex; align-items:center; gap:6px; }
  .shield-item span { color:#4a5568; }

  .btn-scrape { padding:12px; background:#1a5276; border:1px solid #2980b9; border-radius:9px; color:#aed6f1; font-size:14px; font-weight:600; cursor:pointer; transition:all 0.2s; }
  .btn-scrape:hover:not(:disabled) { background:#154360; }
  .btn-scrape:disabled { opacity:0.4; cursor:not-allowed; }

  .filter-row { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
  .filter-label { font-size:11.5px; color:#a0aec0; font-weight:600; min-width:115px; }
  .filter-input { flex:1; background:#2d3748; border:1px solid #4a5568; border-radius:7px; padding:7px 10px; color:#e2e8f0; font-size:12px; outline:none; transition:border-color 0.2s; }
  .filter-input:focus { border-color:#4299e1; }
  .filter-input::placeholder { color:#4a5568; }
  .file-pick-row { display:flex; gap:6px; flex:1; }
  .file-pick-row .filter-input { flex:1; }
  .btn-sm { background:#2d3748; border:1px solid #4a5568; border-radius:7px; padding:7px 10px; color:#e2e8f0; cursor:pointer; font-size:13px; transition:all 0.2s; }
  .btn-sm:hover { background:#4a5568; }
  .filter-section { display:flex; flex-direction:column; gap:7px; }
  .domain-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:5px; }
  .domain-btn { padding:6px 4px; background:#2d3748; border:1px solid #4a5568; border-radius:7px; color:#718096; cursor:pointer; font-size:10.5px; font-weight:500; transition:all 0.15s; text-align:center; }
  .domain-btn:hover { background:#4a5568; color:#e2e8f0; }
  .domain-active { background:#2d3a1e; border-color:#68d391; color:#68d391; font-weight:700; }
  .quality-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; }
  .check-row { display:flex; gap:20px; flex-wrap:wrap; }
  .check-label { display:flex; align-items:center; gap:8px; font-size:12px; color:#a0aec0; cursor:pointer; }
  .check-label input { width:14px; height:14px; cursor:pointer; accent-color:#805ad5; }
  .custom-grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
  .custom-field { display:flex; flex-direction:column; gap:4px; }
  .field-label { font-size:10.5px; color:#4a5568; }
  .format-row { display:flex; gap:6px; }
  .fmt-btn { flex:1; padding:7px; background:#2d3748; border:1px solid #4a5568; border-radius:7px; color:#718096; cursor:pointer; font-size:12px; font-weight:500; transition:all 0.2s; }
  .fmt-btn:hover { background:#4a5568; color:#e2e8f0; }
  .fmt-active { background:#744210; border-color:#d69e2e; color:#faf089; }
  .btn-filter { padding:10px; background:#744210; border:1px solid #d69e2e; border-radius:9px; color:#faf089; font-size:13px; font-weight:600; cursor:pointer; transition:all 0.2s; }
  .btn-filter:hover:not(:disabled) { background:#5c3c0d; }
  .btn-filter:disabled { opacity:0.4; cursor:not-allowed; }

  .btn-parse { padding:10px; background:#1d4e89; border:1px solid #3182ce; border-radius:9px; color:#bee3f8; font-size:13px; font-weight:600; cursor:pointer; transition:all 0.2s; }
  .btn-parse:hover:not(:disabled) { background:#1a3f6e; }
  .btn-parse:disabled { opacity:0.4; cursor:not-allowed; }
  .parse-features { display:grid; grid-template-columns:repeat(3,1fr); gap:7px; }
  .feature { background:#0d1117; border:1px solid #2d3748; border-radius:8px; padding:9px; display:flex; flex-direction:column; gap:3px; font-size:10.5px; }
  .feature strong { color:#90cdf4; }
  .feature span { color:#4a5568; }

  .style-grid { display:grid; grid-template-columns:repeat(5,1fr); gap:5px; }
  .style-btn { padding:6px 3px; background:#2d3748; border:1px solid #4a5568; border-radius:7px; color:#718096; cursor:pointer; font-size:10.5px; font-weight:500; transition:all 0.15s; text-align:center; }
  .style-btn:hover { background:#4a5568; color:#e2e8f0; }
  .style-active { background:#3d1a4e; border-color:#b794f4; color:#e9d8fd; font-weight:700; }
  .estimate-box { background:#0d1117; border:1px solid #2d3748; border-radius:8px; padding:10px 12px; display:flex; align-items:center; gap:14px; font-size:12px; color:#718096; }
  .estimate-box strong { color:#68d391; font-size:14px; }
  .btn-augment { padding:11px; background:#702459; border:1px solid #b83280; border-radius:9px; color:#fed7e2; font-size:13px; font-weight:600; cursor:pointer; transition:all 0.2s; }
  .btn-augment:hover:not(:disabled) { background:#561c45; }
  .btn-augment:disabled { opacity:0.4; cursor:not-allowed; }

  .log-section { background:#0d1117; border:1px solid #2d3748; border-radius:12px; overflow:hidden; }
  .log-header { display:flex; align-items:center; gap:10px; padding:8px 14px; background:#1a202c; border-bottom:1px solid #2d3748; font-size:12px; color:#718096; }
  .spinner { color:#f6ad55; animation:pulse 1.2s ease-in-out infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }
  .btn-clear { margin-left:auto; background:none; border:none; color:#4a5568; cursor:pointer; font-size:12px; }
  .btn-clear:hover { color:#a0aec0; }
  .log { padding:13px 15px; font-family:'Cascadia Code','Consolas',monospace; font-size:12px; color:#68d391; white-space:pre-wrap; word-break:break-all; min-height:140px; max-height:260px; overflow-y:auto; line-height:1.7; }
</style>
