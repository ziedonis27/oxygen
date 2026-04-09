<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { open, save } from "@tauri-apps/plugin-dialog";
  import { onMount } from "svelte";
  import { EditorView, basicSetup } from "codemirror";
  import { json } from "@codemirror/lang-json";
  import { oneDark } from "@codemirror/theme-one-dark";
  import { linter, lintGutter, type Diagnostic } from "@codemirror/lint";
  import { EditorState } from "@codemirror/state";

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
  let prevFile          = $state("");
  let prevData: any[]   = $state([]);
  let prevSearch        = $state("");
  let prevPage          = $state(1);
  let prevLimit         = $state(20);
  let prevTotal         = $state(0);
  let prevFilteredTotal = $state(0);
  let prevFields: string[] = $state([]);
  let prevLoading       = $state(false);
  let prevSelectedIds   = $state<string[]>([]);
  let prevExpandedId    = $state<string | null>(null);

  async function loadPreview(resetPage = false) {
    if (!folder || !prevFile) { appendLog("⚠️ Select a working folder and file first."); return; }
    if (resetPage) { prevPage = 1; prevSelectedIds = []; prevExpandedId = null; }
    prevLoading = true;
    try {
      const res = await invoke<string>("preview_dataset", {
        folder,
        inputFile:     prevFile,
        action:        "preview",
        offset:        (prevPage - 1) * prevLimit,
        limit:         prevLimit,
        search:        prevSearch,
        deleteIndices: "",
      });
      const d = JSON.parse(res);
      prevData          = d.records ?? [];
      prevTotal         = d.total ?? 0;
      prevFilteredTotal = d.filtered_total ?? 0;
      prevFields        = ((d.fields ?? []) as string[]).filter((f: string) => !f.startsWith("_")).slice(0, 4);
    } catch (e) { appendLog(`❌ Preview error: ${e}`); }
    prevLoading = false;
  }

  async function prevDeleteSingle(index: number) {
    try {
      const res = await invoke<string>("preview_dataset", {
        folder, inputFile: prevFile, action: "delete",
        offset: 0, limit: prevLimit, search: "",
        deleteIndices: String(index),
      });
      const d = JSON.parse(res);
      appendLog(`🗑️ Record #${index} deleted. Remaining: ${d.remaining}`);
      prevSelectedIds = prevSelectedIds.filter(id => id !== String(index));
      loadPreview();
    } catch (e) { appendLog(`❌ Delete error: ${e}`); }
  }

  async function prevDeleteSelected() {
    if (!prevSelectedIds.length) return;
    try {
      const res = await invoke<string>("preview_dataset", {
        folder, inputFile: prevFile, action: "delete",
        offset: 0, limit: prevLimit, search: "",
        deleteIndices: prevSelectedIds.join(","),
      });
      const d = JSON.parse(res);
      appendLog(`🗑️ Deleted ${d.deleted} records. Remaining: ${d.remaining}`);
      prevSelectedIds = [];
      loadPreview(true);
    } catch (e) { appendLog(`❌ Delete error: ${e}`); }
  }

  function prevToggleSelect(id: string) {
    if (prevSelectedIds.includes(id)) prevSelectedIds = prevSelectedIds.filter(x => x !== id);
    else prevSelectedIds = [...prevSelectedIds, id];
  }

  function prevToggleAll() {
    const ids = prevData.map(r => String(r._index));
    if (ids.every(id => prevSelectedIds.includes(id))) prevSelectedIds = prevSelectedIds.filter(id => !ids.includes(id));
    else prevSelectedIds = [...new Set([...prevSelectedIds, ...ids])];
  }

  function prevTotalPages() { return Math.max(1, Math.ceil(prevFilteredTotal / prevLimit)); }

  function truncate(val: any, len = 80): string {
    const s = typeof val === "object" ? JSON.stringify(val) : String(val ?? "");
    return s.length > len ? s.slice(0, len) + "…" : s;
  }

  function openInEditor(rec: any) {
    const content = JSON.stringify(rec, null, 2);
    editorContent = content;
    activeTab = "editor";
  }

  // --- JSON Editor state ---
  let editorFile   = $state("");
  let editorSaving = $state(false);
  let editorDirty  = $state(false);
  let editorValid  = $state<boolean | null>(null);
  let editorErrors = $state<{ line: number; col: number; msg: string }[]>([]);
  let editorRecordCount = $state<number | null>(null);
  let editorContent = $state("");      // persists content across tab switches
  let editorViewRef: EditorView | null = null;

  function buildEditorExtensions() {
    const jsonLinter = linter((view): Diagnostic[] => {
      const doc = view.state.doc.toString();
      if (!doc.trim()) { editorValid = null; editorErrors = []; editorRecordCount = null; return []; }
      try {
        const parsed = JSON.parse(doc);
        editorValid = true;
        editorErrors = [];
        editorRecordCount = Array.isArray(parsed) ? parsed.length : null;
        return [];
      } catch (e: any) {
        editorValid = false;
        const msg: string = e.message ?? "Invalid JSON";
        const posMatch = msg.match(/position (\d+)/);
        if (posMatch) {
          const pos = Math.min(parseInt(posMatch[1]), doc.length - 1);
          const line = view.state.doc.lineAt(pos);
          editorErrors = [{ line: line.number, col: pos - line.from + 1, msg }];
          return [{ from: line.from, to: line.to, severity: "error", message: msg }];
        }
        editorErrors = [{ line: 1, col: 1, msg }];
        return [{ from: 0, to: Math.min(doc.length, 1), severity: "error", message: msg }];
      }
    });

    return [
      basicSetup,
      json(),
      oneDark,
      jsonLinter,
      lintGutter(),
      EditorView.updateListener.of((update) => {
        if (update.docChanged) {
          editorContent = update.state.doc.toString();
          editorDirty = true;
        }
      }),
      EditorView.theme({
        "&": { height: "420px", borderRadius: "12px", overflow: "hidden" },
        ".cm-scroller": { fontFamily: "'JetBrains Mono','Fira Code',monospace", fontSize: "13px", lineHeight: "1.7" },
        ".cm-focused": { outline: "none" },
        "&.cm-editor": { background: "rgba(18,18,22,0.95)" },
      }),
    ];
  }

  function initEditorAction(node: HTMLElement) {
    editorViewRef = new EditorView({
      state: EditorState.create({
        doc: editorContent,
        extensions: buildEditorExtensions(),
      }),
      parent: node,
    });
    return {
      destroy() {
        editorViewRef?.destroy();
        editorViewRef = null;
      },
    };
  }

  async function editorLoadFile() {
    const selected = await open({ multiple: false, filters: [{ name: "JSON/JSONL", extensions: ["json", "jsonl"] }] });
    if (typeof selected !== "string") return;
    try {
      const text = await invoke<string>("read_text_file", { path: selected });
      editorFile = selected;
      editorContent = text;
      editorDirty = false;
      if (editorViewRef) {
        editorViewRef.dispatch({
          changes: { from: 0, to: editorViewRef.state.doc.length, insert: text },
        });
      }
    } catch (e) { appendLog(`❌ Editor load error: ${e}`); }
  }

  async function editorSaveFile() {
    const content = editorViewRef ? editorViewRef.state.doc.toString() : editorContent;
    const defaultPath = editorFile || "edited.json";
    const outPath = await save({ defaultPath, filters: [{ name: "JSON", extensions: ["json", "jsonl"] }] });
    if (!outPath) return;
    editorSaving = true;
    try {
      await invoke("save_log_file", { path: outPath, content });
      editorFile = outPath;
      editorDirty = false;
      appendLog(`✅ Editor: saved to ${outPath}`);
    } catch (e) { appendLog(`❌ Editor save error: ${e}`); }
    editorSaving = false;
  }

  function editorPrettify() {
    const view = editorViewRef;
    if (!view) return;
    const doc = view.state.doc.toString();
    try {
      const pretty = JSON.stringify(JSON.parse(doc), null, 2);
      view.dispatch({ changes: { from: 0, to: doc.length, insert: pretty } });
    } catch { appendLog("⚠️ Cannot prettify — JSON has errors."); }
  }

  function editorMinify() {
    const view = editorViewRef;
    if (!view) return;
    const doc = view.state.doc.toString();
    try {
      const min = JSON.stringify(JSON.parse(doc));
      view.dispatch({ changes: { from: 0, to: doc.length, insert: min } });
    } catch { appendLog("⚠️ Cannot minify — JSON has errors."); }
  }

  function editorClear() {
    if (!editorViewRef) return;
    const len = editorViewRef.state.doc.length;
    editorViewRef.dispatch({ changes: { from: 0, to: len, insert: "" } });
    editorFile = "";
    editorDirty = false;
    editorValid = null;
    editorErrors = [];
    editorRecordCount = null;
  }

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

  // ===== PIPELINE / QUEUE =====
  function appendQueueLog(text: string) { queueLog += text + "\n"; }

  function addQueueStep(type: QueueStepType) {
    const def = STEP_DEFAULTS[type];
    queueSteps = [...queueSteps, {
      id: Math.random().toString(36).slice(2),
      type,
      label: def.label,
      icon:  def.icon,
      status: "pending",
      config: { ...def.config },
    }];
    showAddStep = false;
  }

  function removeQueueStep(i: number) {
    queueSteps = queueSteps.filter((_, idx) => idx !== i);
  }

  function moveQueueStep(i: number, dir: -1 | 1) {
    const j = i + dir;
    if (j < 0 || j >= queueSteps.length) return;
    const arr = [...queueSteps];
    [arr[i], arr[j]] = [arr[j], arr[i]];
    queueSteps = arr;
  }

  function clearQueue() { queueSteps = []; queueLog = ""; }

  function loadQueuePreset(preset: { name: string; icon: string; steps: string[] }) {
    queueSteps = preset.steps.map(type => {
      const def = STEP_DEFAULTS[type as QueueStepType];
      return {
        id: Math.random().toString(36).slice(2),
        type: type as QueueStepType,
        label: def.label,
        icon:  def.icon,
        status: "pending" as QueueStatus,
        config: { ...def.config },
      };
    });
    queueLog = "";
  }

  function resetQueueStatuses() {
    queueSteps = queueSteps.map(s => ({ ...s, status: "pending" as QueueStatus, duration: undefined }));
  }

  async function runQueueStep(step: QueueStep): Promise<string> {
    switch (step.type) {
      case "scrape":
        return invoke("scrape_dataset", {
          folder,
          url: step.config.url || scrapeUrl,
          hfToken: scrapeToken,
          split: step.config.split || scrapeSplit,
          maxRows: scrapeMaxRows,
          retries: scrapeRetries,
        });
      case "parse":
        return invoke("smart_parse", { folder, inputFile: step.config.inputFile || parseFile });
      case "filter":
        return invoke("filter_dataset", {
          folder,
          inputFile:    filterFile,
          outputFile:   filterOutput,
          domain:       step.config.domain || filterDomain,
          minOutput:    filterMinOut,
          minInstr:     filterMinInstr,
          maxRecords:   filterMaxRec,
          removeDupes:  filterDupes,
          requireCode:  filterCode,
          format:       filterFormat,
          includeWords: filterInclude,
          excludeWords: filterExclude,
        });
      case "convert":
        return invoke("parquet_to_json", { folder });
      case "merge":
        return invoke("merge_alpaca", { folder });
      case "split": {
        const mb   = step.config.maxMb ?? maxMb;
        const type = step.config.type  ?? "json";
        return invoke(type === "jsonl" ? "split_jsonl" : "split_json", { folder, max_mb: mb });
      }
      case "augment": {
        let apiKey = varApiKey.trim();
        if (!apiKey && varKeyStored) {
          try { apiKey = await invoke<string>("get_api_key"); } catch { throw new Error("Cannot retrieve API key from keychain."); }
        }
        if (!apiKey) throw new Error("No Anthropic API key set. Configure it in the Aug tab first.");
        return invoke("generate_variations", {
          folder,
          inputFile:  step.config.inputFile || varFile,
          outputFile: varOutput,
          apiKey,
          count:      step.config.count ?? varCount,
          maxSource:  varMaxSource,
          style:      step.config.style  || varStyle,
          delay:      varDelay,
        });
      }
      default:
        throw new Error(`Unknown step type: ${(step as any).type}`);
    }
  }

  async function runQueue() {
    if (!queueSteps.length) { appendQueueLog("⚠️ Add steps first."); return; }
    if (!folder)            { appendQueueLog("⚠️ Select working folder first."); return; }
    queueRunning = true;
    queueLog = "";
    resetQueueStatuses();
    appendQueueLog(`🚀 Pipeline started — ${queueSteps.length} step(s)\n${"─".repeat(40)}`);
    const t0Total = performance.now();

    for (let i = 0; i < queueSteps.length; i++) {
      const step = queueSteps[i];
      queueSteps[i] = { ...step, status: "running" };
      const t0 = performance.now();
      appendQueueLog(`\n[${i + 1}/${queueSteps.length}] ${step.icon} ${step.label}`);
      try {
        const res = await runQueueStep(queueSteps[i]);
        const dur = ((performance.now() - t0) / 1000).toFixed(1);
        queueSteps[i] = { ...queueSteps[i], status: "done", duration: parseFloat(dur) };
        appendQueueLog(`  ✅ Done  (${dur}s)`);
        const preview = String(res ?? "").trim().slice(0, 180);
        if (preview) appendQueueLog(`  ${preview}`);
      } catch (e) {
        const dur = ((performance.now() - t0) / 1000).toFixed(1);
        queueSteps[i] = { ...queueSteps[i], status: "error", duration: parseFloat(dur) };
        appendQueueLog(`  ❌ Error: ${e}`);
        // Mark remaining steps as skipped
        for (let j = i + 1; j < queueSteps.length; j++) queueSteps[j] = { ...queueSteps[j], status: "skipped" };
        appendQueueLog(`\n⏹ Pipeline stopped at step ${i + 1}.`);
        queueRunning = false;
        return;
      }
    }

    const total = ((performance.now() - t0Total) / 1000).toFixed(1);
    appendQueueLog(`\n${"─".repeat(40)}\n🏁 Pipeline complete in ${total}s`);
    queueRunning = false;
    loadDashboard();
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
      { id: "queue",   label: "⚙️ Queue"  },
      { id: "preview", label: "👁 Preview"  },
      { id: "editor",  label: "✏️ Edit"    },
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

    <!-- PIPELINE / QUEUE -->
    {#if activeTab === "queue"}
      <div class="card-glass content-card">
        <div class="card-header">
          <div style="display:flex; align-items:center; gap:10px;">
            <span style="font-size:24px;">⚙️</span>
            <div>
              <h2 style="margin:0">Pipeline Builder</h2>
              <p class="card-sub" style="margin:0">Chain operations into automated workflows that run sequentially</p>
            </div>
          </div>
          <div style="display:flex; gap:8px; align-items:center;">
            {#if queueSteps.length > 0}
              <span class="ed-badge info">{queueSteps.length} step{queueSteps.length !== 1 ? 's' : ''}</span>
              {#if queueSteps.filter(s => s.status === 'done').length > 0}
                <span class="ed-badge valid">{queueSteps.filter(s => s.status === 'done').length} done</span>
              {/if}
            {/if}
          </div>
        </div>

        <!-- Presets -->
        <div class="queue-presets">
          <span class="queue-section-label">Quick presets:</span>
          {#each QUEUE_PRESETS as preset}
            <button class="preset-btn" onclick={() => loadQueuePreset(preset)} disabled={queueRunning}>
              {preset.icon} {preset.name}
            </button>
          {/each}
        </div>

        <!-- Step list -->
        {#if queueSteps.length > 0}
          <div class="queue-step-list">
            {#each queueSteps as step, i}
              <div class="queue-step-row q-{step.status}">
                <div class="q-step-indicator">
                  {#if step.status === 'pending'}  <span class="q-dot pending">○</span>
                  {:else if step.status === 'running'} <span class="q-dot running">⏳</span>
                  {:else if step.status === 'done'}    <span class="q-dot done">✓</span>
                  {:else if step.status === 'error'}   <span class="q-dot error">✗</span>
                  {:else}                              <span class="q-dot skipped">–</span>
                  {/if}
                </div>
                <div class="q-step-num">{i + 1}</div>
                <span class="q-step-icon">{step.icon}</span>
                <span class="q-step-label">{step.label}</span>
                {#if step.type === 'scrape'}
                  <input type="text" class="q-inline-input" placeholder="Dataset URL / HF ID" bind:value={step.config.url} disabled={queueRunning} />
                {:else if step.type === 'filter'}
                  <select class="q-inline-sel" bind:value={step.config.domain} disabled={queueRunning}>
                    {#each DOMAINS as d}<option value={d.id}>{d.label}</option>{/each}
                  </select>
                {:else if step.type === 'split'}
                  <span class="q-inline-label">{step.config.maxMb ?? maxMb} MB</span>
                {:else if step.type === 'augment'}
                  <span class="q-inline-label">×{step.config.count ?? varCount} {step.config.style ?? varStyle}</span>
                {/if}
                {#if step.duration != null}
                  <span class="q-step-dur">{step.duration}s</span>
                {/if}
                <div class="q-step-btns">
                  <button class="q-btn" onclick={() => moveQueueStep(i, -1)} disabled={i === 0 || queueRunning} title="Move up">↑</button>
                  <button class="q-btn" onclick={() => moveQueueStep(i, 1)} disabled={i === queueSteps.length - 1 || queueRunning} title="Move down">↓</button>
                  <button class="q-btn danger" onclick={() => removeQueueStep(i)} disabled={queueRunning} title="Remove">✕</button>
                </div>
              </div>
              {#if i < queueSteps.length - 1}
                <div class="q-connector">│</div>
              {/if}
            {/each}
          </div>
        {:else}
          <div class="queue-empty-state">
            <span style="font-size:36px; opacity:0.3;">⚙️</span>
            <p>No steps yet. Use a preset above or add steps manually.</p>
          </div>
        {/if}

        <!-- Add step picker -->
        <div class="queue-add-section">
          <button class="ed-tool-btn" onclick={() => showAddStep = !showAddStep} disabled={queueRunning}>
            {showAddStep ? '✕ Cancel' : '＋ Add Step'}
          </button>
          {#if showAddStep}
            <div class="step-type-grid">
              {#each Object.entries(STEP_DEFAULTS) as [type, def]}
                <button class="step-type-btn" onclick={() => addQueueStep(type as QueueStepType)}>
                  <span class="step-type-icon">{def.icon}</span>
                  <span class="step-type-label">{def.label}</span>
                </button>
              {/each}
            </div>
          {/if}
        </div>

        <!-- Run bar -->
        <div class="queue-run-bar">
          <button class="btn-action" style="flex:1;" onclick={runQueue} disabled={queueRunning || !queueSteps.length || !folder}>
            {queueRunning ? '⏳ Running pipeline...' : '▶ Run Pipeline'}
          </button>
          <button class="btn-outline" style="padding:17px 22px;" onclick={clearQueue} disabled={queueRunning}>🗑 Clear</button>
        </div>

        <!-- Queue log -->
        {#if queueLog}
          <div class="queue-log-wrap card-glass-dark">
            <div class="log-header" style="padding:10px 18px;">
              <span class="log-title">Pipeline Log</span>
            </div>
            <pre class="log-area" style="height:200px; color:#90cdf4;">{queueLog}</pre>
          </div>
        {/if}
      </div>
    {/if}

    <!-- PREVIEW -->
    {#if activeTab === "preview"}
      <div class="card-glass content-card">
        <div class="card-header">
          <div style="display:flex; align-items:center; gap:10px;">
            <span style="font-size:24px;">👁</span>
            <div>
              <h2 style="margin:0">Dataset Browser</h2>
              <p class="card-sub" style="margin:0">Browse, search, and delete records from any JSON/JSONL file</p>
            </div>
          </div>
          {#if prevTotal > 0}
            <div style="display:flex; flex-direction:column; align-items:flex-end; gap:4px;">
              <span class="ed-badge info">{prevTotal.toLocaleString()} total</span>
              {#if prevSearch && prevFilteredTotal !== prevTotal}
                <span class="ed-badge neutral">{prevFilteredTotal.toLocaleString()} matched</span>
              {/if}
            </div>
          {/if}
        </div>

        <!-- Controls bar -->
        <div class="prev-controls">
          <div class="file-pick-group" style="flex:1;">
            <input type="text" class="form-input" placeholder="Select dataset file..." bind:value={prevFile} />
            <button class="btn-square" onclick={() => pickFile(v => { prevFile = v; loadPreview(true); })}>📂</button>
          </div>
          <input
            type="text"
            class="form-input prev-search"
            placeholder="🔍 Search records..."
            bind:value={prevSearch}
            onkeydown={(e) => e.key === "Enter" && loadPreview(true)}
          />
          <select class="prev-limit-sel" bind:value={prevLimit} onchange={() => loadPreview(true)}>
            {#each [10, 20, 50, 100] as n}
              <option value={n}>{n} / page</option>
            {/each}
          </select>
          <button class="btn-primary" style="padding:11px 18px; white-space:nowrap;" onclick={() => loadPreview(true)} disabled={prevLoading || !prevFile}>
            {prevLoading ? "⏳" : "🔄"} Load
          </button>
        </div>

        <!-- Bulk action bar -->
        {#if prevData.length > 0}
          <div class="prev-bulk-bar">
            <label class="checkbox-row" style="margin:0;">
              <input type="checkbox"
                checked={prevData.every(r => prevSelectedIds.includes(String(r._index)))}
                onchange={prevToggleAll}
              />
              <span>Select page</span>
            </label>
            {#if prevSelectedIds.length > 0}
              <span class="ed-badge dirty">{prevSelectedIds.length} selected</span>
              <button class="ed-tool-btn danger" onclick={prevDeleteSelected}>🗑️ Delete selected</button>
            {/if}
            <span style="margin-left:auto; font-size:12px; color:#666;">
              Rows {((prevPage-1)*prevLimit)+1}–{Math.min(prevPage*prevLimit, prevFilteredTotal)} of {prevFilteredTotal.toLocaleString()}
            </span>
          </div>
        {/if}

        <!-- Table -->
        {#if prevLoading}
          <div class="loading-full" style="padding:40px 0;">
            <div class="spinner"></div>
            <p>Loading records...</p>
          </div>
        {:else if prevData.length > 0}
          <div class="prev-table-wrap card-glass-dark">
            <table class="prev-table">
              <thead>
                <tr>
                  <th class="col-check"></th>
                  <th class="col-idx">#</th>
                  {#each prevFields as f}
                    <th>{f}</th>
                  {/each}
                  <th class="col-actions"></th>
                </tr>
              </thead>
              <tbody>
                {#each prevData as rec}
                  {@const id = String(rec._index)}
                  {@const isSelected = prevSelectedIds.includes(id)}
                  {@const isExpanded = prevExpandedId === id}
                  <tr
                    class="prev-row {isSelected ? 'selected' : ''} {isExpanded ? 'expanded' : ''}"
                    onclick={(e) => { if ((e.target as HTMLElement).closest('.no-expand')) return; prevExpandedId = isExpanded ? null : id; }}
                  >
                    <td class="col-check no-expand" onclick={(e) => e.stopPropagation()}>
                      <input type="checkbox" checked={isSelected} onchange={() => prevToggleSelect(id)} />
                    </td>
                    <td class="col-idx">{rec._index}</td>
                    {#each prevFields as f}
                      <td class="cell-value" title={String(rec[f] ?? "")}>{truncate(rec[f])}</td>
                    {/each}
                    <td class="col-actions no-expand">
                      <div class="row-actions">
                        <button class="row-btn" title="Open in Editor" onclick={(e) => { e.stopPropagation(); openInEditor(rec); }}>✏️</button>
                        <button class="row-btn danger" title="Delete record" onclick={(e) => { e.stopPropagation(); prevDeleteSingle(rec._index); }}>🗑️</button>
                      </div>
                    </td>
                  </tr>
                  {#if isExpanded}
                    <tr class="expanded-row">
                      <td colspan={prevFields.length + 3}>
                        <pre class="record-json">{JSON.stringify(Object.fromEntries(Object.entries(rec).filter(([k]) => k !== '_index')), null, 2)}</pre>
                      </td>
                    </tr>
                  {/if}
                {/each}
              </tbody>
            </table>
          </div>

          <!-- Pagination -->
          <div class="prev-pagination">
            <button class="ed-tool-btn" onclick={() => { prevPage = 1; loadPreview(); }} disabled={prevPage <= 1}>«</button>
            <button class="ed-tool-btn" onclick={() => { prevPage--; loadPreview(); }} disabled={prevPage <= 1}>‹ Prev</button>
            <span class="page-indicator">Page {prevPage} of {prevTotalPages()}</span>
            <button class="ed-tool-btn" onclick={() => { prevPage++; loadPreview(); }} disabled={prevPage >= prevTotalPages()}>Next ›</button>
            <button class="ed-tool-btn" onclick={() => { prevPage = prevTotalPages(); loadPreview(); }} disabled={prevPage >= prevTotalPages()}>»</button>
          </div>
        {:else if prevFile}
          <div class="welcome-hero" style="padding:48px 20px;">
            <div style="font-size:48px; margin-bottom:16px;">📭</div>
            <h3>No records found</h3>
            <p>{prevSearch ? "Try a different search term." : "File may be empty or in an unsupported format."}</p>
          </div>
        {:else}
          <div class="welcome-hero" style="padding:48px 20px;">
            <div style="font-size:48px; margin-bottom:16px;">📋</div>
            <h3>Select a file to browse</h3>
            <p>Pick any JSON or JSONL dataset file above to start exploring its records.</p>
          </div>
        {/if}
      </div>
    {/if}

    <!-- JSON EDITOR -->
    {#if activeTab === "editor"}
      <div class="card-glass content-card editor-card">
        <div class="card-header">
          <div style="display:flex; align-items:center; gap:10px;">
            <span style="font-size:24px;">✏️</span>
            <div>
              <h2 style="margin:0">JSON Editor</h2>
              <p class="card-sub" style="margin:0">Edit, lint and validate JSON files with real-time feedback</p>
            </div>
          </div>
          <div class="editor-status-badge">
            {#if editorValid === true}
              <span class="ed-badge valid">✓ Valid JSON</span>
              {#if editorRecordCount !== null}
                <span class="ed-badge info">{editorRecordCount.toLocaleString()} records</span>
              {/if}
            {:else if editorValid === false}
              <span class="ed-badge error">✗ Invalid JSON</span>
            {:else}
              <span class="ed-badge neutral">— No file</span>
            {/if}
            {#if editorDirty}
              <span class="ed-badge dirty">● Unsaved</span>
            {/if}
          </div>
        </div>

        <!-- Toolbar -->
        <div class="editor-toolbar">
          <div class="editor-file-path">
            {#if editorFile}
              <span class="file-path-text" title={editorFile}>📄 {editorFile.split(/[\/\\]/).pop()}</span>
            {:else}
              <span class="file-path-empty">No file loaded</span>
            {/if}
          </div>
          <div class="editor-tools">
            <button class="ed-tool-btn" onclick={editorLoadFile} title="Open file">📂 Open</button>
            <button class="ed-tool-btn" onclick={editorSaveFile} disabled={editorSaving} title="Save file">
              {editorSaving ? "⏳" : "💾"} Save
            </button>
            <div class="ed-divider"></div>
            <button class="ed-tool-btn" onclick={editorPrettify} title="Format JSON (Shift+Alt+F)">⚡ Format</button>
            <button class="ed-tool-btn" onclick={editorMinify} title="Minify JSON">📦 Minify</button>
            <div class="ed-divider"></div>
            <button class="ed-tool-btn danger" onclick={editorClear} title="Clear editor">🗑️ Clear</button>
          </div>
        </div>

        <!-- CodeMirror container -->
        <div class="editor-cm-wrap card-glass-dark" use:initEditorAction></div>

        <!-- Error panel -->
        {#if editorErrors.length > 0}
          <div class="editor-error-panel">
            <div class="error-panel-title">⚠️ Lint Errors</div>
            {#each editorErrors as err}
              <div class="error-item">
                <span class="error-loc">Line {err.line}, Col {err.col}</span>
                <span class="error-msg">{err.msg}</span>
              </div>
            {/each}
          </div>
        {:else if editorValid === true}
          <div class="editor-ok-panel">
            <span>✅ JSON is valid</span>
            {#if editorRecordCount !== null}
              <span>· <strong>{editorRecordCount.toLocaleString()}</strong> top-level records</span>
            {:else}
              <span>· Object structure</span>
            {/if}
            <span>· {(new TextEncoder().encode(editorContent).length / 1024).toFixed(1)} KB</span>
          </div>
        {/if}
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

  /* ===== PIPELINE / QUEUE ===== */
  .queue-presets {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    padding: 14px 18px;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 12px;
  }
  .queue-section-label { font-size: 12px; color: #666; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; white-space: nowrap; }
  .preset-btn {
    padding: 8px 16px;
    border-radius: 9px;
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.12);
    color: #d0d0d0;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
  }
  .preset-btn:hover:not(:disabled) { background: rgba(255,255,255,0.14); color: #fff; transform: translateY(-1px); }
  .preset-btn:disabled { opacity: 0.4; cursor: not-allowed; }

  .queue-step-list { display: flex; flex-direction: column; }
  .queue-step-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 13px 16px;
    border-radius: 11px;
    border: 1px solid rgba(255,255,255,0.07);
    background: rgba(255,255,255,0.03);
    transition: all 0.2s;
  }
  .queue-step-row:hover { background: rgba(255,255,255,0.06); }
  .queue-step-row.q-running { border-color: rgba(246,173,85,0.4); background: rgba(246,173,85,0.06); }
  .queue-step-row.q-done    { border-color: rgba(80,180,130,0.3); background: rgba(80,180,130,0.05); }
  .queue-step-row.q-error   { border-color: rgba(220,80,80,0.3);  background: rgba(220,80,80,0.05);  }
  .queue-step-row.q-skipped { opacity: 0.4; }

  .q-step-indicator { width: 22px; display: flex; justify-content: center; }
  .q-dot { font-size: 14px; font-weight: 700; }
  .q-dot.pending  { color: #555; }
  .q-dot.running  { color: #f6ad55; }
  .q-dot.done     { color: #7ee8b0; }
  .q-dot.error    { color: #fc8181; }
  .q-dot.skipped  { color: #555; }

  .q-step-num   { font-size: 11px; color: #555; font-weight: 700; min-width: 18px; }
  .q-step-icon  { font-size: 18px; }
  .q-step-label { font-size: 14px; font-weight: 600; color: #d0d0d0; flex: 1; }
  .q-step-dur   { font-size: 12px; color: #888; font-family: 'JetBrains Mono','Fira Code',monospace; white-space: nowrap; }

  .q-inline-input {
    flex: 0 0 200px;
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 7px;
    padding: 6px 10px;
    color: #d0d0d0;
    font-size: 12px;
    outline: none;
  }
  .q-inline-sel {
    flex: 0 0 140px;
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 7px;
    padding: 6px 10px;
    color: #d0d0d0;
    font-size: 12px;
    outline: none;
    cursor: pointer;
  }
  .q-inline-label { font-size: 12px; color: #777; background: rgba(255,255,255,0.05); padding: 4px 9px; border-radius: 6px; }

  .q-step-btns { display: flex; gap: 5px; margin-left: auto; }
  .q-btn {
    padding: 5px 9px;
    border-radius: 6px;
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.08);
    color: #aaa;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.15s;
  }
  .q-btn:hover:not(:disabled) { background: rgba(255,255,255,0.13); color: #fff; }
  .q-btn:disabled { opacity: 0.3; cursor: not-allowed; }
  .q-btn.danger:hover { background: rgba(220,80,80,0.2); color: #fc8181; }

  .q-connector { text-align: center; color: rgba(255,255,255,0.15); font-size: 14px; line-height: 1; margin: 1px 0; padding-left: 24px; }

  .queue-empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    padding: 40px 20px;
    color: #555;
    font-size: 14px;
    border: 1px dashed rgba(255,255,255,0.08);
    border-radius: 12px;
  }

  .queue-add-section { display: flex; flex-direction: column; gap: 12px; }
  .step-type-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 8px;
  }
  .step-type-btn {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 11px 14px;
    border-radius: 10px;
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.1);
    color: #ccc;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
  }
  .step-type-btn:hover { background: rgba(255,255,255,0.12); color: #fff; transform: translateY(-2px); }
  .step-type-icon { font-size: 18px; }
  .step-type-label { font-size: 12px; }

  .queue-run-bar { display: flex; gap: 10px; align-items: stretch; }
  .queue-log-wrap { border-radius: 14px; overflow: hidden; }

  /* ===== DATASET PREVIEW ===== */
  .prev-controls {
    display: flex;
    gap: 10px;
    align-items: center;
  }
  .prev-search { flex: 0 0 240px; }
  .prev-limit-sel {
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 9px;
    padding: 11px 12px;
    color: #d0d0d0;
    font-size: 13px;
    outline: none;
    cursor: pointer;
    white-space: nowrap;
  }
  .prev-bulk-bar {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 10px;
    min-height: 44px;
  }
  .prev-table-wrap {
    overflow-x: auto;
    border-radius: 14px;
  }
  .prev-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }
  .prev-table thead th {
    padding: 13px 14px;
    text-align: left;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #666;
    border-bottom: 1px solid rgba(255,255,255,0.07);
    white-space: nowrap;
  }
  .col-check  { width: 36px; }
  .col-idx    { width: 52px; color: #555; font-size: 11px; }
  .col-actions{ width: 72px; }
  .prev-row {
    border-bottom: 1px solid rgba(255,255,255,0.04);
    cursor: pointer;
    transition: background 0.15s;
  }
  .prev-row:hover { background: rgba(255,255,255,0.04); }
  .prev-row.selected { background: rgba(66,153,225,0.08); }
  .prev-row.expanded { background: rgba(255,255,255,0.06); }
  .prev-row td { padding: 11px 14px; vertical-align: middle; }
  .cell-value {
    max-width: 260px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: #d0d0d0;
    font-size: 13px;
  }
  .row-actions { display: flex; gap: 6px; justify-content: flex-end; }
  .row-btn {
    padding: 5px 8px;
    border-radius: 6px;
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.1);
    color: #bbb;
    font-size: 13px;
    cursor: pointer;
    transition: all 0.15s;
  }
  .row-btn:hover { background: rgba(255,255,255,0.14); }
  .row-btn.danger:hover { background: rgba(220,80,80,0.2); border-color: rgba(220,80,80,0.3); color: #fc8181; }
  .expanded-row td {
    padding: 0 14px 14px 52px;
    background: rgba(0,0,0,0.3);
  }
  .record-json {
    font-family: 'JetBrains Mono','Fira Code',monospace;
    font-size: 12px;
    color: #7ee8b0;
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-all;
    max-height: 320px;
    overflow-y: auto;
    padding: 14px;
    background: rgba(0,0,0,0.2);
    border-radius: 8px;
    border: 1px solid rgba(255,255,255,0.06);
  }
  .prev-pagination {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
  }
  .page-indicator {
    font-size: 13px;
    color: #888;
    padding: 0 12px;
  }
  .checkbox-row { display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 13px; color: #ccc; }
  .checkbox-row input[type="checkbox"] { width: 15px; height: 15px; cursor: pointer; accent-color: #90cdf4; }

  /* ===== JSON EDITOR ===== */
  .editor-card { gap: 16px; }
  .editor-status-badge { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .ed-badge {
    padding: 5px 10px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 700;
    border: 1px solid transparent;
  }
  .ed-badge.valid   { background: rgba(80,180,130,0.15); border-color: rgba(80,180,130,0.3);  color: #7ee8b0; }
  .ed-badge.error   { background: rgba(220, 80, 80,0.15); border-color: rgba(220,80,80,0.3);  color: #fc8181; }
  .ed-badge.info    { background: rgba(66,153,225,0.12); border-color: rgba(66,153,225,0.25); color: #90cdf4; }
  .ed-badge.dirty   { background: rgba(246,173,85,0.12); border-color: rgba(246,173,85,0.25); color: #f6ad55; }
  .ed-badge.neutral { background: rgba(255,255,255,0.05); border-color: rgba(255,255,255,0.1); color: #777; }

  .editor-toolbar {
    display: flex;
    align-items: center;
    gap: 12px;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 10px 16px;
  }
  .editor-file-path { flex: 1; overflow: hidden; }
  .file-path-text {
    font-family: 'JetBrains Mono','Fira Code',monospace;
    font-size: 12px;
    color: #90cdf4;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    display: block;
  }
  .file-path-empty { font-size: 12px; color: #555; }
  .editor-tools { display: flex; align-items: center; gap: 6px; }
  .ed-tool-btn {
    padding: 7px 12px;
    border-radius: 8px;
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.1);
    color: #d0d0d0;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    white-space: nowrap;
  }
  .ed-tool-btn:hover:not(:disabled) { background: rgba(255,255,255,0.14); color: #fff; }
  .ed-tool-btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .ed-tool-btn.danger:hover { background: rgba(220,80,80,0.18); border-color: rgba(220,80,80,0.3); color: #fc8181; }
  .ed-divider { width: 1px; height: 22px; background: rgba(255,255,255,0.1); margin: 0 4px; }

  .editor-cm-wrap {
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid rgba(255,255,255,0.08);
  }
  :global(.editor-cm-wrap .cm-editor) { height: 420px; }
  :global(.editor-cm-wrap .cm-scroller) { overflow: auto; }

  .editor-error-panel {
    background: rgba(220,80,80,0.08);
    border: 1px solid rgba(220,80,80,0.25);
    border-radius: 10px;
    padding: 14px 18px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .error-panel-title { font-size: 12px; font-weight: 700; color: #fc8181; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px; }
  .error-item { display: flex; gap: 12px; align-items: baseline; }
  .error-loc { font-family: 'JetBrains Mono','Fira Code',monospace; font-size: 12px; color: #f6ad55; font-weight: 700; white-space: nowrap; }
  .error-msg { font-size: 13px; color: #fca5a5; }

  .editor-ok-panel {
    display: flex;
    align-items: center;
    gap: 10px;
    background: rgba(80,180,130,0.07);
    border: 1px solid rgba(80,180,130,0.2);
    border-radius: 10px;
    padding: 12px 18px;
    font-size: 13px;
    color: #7ee8b0;
  }
  .editor-ok-panel strong { color: #9ef0c0; }
</style>
