<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { open, save } from "@tauri-apps/plugin-dialog";
  import { onMount } from "svelte";

  const APP_VERSION = "1.2.4";

  // --- Main state ---
  let folder    = $state("");
  let log       = $state("");
  let running   = $state(false);
  let activeTab = $state("dash");
  let showAbout = $state(false);

  // --- Dashboard state ---
  let dashData: any = $state(null);
  let dashLoading   = $state(false);

  // --- Scraper state ---
  let scrapeUrl     = $state("");
  let scrapeOutput  = $state("downloads");
  let scrapeToken   = $state("");
  let scrapeSplit   = $state("train");
  let scrapeMaxRows = $state(0);
  let scrapeRetries = $state(3);
  let scrapeHistory = $state<string[]>([]);

  // --- Analyze state ---
  let parseFile     = $state("");

  // --- Queue state ---
  type QueueStatus = "pending" | "running" | "done" | "error" | "skipped";
  type QueueStepType = "scrape" | "parse" | "filter" | "convert" | "merge" | "split" | "augment";

  interface QueueStep {
    id: string;
    type: QueueStepType;
    label: string;
    icon: string;
    status: QueueStatus;
    config: any;
    duration?: number;
  }

  let queueSteps: QueueStep[] = $state([]);
  let queueRunning = $state(false);
  let queueLog     = $state("");
  let showAddStep  = $state(false);

  const STEP_DEFAULTS: Record<QueueStepType, any> = {
    scrape:  { label: "Scrape Dataset",  icon: "🌐", config: { url: "", split: "train" } },
    parse:   { label: "Analyze Dataset", icon: "🧠", config: { inputFile: "" } },
    filter:  { label: "Filter Samples",  icon: "🔍", config: { domain: "nav", removeDupes: true, requireCode: false } },
    convert: { label: "Convert Alpaca",  icon: "🔄", config: {} },
    merge:   { label: "Merge Files",     icon: "🔗", config: {} },
    split:   { label: "Split Files",     icon: "✂️", config: { maxMb: 20, type: "json" } },
    augment: { label: "Augment Data",    icon: "🤖", config: { count: 3, style: "mixed" } },
  };

  const QUEUE_PRESETS = [
    { name: "Full Cycle", icon: "♻️", steps: ["scrape", "parse", "filter", "convert", "merge"] },
    { name: "Quick Filter", icon: "⚡", steps: ["parse", "filter"] },
    { name: "Modernize", icon: "✨", steps: ["convert", "merge", "augment"] },
  ];

  // --- Tab specific states ---
  let maxMb         = $state(50);
  let filterFile    = $state("");
  let filterOutput  = $state("filtered_output.json");
  let filterDomain  = $state("nav");
  let filterMinOut  = $state(50);
  let filterMinInstr = $state(10);
  let filterMaxRec   = $state(0);
  let filterDupes    = $state(true);
  let filterCode     = $state(false);
  let filterFormat   = $state("alpaca");
  let filterInclude  = $state("");
  let filterExclude  = $state("");

  let varFile       = $state("");
  let varOutput     = $state("variations_output.json");
  let varApiKey     = $state("");
  let varKeyStored  = $state(false);
  let varKeySaving  = $state(false);
  let varCount      = $state(3);
  let varMaxSource  = $state(100);
  let varStyle      = $state("mixed");
  let varDelay      = $state(0.5);

  // --- Score state ---
  let scoreFile      = $state("filtered_output.json");
  let scoreOutput    = $state("scored_output.json");
  let scoreMinScore  = $state(5);
  let scoreTop       = $state(0);
  let scoreStatsOnly = $state(false);
  let scoreDist: any[] = $state([]);
  let scoreAvg: number = $state(0);
  let scoreTotal: number = $state(0);
  let scoreFiltered: number = $state(0);

  // --- Language state ---
  let langFile      = $state("alpaca_merged.json");
  let langOutput    = $state("lang_filtered.json");
  let langSelected  = $state<string[]>(["en", "lv"]);
  let langAutoMode  = $state(false);
  let langStatsOnly = $state(false);
  let langField     = $state("instruction");
  let langStats: any[] = $state([]);
  let langTotal: number = $state(0);
  let langSaved: number = $state(0);

  // --- Preview state ---
  let prevFile     = $state("");
  let prevData: any[] = $state([]);
  let prevSearch   = $state("");
  let prevPage     = $state(1);
  let prevLimit    = $state(20);
  let prevTotal    = $state(0);
  let prevSelectedIds = $state<string[]>([]);
  let prevExpandedId  = $state<string | null>(null);

  const DOMAINS = [
    { id: "nav",     label: "🔵 No filter"  },
    { id: "svelte5", label: "🧡 Svelte 5"   },
    { id: "python",  label: "🐍 Python"     },
    { id: "coding",  label: "💻 Coding"     },
    { id: "webdev",  label: "🌐 Web Dev"    },
    { id: "blender", label: "🎨 Blender"    },
    { id: "unreal",  label: "🎮 Unreal"     },
  ];

  const LANGUAGES = [
    { id: "en", label: "English", flag: "🇺🇸" },
    { id: "lv", label: "Latvian", flag: "🇱🇻" },
    { id: "ru", label: "Russian", flag: "🇷🇺" },
    { id: "de", label: "German",  flag: "🇩🇪" },
    { id: "fr", label: "French",  flag: "🇫🇷" },
    { id: "es", label: "Spanish", flag: "🇪🇸" },
    { id: "it", label: "Italian", flag: "🇮🇹" },
    { id: "jp", label: "Japanese", flag: "🇯🇵" },
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
    "Open-Orca/OpenOrca",
    "codeparrot/github-code",
  ];

  // --- Helpers ---
  function appendLog(text: string) { log += text + "\n"; }
  function clearLog() { log = ""; }
  function setTab(id: string) { activeTab = id; clearLog(); }

  function validate(checks: { cond: boolean; msg: string }[]): boolean {
    for (const c of checks) {
      if (!c.cond) { appendLog(`⚠️ ${c.msg}`); return false; }
    }
    return true;
  }

  async function pickOutputFile(currentName: string, setter: (v: string) => void) {
    const path = await save({ defaultPath: currentName, filters: [{ name: "JSON", extensions: ["json", "jsonl"] }] });
    if (path) {
      const parts = path.split(/[\/\\]/);
      setter(parts.pop() || currentName);
    }
  }

  async function pickFolder() {
    const selected = await open({ directory: true, multiple: false });
    if (typeof selected === "string") {
      folder = selected;
      localStorage.setItem("oxygen_last_folder", folder);
      loadDashboard();
    }
  }

  async function pickFile(setter: (v: string) => void) {
    const selected = await open({
      multiple: false,
      filters: [{ name: "JSON/JSONL", extensions: ["json", "jsonl"] }]
    });
    if (typeof selected === "string") {
       const parts = selected.split(/[\/\\]/);
       setter(parts.pop() || selected);
       if (!folder) folder = parts.join("\\");
    }
  }

  onMount(async () => {
    const last = localStorage.getItem("oxygen_last_folder");
    if (last) { folder = last; loadDashboard(); }

    // Check if API key is stored in OS keychain
    try {
      const stored = await invoke<string>("get_api_key");
      varKeyStored = stored !== "no_key" && stored.length > 0;
    } catch { varKeyStored = false; }
  });

  async function saveApiKey() {
    if (!varApiKey.trim()) { appendLog("⚠️ Enter an API key first."); return; }
    varKeySaving = true;
    try {
      await invoke("set_api_key", { key: varApiKey.trim() });
      varKeyStored = true;
      varApiKey = "";
      appendLog("🔐 API key saved to system keychain.");
    } catch (e) { appendLog(`❌ Failed to save key: ${e}`); }
    varKeySaving = false;
  }

  async function clearApiKey() {
    try {
      await invoke("delete_api_key");
      varKeyStored = false;
      varApiKey = "";
      appendLog("🗑️ API key removed from keychain.");
    } catch (e) { appendLog(`❌ Failed to remove key: ${e}`); }
  }

  // --- Actions ---
  async function loadDashboard() {
    if (!folder) return;
    dashLoading = true;
    try {
      const res = await invoke("get_dashboard", { folder });
      dashData = JSON.parse(res as string);
    } catch (e) { appendLog(`❌ Dash Error: ${e}`); }
    dashLoading = false;
  }

  async function checkEnv() {
    if (!folder) return;
    running = true; clearLog();
    try {
      const res = await invoke("check_environment", { working_dir: folder });
      appendLog(res as string);
    } catch (e) { appendLog(`❌ Env Error: ${e}`); }
    running = false;
  }

  async function run(command: string, args: any = {}) {
    if (!folder) { appendLog("⚠️ Select folder!"); return; }
    running = true; clearLog();
    appendLog(`🚀 Running: ${command}...`);
    try {
      const res = await invoke(command, { folder, ...args });
      appendLog(res as string);
      loadDashboard();
    } catch (e) { appendLog(`❌ Error: ${e}`); }
    running = false;
  }

  async function runFilter() {
    if (!validate([
      { cond: !!folder,      msg: "Please select a working folder first." },
      { cond: !!filterFile,  msg: "Please select an input file." },
      { cond: !!filterOutput, msg: "Please specify an output file name." },
    ])) return;
    run("filter_dataset", {
      inputFile:    filterFile,
      outputFile:   filterOutput,
      domain:       filterDomain,
      minOutput:    filterMinOut,
      minInstr:     filterMinInstr,
      maxRecords:   filterMaxRec,
      removeDupes:  filterDupes,
      requireCode:  filterCode,
      format:       filterFormat,
      includeWords: filterInclude,
      excludeWords: filterExclude,
    });
  }

  async function runScore() {
    if (!validate([
      { cond: !!folder,      msg: "Please select a working folder first." },
      { cond: !!scoreFile,   msg: "Please select an input file." },
      { cond: !!scoreOutput, msg: "Please specify an output file name." },
    ])) return;
    running = true; clearLog();
    appendLog(`⭐ Scoring: ${scoreFile}...`);
    try {
      const res = await invoke("score_dataset", {
        folder,
        inputFile:  scoreFile,
        outputFile: scoreOutput,
        minScore:   scoreMinScore,
        maxScore:   10,
        top:        scoreTop,
        statsOnly:  scoreStatsOnly,
      });
      const data = JSON.parse(res as string);
      scoreDist = data.distribution;
      scoreAvg = data.average;
      scoreTotal = data.total;
      scoreFiltered = data.saved;
      appendLog("✅ Scoring complete!");
    } catch (e) { appendLog(`❌ Score Error: ${e}`); }
    running = false;
  }

  function scoreColor(s: number) {
    if (s >= 8) return "#68d391";
    if (s >= 5) return "#f6ad55";
    return "#fc8181";
  }

  async function runLangFilter() {
    if (!validate([
      { cond: !!folder,     msg: "Please select a working folder first." },
      { cond: !!langFile,   msg: "Please select an input file." },
      { cond: !!langOutput, msg: "Please specify an output file name." },
    ])) return;
    running = true; clearLog();
    appendLog(`🌍 Analyzing languages: ${langFile}...`);
    try {
      const res = await invoke("filter_language", {
        folder,
        inputFile:  langFile,
        outputFile: langOutput,
        lang:       langSelected.join(","),
        field:      langField,
        statsOnly:  langStatsOnly,
        addField:   langAutoMode,
      });
      const data = JSON.parse(res as string);
      langStats = data.stats;
      langTotal = data.total;
      langSaved = data.saved;
      appendLog("✅ Language filtering complete!");
    } catch (e) { appendLog(`❌ Lang Error: ${e}`); }
    running = false;
  }

  function langColor(l: string) {
    const colors: any = { en: "#4299e1", lv: "#9f7aea", ru: "#ed64a1", de: "#ed8936" };
    return colors[l] || "#4a5568";
  }

  function toggleLang(id: string) {
    if (langSelected.includes(id)) langSelected = langSelected.filter(x => x !== id);
    else langSelected = [...langSelected, id];
  }

  async function runSmartParse() {
    if (!validate([
      { cond: !!folder,    msg: "Please select a working folder first." },
      { cond: !!parseFile, msg: "Please select a file to analyze." },
    ])) return;
    run("smart_parse", { inputFile: parseFile });
  }

  async function runVariations() {
    if (!validate([
      { cond: !!folder,                    msg: "Please select a working folder first." },
      { cond: !!varFile,                   msg: "Please select a source file." },
      { cond: !!varOutput,                 msg: "Please specify an output file name." },
      { cond: !!varApiKey || varKeyStored, msg: "Please enter your Anthropic API key or save one to keychain." },
    ])) return;

    // Load key from keychain if field is empty
    let apiKey = varApiKey.trim();
    if (!apiKey && varKeyStored) {
      try {
        apiKey = await invoke<string>("get_api_key");
      } catch {
        appendLog("❌ Could not retrieve API key from keychain."); return;
      }
    }

    run("generate_variations", {
      inputFile:  varFile,
      outputFile: varOutput,
      apiKey,
      count:      varCount,
      maxSource:  varMaxSource,
      style:      varStyle,
      delay:      varDelay,
    });
  }

  async function runScraper() {
    if (!validate([
      { cond: !!folder,    msg: "Please select a working folder first." },
      { cond: !!scrapeUrl, msg: "Please enter a dataset URL or HuggingFace ID." },
    ])) return;
    run("scrape_dataset", {
      url: scrapeUrl, hfToken: scrapeToken,
      split: scrapeSplit, maxRows: scrapeMaxRows, retries: scrapeRetries,
    });
  }

  async function exportLog() {
    try {
      const path = await save({ defaultPath: "oxygen_log.txt" });
      if (path) {
        const res = await invoke("save_log_file", { path, content: log });
        appendLog(`✅ ${res}`);
      }
    } catch (e) {
      appendLog(`❌ Failed to save log: ${e}`);
    }
  }
</script>

<main>
  <!-- ABOUT MODAL -->
  {#if showAbout}
    <div 
      class="modal-bg" 
      onclick={() => showAbout = false} 
      onkeydown={(e) => e.key === 'Escape' && (showAbout = false)}
      role="button"
      tabindex="0"
      aria-label="Close about dialog"
    >
      <div class="modal">
        <div class="modal-logo">🐂</div>
        <h2>Oxygen</h2>
        <p class="modal-version">v{APP_VERSION} — ML Dataset Manager</p>
        <div class="modal-info">
          <div>🛠 Tauri + Svelte 5 + Python</div>
          <div>📋 GPL v3.0 License</div>
        </div>
        <button class="modal-close" onclick={() => showAbout = false}>✕ Close</button>
      </div>
    </div>
  {/if}

  <header>
    <div class="header-left">
      <span class="logo">🐂</span>
      <div class="header-text">
         <h1>Oxygen</h1>
         <span class="sub">ML Dataset Manager</span>
      </div>
    </div>
    <div class="header-right">
       <span class="version-badge">v{APP_VERSION}</span>
       <button class="btn-about" onclick={() => showAbout = true}>ℹ️ Info</button>
    </div>
  </header>

  <section class="folder-bar card-glass">
    <div class="input-wrapper">
      <span class="input-icon">📁</span>
      <input type="text" placeholder="Select working folder..." bind:value={folder} />
    </div>
    <div class="folder-actions">
      <button class="btn-primary" onclick={pickFolder} disabled={running}>📂 Folder</button>
      <button class="btn-outline" onclick={checkEnv} disabled={running || !folder}>🛡️ Check Env</button>
    </div>
  </section>

  <nav class="tabs-nav card-glass">
    {#each [
      { id: "dash",    label: "📊 Dash"    },
      { id: "scrape",  label: "🌐 Scrape"  },
      { id: "parse",   label: "🧠 Analyze" },
      { id: "filter",  label: "🔍 Filter"  },
      { id: "score",   label: "⭐ Score"   },
      { id: "lang",    label: "🌍 Lang"    },
      { id: "convert", label: "🔄 Conv"    },
      { id: "merge",   label: "🔗 Merge"   },
      { id: "split",   label: "✂️ Split"   },
      { id: "augment", label: "🤖 Aug"     },
    ] as tab}
      <button class="tab-btn {activeTab === tab.id ? 'active' : ''}" onclick={() => setTab(tab.id)}>{tab.label}</button>
    {/each}
  </nav>

  <section class="content">

    <!-- DASHBOARD -->
    {#if activeTab === "dash"}
      <div class="card-glass content-card">
        <div class="card-header">
           <div style="display:flex; align-items:center; gap:10px;">
             <span style="font-size:24px;">📊</span>
             <div>
               <h2 style="margin:0">Repository Insights</h2>
               <p class="card-sub" style="margin:0">Workspace statistics and file overview</p>
             </div>
           </div>
           <button class="btn-square" style="background:rgba(255,255,255,0.1); border:1px solid rgba(255,255,255,0.2);" onclick={loadDashboard} disabled={dashLoading || !folder} title="Refresh Statistics">
              {dashLoading ? "⏳" : "🔄"}
           </button>
        </div>

        {#if dashData}
           <div class="stat-grid">
              <div class="stat-box blue">
                <span class="stat-icon">📄</span>
                <span class="stat-val">{dashData.total_files}</span>
                <span class="stat-lbl">Source Files</span>
              </div>
              <div class="stat-box green">
                <span class="stat-icon">🗂️</span>
                <span class="stat-val">{dashData.total_records.toLocaleString()}</span>
                <span class="stat-lbl">Total Samples</span>
              </div>
              <div class="stat-box purple">
                <span class="stat-icon">💾</span>
                <span class="stat-val">{dashData.total_size_mb.toFixed(1)} MB</span>
                <span class="stat-lbl">Storage Use</span>
              </div>
           </div>
           
           {#if dashData.files && dashData.files.length > 0}
             <div class="file-list-container card-glass-dark">
                <h4 class="list-title">🗄️ RECENT FILES</h4>
                <div class="file-table">
                  {#each dashData.files.slice(0, 8) as f}
                    <div class="file-item-row">
                       <span class="file-name">📄 {f.name}</span>
                       <span class="file-size">{f.size_mb.toFixed(2)} MB</span>
                    </div>
                  {/each}
                </div>
             </div>
           {/if}
        {:else if dashLoading}
           <div class="loading-full">
              <div class="spinner"></div>
              <p>Analyzing repository structure...</p>
           </div>
        {:else}
           <div class="welcome-hero">
              <div class="hero-icon">🐂</div>
              <h3>Ready to analyze?</h3>
              <p>Pick a working folder above to unlock repository insights and start engineering your dataset.</p>
              <button class="btn-primary" style="margin-top:20px;" onclick={pickFolder}>📂 Select Folder</button>
           </div>
        {/if}
      </div>
    {/if}

    <!-- SCRAPER -->
    {#if activeTab === "scrape"}
      <div class="card-glass content-card">
        <div class="card-header">
           <h2>🌐 Cloud Dataset Hub</h2>
           <p class="card-sub">Import from HuggingFace, URLs, or local repositories.</p>
        </div>
        <div class="form-grid">
           <div class="form-row">
              <span class="row-label">📡 Dataset ID / URL</span>
              <input type="text" class="form-input" placeholder="e.g. opensat/blender-python" bind:value={scrapeUrl} />
           </div>
           <div class="form-row">
              <span class="row-label">🔑 HF Token (Optional)</span>
              <input type="password" class="form-input" placeholder="hf_..." bind:value={scrapeToken} />
           </div>
           <div class="quality-grid" style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
              <div class="input-col"><span>Split (train/test)</span><input type="text" bind:value={scrapeSplit} /></div>
              <div class="input-col"><span>Max Rows (0=all)</span><input type="number" bind:value={scrapeMaxRows} /></div>
           </div>
        </div>
        <button class="btn-action" onclick={runScraper} disabled={running || !scrapeUrl}>
           🚀 Start Fetching
        </button>
      </div>
    {/if}

    <!-- ANALYZE -->
    {#if activeTab === "parse"}
      <div class="card-glass content-card">
        <div class="card-header">
          <h2>🧠 Smart Parse & Schema</h2>
          <p class="card-sub">Automatically detect fields and data structures.</p>
        </div>
        <div class="form-grid">
          <div class="form-row">
            <span class="row-label">📄 Source JSON</span>
            <div class="file-pick-group">
              <input type="text" class="form-input" placeholder="Select file to analyze..." bind:value={parseFile} />
              <button class="btn-square" onclick={() => pickFile(v => parseFile = v)}>📂</button>
            </div>
          </div>
        </div>
        <button class="btn-action" onclick={runSmartParse} disabled={running || !parseFile}>
          🧠 Run Analysis
        </button>
      </div>
    {/if}

    <!-- SCORE -->
    {#if activeTab === "score"}
      <div class="card-glass content-card">
        <div class="card-header">
          <h2>⭐ Dataset Quality Scoring</h2>
          <p class="card-sub">Evaluate records and filter by quality score (1-10)</p>
        </div>
        <div class="form-grid">
          <div class="form-row">
            <span class="row-label">📄 Input File</span>
            <div class="file-pick-group">
              <input type="text" class="form-input" placeholder="Select input file..." bind:value={scoreFile} />
              <button class="btn-square" onclick={() => pickFile(v => scoreFile = v)}>📂</button>
            </div>
          </div>
          <div class="form-row">
            <span class="row-label">💾 Output File</span>
            <div class="file-pick-group">
              <input type="text" class="form-input" bind:value={scoreOutput} placeholder="scored_output.json" />
              <button class="btn-square" onclick={() => pickOutputFile(scoreOutput, v => scoreOutput = v)}>💾</button>
            </div>
          </div>
          <div class="form-row">
            <span class="row-label">📈 Min Score</span>
            <div class="slider-group">
              <input type="range" class="glass-slider" min="0" max="10" bind:value={scoreMinScore} />
              <span class="badge" style="background:{scoreColor(scoreMinScore)}">{scoreMinScore}/10</span>
            </div>
          </div>
          <label class="checkbox-row">
            <input type="checkbox" bind:checked={scoreStatsOnly} />
            <span>Statistics only (faster)</span>
          </label>
        </div>
        <button class="btn-action" disabled={running || !scoreFile} onclick={runScore}>
          {running ? "⏳ Processing..." : "⭐ Start Scoring"}
        </button>

        {#if scoreTotal > 0}
          <div class="score-results card-glass-dark">
            <div class="results-summary">
              <div class="res-item"><span>Average</span><strong>{scoreAvg?.toFixed(2)}</strong></div>
              <div class="res-item"><span>Records</span><strong>{scoreTotal}</strong></div>
              <div class="res-item"><span>Saved</span><strong>{scoreFiltered}</strong></div>
            </div>
            <div class="score-bars">
              {#each scoreDist as d}
                <div class="bar-row">
                  <span class="bar-lbl">{d.score}</span>
                  <div class="bar-track"><div class="bar-fill" style="width:{d.pct}%;background:{scoreColor(d.score)}"></div></div>
                  <span class="bar-pct">{d.pct.toFixed(0)}%</span>
                </div>
              {/each}
            </div>
          </div>
        {/if}
      </div>
    {/if}

    <!-- FILTER -->
    {#if activeTab === "filter"}
      <div class="card-glass content-card">
        <div class="card-header">
          <h2>🔍 Advanced Dataset Filter</h2>
        </div>
        <div class="form-grid">
          <div class="form-row">
            <span class="row-label">📄 Source File</span>
            <div class="file-pick-group">
              <input type="text" class="form-input" bind:value={filterFile} placeholder="Select input file..." />
              <button class="btn-square" onclick={() => pickFile(v => filterFile = v)}>📂</button>
            </div>
          </div>
          <div class="form-row">
            <span class="row-label">💾 Output File</span>
            <div class="file-pick-group">
              <input type="text" class="form-input" bind:value={filterOutput} placeholder="filtered_output.json" />
              <button class="btn-square" onclick={() => pickOutputFile(filterOutput, v => filterOutput = v)}>💾</button>
            </div>
          </div>
          <div class="form-row">
            <span class="row-label">🎯 Domain</span>
            <div class="pill-grid">
              {#each DOMAINS as d}
                <button class="pill-btn {filterDomain === d.id ? 'active' : ''}" onclick={() => filterDomain = d.id}>{d.label}</button>
              {/each}
            </div>
          </div>
          <div class="quality-inputs">
             <div class="input-col"><span>Min instr.</span><input type="number" bind:value={filterMinInstr} /></div>
             <div class="input-col"><span>Min output</span><input type="number" bind:value={filterMinOut} /></div>
          </div>
        </div>
        <button class="btn-action" onclick={runFilter} disabled={running}>🔍 Run Filter</button>
      </div>
    {/if}

    <!-- LANG FILTER -->
    {#if activeTab === "lang"}
      <div class="card-glass content-card">
        <div class="card-header">
          <h2>🌍 Language Detection & Filter</h2>
          <p class="card-sub">Identify languages and split datasets by locale</p>
        </div>
        <div class="form-grid">
          <div class="form-row">
            <span class="row-label">📄 Input File</span>
            <div class="file-pick-group">
              <input type="text" class="form-input" bind:value={langFile} placeholder="Select input file..." />
              <button class="btn-square" onclick={() => pickFile(v => langFile = v)}>📂</button>
            </div>
          </div>
          <div class="form-row">
            <span class="row-label">💾 Output File</span>
            <div class="file-pick-group">
              <input type="text" class="form-input" bind:value={langOutput} placeholder="lang_filtered.json" />
              <button class="btn-square" onclick={() => pickOutputFile(langOutput, v => langOutput = v)}>💾</button>
            </div>
          </div>
          <div class="form-row">
            <span class="row-label">🌐 Keep Languages</span>
            <div class="pill-grid">
              {#each ["en", "lv", "ru", "de", "fr", "es", "auto"] as l}
                <button class="pill-btn {langSelected.includes(l) ? 'active' : ''}" 
                  onclick={() => {
                    if (l === 'auto') langSelected = ['auto'];
                    else {
                      langSelected = langSelected.filter(x => x !== 'auto');
                      if (langSelected.includes(l)) langSelected = langSelected.filter(x => x !== l);
                      else langSelected = [...langSelected, l];
                    }
                  }}>{l.toUpperCase()}</button>
              {/each}
            </div>
          </div>
          <div class="quality-inputs">
             <label class="checkbox-row">
               <input type="checkbox" bind:checked={langStatsOnly} />
               <span>Stats only</span>
             </label>
             <label class="checkbox-row">
               <input type="checkbox" bind:checked={langAutoMode} />
               <span>Add _lang field</span>
             </label>
          </div>
        </div>
        <button class="btn-action" onclick={runLangFilter} disabled={running}>🌍 Run Language Filter</button>

        {#if langTotal > 0}
          <div class="score-results card-glass-dark">
            <div class="results-summary">
              <div class="res-item"><span>Total</span><strong>{langTotal}</strong></div>
              <div class="res-item"><span>Saved</span><strong>{langSaved}</strong></div>
            </div>
            <div class="score-bars">
              {#each langStats as s}
                <div class="bar-row">
                  <span class="bar-lbl" style="width:60px">{s.lang}</span>
                  <div class="bar-track"><div class="bar-fill" style="width:{s.pct}%;background:#10b981"></div></div>
                  <span class="bar-pct">{s.pct.toFixed(1)}%</span>
                </div>
              {/each}
            </div>
          </div>
        {/if}
      </div>
    {/if}

    <!-- AUGMENT -->
    {#if activeTab === "augment"}
      <div class="card-glass content-card">
        <div class="card-header">
          <h2>🤖 AI Dataset Augmentation</h2>
          <p class="card-sub">Generate unique variations using Claude AI</p>
        </div>
        <div class="form-grid">
          <div class="form-row">
            <span class="row-label">🔑 Anthropic API Key</span>
            {#if varKeyStored}
              <div class="keychain-status">
                <span class="key-badge">🔐 Key saved in system keychain</span>
                <button class="btn-outline" style="padding: 8px 14px; font-size:13px;" onclick={clearApiKey}>🗑️ Remove</button>
              </div>
              <input type="password" class="form-input" placeholder="Enter new key to replace..." bind:value={varApiKey} style="margin-top:8px;" />
              {#if varApiKey}
                <button class="btn-primary" style="margin-top:6px; padding:9px 16px;" onclick={saveApiKey} disabled={varKeySaving}>
                  {varKeySaving ? "Saving..." : "💾 Update in Keychain"}
                </button>
              {/if}
            {:else}
              <div class="file-pick-group">
                <input type="password" class="form-input" placeholder="sk-ant-... (will be saved to OS keychain)" bind:value={varApiKey} />
                <button class="btn-square" onclick={saveApiKey} disabled={varKeySaving || !varApiKey} title="Save to keychain">
                  {varKeySaving ? "⏳" : "🔐"}
                </button>
              </div>
              <span style="font-size:12px; color:#777; margin-top:4px; display:block;">Key is stored in OS keychain — never written to disk or logs.</span>
            {/if}
          </div>
          <div class="form-row">
            <span class="row-label">📄 Source File</span>
            <div class="file-pick-group">
              <input type="text" class="form-input" bind:value={varFile} placeholder="Select source file..." />
              <button class="btn-square" onclick={() => pickFile(v => varFile = v)}>📂</button>
            </div>
          </div>
          <div class="form-row">
            <span class="row-label">💾 Output File</span>
            <div class="file-pick-group">
              <input type="text" class="form-input" bind:value={varOutput} placeholder="variations_output.json" />
              <button class="btn-square" onclick={() => pickOutputFile(varOutput, v => varOutput = v)}>💾</button>
            </div>
          </div>
          <div class="quality-grid" style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px;">
             <div class="input-col"><span>Count</span><input type="number" bind:value={varCount} min="1" max="10" /></div>
             <div class="input-col"><span>Max Source</span><input type="number" bind:value={varMaxSource} /></div>
             <div class="input-col"><span>Delay (s)</span><input type="number" bind:value={varDelay} step="0.1" /></div>
          </div>
          <div class="form-row">
            <span class="row-label">🎭 Variation Style</span>
            <div class="pill-grid">
              {#each ["mixed", "rephrase", "harder", "simpler", "different"] as s}
                <button class="pill-btn {varStyle === s ? 'active' : ''}" onclick={() => varStyle = s}>{s.toUpperCase()}</button>
              {/each}
            </div>
          </div>
        </div>
        <button class="btn-action" onclick={runVariations} disabled={running || !varApiKey || !varFile}>
          🤖 Start Augmentation
        </button>
      </div>
    {/if}

    <!-- CONVERT -->
    {#if activeTab === "convert"}
      <div class="card-glass content-card">
        <div class="card-header">
          <h2>🔄 Format Conversion</h2>
          <p class="card-sub">Transform files between formats (Parquet, Raw JSON, Alpaca)</p>
        </div>
        <div class="form-grid">
           <div class="stat-box blue" style="flex-direction:row; justify-content:space-between; width:100%; padding:16px;">
              <div style="text-align:left">
                <strong>📦 Bulk Parquet → JSON</strong>
                <p style="font-size:11px;opacity:0.7">Converts all .parquet files in current folder</p>
              </div>
              <button class="btn-primary" onclick={() => run("parquet_to_json")} disabled={running}>Run</button>
           </div>
           
           <div class="card-glass-dark" style="padding:20px; border-radius:12px;">
              <h3 style="margin-bottom:12px; font-size:14px;">🦙 JSON → Alpaca Format</h3>
              <div class="file-pick-group">
                <input type="text" class="form-input" placeholder="Select source JSON..." bind:value={filterFile} />
                <button class="btn-square" onclick={() => pickFile(v => filterFile = v)}>📂</button>
              </div>
              <button class="btn-action" 
                onclick={() => run("convert_to_alpaca", { input_file: filterFile })} 
                disabled={running || !filterFile}>Convert to Alpaca</button>
           </div>
        </div>
      </div>
    {/if}
 
    <!-- SPLIT -->
    {#if activeTab === "split"}
      <div class="card-glass content-card">
        <div class="card-header">
           <div style="display:flex; align-items:center; gap:10px;">
             <span style="font-size:24px;">✂️</span>
             <div>
               <h2 style="margin:0">Large File Splitting</h2>
               <p class="card-sub" style="margin:0">Break down 1GB+ files into manageable chunks</p>
             </div>
           </div>
        </div>
        <div class="form-grid">
           <div class="form-row">
              <span class="row-label">💾 Target Chunk Size</span>
              <div class="slider-group">
                 <input type="range" class="glass-slider" min="1" max="250" bind:value={maxMb} />
                 <span class="badge" style="background:#3b82f6">{maxMb} MB</span>
              </div>
           </div>
           
           <div style="display:grid; grid-template-columns: 1fr 1fr; gap:16px;">
              <div class="card-glass-dark" style="padding:16px; display:flex; flex-direction:column; gap:10px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                  <strong>📄 .json Splitting</strong>
                  <span class="badge" style="background:rgba(255,255,255,0.05); font-size:10px;">Array format</span>
                </div>
                <p style="font-size:11px; opacity:0.6;">Good for single large JSON files.</p>
                <button class="btn-primary" style="height:38px; width:100%;" onclick={() => run("split_json", { max_mb: maxMb })} disabled={running}>Split JSON</button>
              </div>

              <div class="card-glass-dark" style="padding:16px; display:flex; flex-direction:column; gap:10px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                  <strong>📦 .jsonl Splitting</strong>
                  <span class="badge" style="background:rgba(255,255,255,0.05); font-size:10px;">Line format</span>
                </div>
                <p style="font-size:11px; opacity:0.6;">Best for extremely large datasets.</p>
                <button class="btn-primary" style="height:38px; width:100%;" onclick={() => run("split_jsonl", { max_mb: maxMb })} disabled={running}>Split JSONL</button>
              </div>
           </div>
        </div>
      </div>
    {/if}

    <!-- MERGE -->
    {#if activeTab === "merge"}
      <div class="card-glass content-card">
        <h2>🔗 Merge & Deduplicate</h2>
        <p class="card-sub">Combine all JSON files in current folder into <code>alpaca_merged.json</code>.</p>
        <button class="btn-action" onclick={() => run("merge_alpaca")} disabled={running}>🔗 Merge Alpaca Files</button>
      </div>
    {/if}

  </section>

  <section class="log-section card-glass-dark">
    <div class="log-header">
      <div class="log-title">📋 Console Output</div>
      <div class="log-actions">
        <button class="log-tool" onclick={exportLog} title="Save Log">💾</button>
        <button class="log-tool" onclick={clearLog} title="Clear Log">🗑️</button>
      </div>
    </div>
    <pre class="log-area" id="log-view">{log || "Waiting for action..."}</pre>
  </section>
</main>

<style>
  :global(*) { box-sizing: border-box; margin: 0; padding: 0; }
  :global(body) {
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    font-size: 15px;
    background: radial-gradient(ellipse at top, #232323, #181818, #0e0e0e);
    color: #e8e8e8;
    min-height: 100vh;
    overflow-x: hidden;
    line-height: 1.6;
  }

  main { max-width: 1140px; margin: 0 auto; padding: 28px 32px; display: flex; flex-direction: column; gap: 22px; }

  header { display: flex; justify-content: space-between; align-items: center; padding-bottom: 8px; }
  .header-left { display: flex; align-items: center; gap: 18px; }
  .logo { font-size: 34px; filter: drop-shadow(0 0 10px rgba(160, 160, 160, 0.3)); }
  h1 {
    font-size: 28px;
    font-weight: 800;
    background: linear-gradient(to right, #d0d0d0, #a0a0a0);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  .sub { font-size: 12px; color: #707070; text-transform: uppercase; letter-spacing: 2px; }
  .header-right { display: flex; align-items: center; gap: 12px; }
  .version-badge { font-size: 11px; color: #888; background: rgba(255,255,255,0.06); padding: 5px 10px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.08); }
  .btn-about { background: none; border: none; color: #aaa; font-size: 13px; cursor: pointer; text-decoration: underline; }

  .card-glass {
    background: rgba(50, 50, 50, 0.55);
    backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 18px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.4);
  }
  .card-glass-dark {
    background: rgba(28, 28, 28, 0.8);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 18px;
  }

  .folder-bar { display: flex; gap: 12px; padding: 14px; align-items: center; }
  .input-wrapper { flex: 1; position: relative; display: flex; align-items: center; }
  .input-icon { position: absolute; left: 13px; opacity: 0.5; pointer-events: none; }
  .input-wrapper input {
    width: 100%;
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 10px;
    padding: 11px 11px 11px 40px;
    color: #e8e8e8;
    font-size: 14px;
    outline: none;
    transition: all 0.2s;
  }
  .input-wrapper input:focus { border-color: #777; box-shadow: 0 0 0 2px rgba(180, 180, 180, 0.15); }
  .folder-actions { display: flex; gap: 8px; }

  .tabs-nav { display: flex; gap: 4px; padding: 7px; }
  .tab-btn {
    flex: 1;
    padding: 11px 4px;
    border: none;
    background: transparent;
    color: #888;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    border-radius: 10px;
    transition: all 0.2s;
  }
  .tab-btn:hover { background: rgba(255,255,255,0.07); color: #e8e8e8; }
  .tab-btn.active { background: rgba(255,255,255,0.14); color: #fff; border: 1px solid rgba(255,255,255,0.18); box-shadow: 0 2px 10px rgba(0,0,0,0.3); }

  .content-card { padding: 28px; display: flex; flex-direction: column; gap: 22px; min-height: 200px; }
  .card-header h2 { font-size: 20px; color: #f0f0f0; margin-bottom: 4px; }
  .card-sub { font-size: 13px; color: #777; }

  .stat-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; }
  .stat-box {
    padding: 22px;
    border-radius: 14px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    border: 1px solid rgba(255,255,255,0.07);
    transition: transform 0.2s;
  }
  .stat-box:hover { transform: translateY(-4px); }
  .stat-box.blue { background: rgba(100, 140, 200, 0.12); border-color: rgba(120, 160, 220, 0.2); }
  .stat-box.green { background: rgba(80, 180, 130, 0.12); border-color: rgba(80, 180, 130, 0.2); }
  .stat-box.purple { background: rgba(160, 120, 220, 0.12); border-color: rgba(160, 120, 220, 0.2); }
  .stat-val { font-size: 32px; font-weight: 800; }
  .stat-lbl { font-size: 12px; text-transform: uppercase; letter-spacing: 1px; color: #888; }

  .form-grid { display: flex; flex-direction: column; gap: 18px; }
  .form-row { display: flex; flex-direction: column; gap: 9px; }
  .row-label { font-size: 13px; font-weight: 600; color: #999; }
  .file-pick-group { display: flex; gap: 8px; }
  .form-input {
    flex: 1;
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 9px;
    padding: 11px 15px;
    color: #e8e8e8;
    font-size: 14px;
    outline: none;
  }
  .btn-square { background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.12); border-radius: 9px; padding: 11px 18px; cursor: pointer; color: #d0d0d0; font-size: 14px; }

  .slider-group { display: flex; align-items: center; gap: 16px; }
  .glass-slider { flex: 1; accent-color: #aaa; height: 6px; border-radius: 3px; cursor: pointer; }
  .badge { padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 13px; min-width: 50px; text-align: center; }

  .pill-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 9px; }
  .pill-btn {
    padding: 9px;
    border-radius: 10px;
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.1);
    color: #999;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.2s;
  }
  .pill-btn.active { background: rgba(255,255,255,0.14); border-color: rgba(255,255,255,0.3); color: #e8e8e8; box-shadow: 0 0 8px rgba(255, 255, 255, 0.08); }

  .quality-inputs { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .input-col { display: flex; align-items: center; gap: 10px; font-size: 13px; color: #888; }
  .input-col input { width: 80px; background: rgba(255,255,255,0.07); border: 1px solid rgba(255,255,255,0.12); border-radius: 6px; padding: 7px 10px; color: #fff; outline:none; font-size: 14px; }

  button { border: none; outline: none; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); }

  .btn-action {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    width: 100%;
    margin-top: 15px;
    padding: 17px;
    border-radius: 12px;
    font-size: 15px;
    font-weight: 800;
    color: white !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    cursor: pointer;
    background: linear-gradient(135deg, #606060 0%, #404040 100%) !important;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.4) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
  }
  .btn-action:hover:not(:disabled) {
    transform: translateY(-3px);
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.5) !important;
    background: linear-gradient(135deg, #707070 0%, #505050 100%) !important;
  }
  .btn-action:disabled {
    opacity: 0.3;
    cursor: not-allowed;
  }

  .btn-primary { background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.18); border-radius: 10px; padding: 0 20px; cursor: pointer; color: #f0f0f0; font-weight: 600; font-size: 14px; }
  .btn-primary:hover { background: rgba(255,255,255,0.22); }
  .btn-outline { background: transparent; border: 1px solid rgba(255,255,255,0.15); border-radius: 10px; padding: 0 20px; cursor: pointer; color: #ccc; font-weight: 600; font-size: 14px; }
  .btn-outline:hover { background: rgba(255,255,255,0.07); }

  .log-section { display: flex; flex-direction: column; overflow: hidden; }
  .log-header { padding: 13px 22px; background: rgba(0,0,0,0.25); border-bottom: 1px solid rgba(255,255,255,0.06); display: flex; justify-content: space-between; align-items: center; }
  .log-title { font-size: 12px; color: #777; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px; }
  .log-actions { display: flex; gap: 8px; }
  .log-tool { background: none; border: none; color: #777; cursor: pointer; font-size: 15px; }
  .log-area { padding: 22px; font-family: 'JetBrains Mono', 'Fira Code', monospace; font-size: 13px; color: #7ee8b0; white-space: pre-wrap; height: 280px; overflow-y: auto; overflow-x: hidden; line-height: 1.7; }

  .score-results { margin-top: 10px; padding: 20px; }
  .results-summary { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid rgba(255,255,255,0.06); }
  .res-item { display: flex; flex-direction: column; gap: 4px; }
  .res-item span { font-size: 12px; color: #777; text-transform: uppercase; }
  .res-item strong { font-size: 22px; color: #f0f0f0; }

  .bar-row { display: grid; grid-template-columns: 30px 1fr 40px; align-items: center; gap: 12px; margin-bottom: 8px; }
  .bar-lbl { font-size: 12px; color: #999; font-weight: 700; }
  .bar-track { height: 8px; background: rgba(0,0,0,0.4); border-radius: 4px; overflow: hidden; }
  .bar-fill { height: 100%; border-radius: 4px; transition: width 0.6s cubic-bezier(0.34, 1.56, 0.64, 1); }
  .bar-pct { font-size: 12px; color: #777; text-align: right; }

  .modal-bg { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.85); backdrop-filter: blur(10px); display: flex; align-items: center; justify-content: center; z-index: 1000; }
  .modal { background: rgba(40, 40, 40, 0.9); border: 1px solid rgba(255,255,255,0.15); border-radius: 24px; padding: 52px; text-align: center; max-width: 420px; box-shadow: 0 0 50px rgba(0,0,0,0.5); }
  .modal-logo { font-size: 52px; margin-bottom: 18px; }
  .modal-version { color: #777; margin-bottom: 24px; font-size: 14px; }
  .modal-info { display: flex; flex-direction: column; gap: 12px; color: #aaa; font-size: 15px; margin-bottom: 32px; }
  .modal-close { padding: 11px 36px; background: rgba(255,255,255,0.15); color: #fff; border-radius: 12px; border: 1px solid rgba(255,255,255,0.2); cursor: pointer; font-weight: 700; font-size: 14px; }
  .modal-close:hover { background: rgba(255,255,255,0.22); }
  .welcome-hero {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 64px 20px;
    text-align: center;
    color: rgba(255,255,255,0.75);
  }
  .hero-icon {
    font-size: 68px;
    margin-bottom: 22px;
    filter: drop-shadow(0 0 15px rgba(180,180,180,0.2));
    animation: pulse 3s infinite ease-in-out;
  }
  @keyframes pulse {
    0%, 100% { transform: scale(1); opacity: 0.75; }
    50% { transform: scale(1.08); opacity: 1; }
  }
  .welcome-hero h3 { font-size: 26px; margin-bottom: 12px; color: white; }
  .welcome-hero p { max-width: 420px; opacity: 0.55; line-height: 1.6; font-size: 15px; }

  .loading-full {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 64px 0;
    gap: 16px;
    opacity: 0.8;
  }
  .spinner {
    width: 42px;
    height: 42px;
    border: 3px solid rgba(255,255,255,0.1);
    border-top-color: #aaa;
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  .file-list-container {
    margin-top: 24px;
    padding: 20px;
    border-radius: 12px;
  }
  .list-title {
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.06em;
    color: rgba(255,255,255,0.35);
    margin-bottom: 15px;
  }
  .file-table {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .file-item-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 9px;
    transition: all 0.2s;
  }
  .file-item-row:hover {
    background: rgba(255,255,255,0.08);
    transform: translateX(5px);
  }
  .file-name { font-size: 14px; color: rgba(255,255,255,0.88); }
  .file-size { font-size: 13px; font-weight: 600; color: #aaa; }

  .keychain-status { display: flex; align-items: center; gap: 12px; }
  .key-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(80, 180, 130, 0.15);
    border: 1px solid rgba(80, 180, 130, 0.3);
    color: #7ee8b0;
    border-radius: 8px;
    padding: 7px 14px;
    font-size: 13px;
    font-weight: 600;
    flex: 1;
  }
</style>
