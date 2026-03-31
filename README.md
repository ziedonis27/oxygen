<div align="center">
  <img src="src-tauri/icons/icon.png" width="80" alt="Oxygen Logo"/>
  <h1>🐂 Oxygen</h1>
  <p><strong>ML Dataset Manager</strong> — A powerful desktop tool for preparing, filtering, and augmenting machine learning datasets.</p>

  [![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
  [![Built with Tauri](https://img.shields.io/badge/Built%20with-Tauri-24C8D8)](https://tauri.app)
  [![Svelte 5](https://img.shields.io/badge/Svelte-5-FF3E00)](https://svelte.dev)
  [![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB)](https://python.org)
</div>

---

## ✨ Features

| Tab | Function |
|-----|----------|
| 🌐 **Scraper** | Download datasets from HuggingFace, GitHub, or direct URLs with anti-blocking |
| ✂️ **Split** | Split large JSON/JSONL files into smaller chunks by MB size |
| 🔄 **Convert** | Convert Parquet → JSON and any format → Alpaca fine-tuning format |
| 🔗 **Merge** | Merge multiple Alpaca JSON files, auto-removing duplicates |
| 🔍 **Filter** | Filter by domain, quality, word count, required/excluded keywords |
| 🧠 **Analyze** | Smart Parse — auto-detect format, analyze structure, get filter recommendations |
| 🤖 **Augment** | Generate variations using Claude API to multiply your dataset |

## 🚀 Typical Workflow

```
🌐 Scrape → 🧠 Analyze → 🔍 Filter → 🔄 Convert to Alpaca → 🔗 Merge → 🏋️ Train!
```

## 📋 Requirements

- [Node.js](https://nodejs.org) 18+
- [Rust](https://rustup.rs) (for Tauri)
- Python 3.10+
- pip packages (see below)

## 🛠️ Installation

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/oxygen.git
cd oxygen

# 2. Install Node dependencies
npm install

# 3. Install Python dependencies
pip install datasets huggingface_hub anthropic requests tqdm pandas pyarrow

# 4. Run in development mode
npm run tauri dev

# 5. Build for production
npm run tauri build
```

## 🌐 Scraper — Supported Sources

| Source | Example |
|--------|---------|
| HuggingFace Dataset ID | `iamtarun/python_code_instructions_18k_alpaca` |
| HuggingFace URL | `https://huggingface.co/datasets/teknium/OpenHermes-2.5` |
| Direct file URL | `https://example.com/data.jsonl` |
| GitHub raw file | `https://github.com/user/repo/blob/main/data.json` |

**Anti-blocking features:**
- 🔄 User-Agent rotation (4 different browsers)
- ⏱️ Retry with exponential backoff
- 📦 HuggingFace streaming mode for large datasets
- 🔑 HF Token support for private datasets

## 🔍 Filter — Supported Domains

`svelte5` `python` `coding` `webdev` `blender` `zbrush` `unreal` `no filter`

## 🤖 Augment — Variation Styles

| Style | Description |
|-------|-------------|
| 🎲 Mixed | Random combination of all styles |
| ✏️ Rephrase | Reword the instruction differently |
| 💪 Harder | Add constraints and edge cases |
| 🌱 Simpler | Make more beginner-friendly |
| 🔀 Different | Create related but distinct task |

## 📁 Project Structure

```
oxygen/
├── src/                    # Svelte 5 frontend
│   └── routes/
│       └── +page.svelte    # Main UI (7 tabs)
├── src-tauri/              # Tauri/Rust backend
│   └── src/
│       └── lib.rs          # Tauri commands
├── python/                 # Python scripts
│   ├── smart_scraper.py    # Dataset downloader
│   ├── split_jsonl.py      # JSONL splitter
│   ├── split_json.py       # JSON splitter
│   ├── parquet_to_json.py  # Parquet converter
│   ├── convert_to_alpaca.py# Alpaca formatter
│   ├── merge_alpaca.py     # Dataset merger
│   ├── filter_dataset.py   # Dataset filter
│   ├── smart_parse.py      # Format analyzer
│   └── generate_variations.py # AI augmentation
└── README.md
```

## 🧠 Supported Input Formats

Oxygen auto-detects and handles:
- **Alpaca** — `instruction / input / output`
- **Messages** — `messages[user/assistant]`
- **HuggingFace Conversations** — `conversations[]`
- **Problem/Solution** — `problem / code / reasoning`
- **Prompt/Completion** — `prompt / completion`
- **Question/Answer** — `question / answer`

## 📄 License

This project is licensed under the **GNU General Public License v3.0** — see the [LICENSE](LICENSE) file for details.

---

<div align="center">
  Built with ❤️ using <a href="https://tauri.app">Tauri</a> + <a href="https://svelte.dev">Svelte 5</a> + Python
</div>
