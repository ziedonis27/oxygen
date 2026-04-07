use std::process::Command;
use std::path::PathBuf;

/// Atrod pieejamo Python izpildāmo failu (python / python3)
fn find_python() -> String {
    for candidate in &["python", "python3"] {
        if let Ok(out) = Command::new(candidate).arg("--version").output() {
            if out.status.success() {
                return candidate.to_string();
            }
        }
    }
    "python".to_string()
}

/// Atrod python/ mapi — vispirms blakus .exe, tad darba mapē
fn get_scripts_dir() -> PathBuf {
    if let Ok(exe) = std::env::current_exe() {
        let exe_dir = exe.parent().unwrap_or(std::path::Path::new("."));
        let candidate = exe_dir.join("python");
        if candidate.exists() {
            return candidate;
        }
    }
    PathBuf::from("python")
}

fn run_python_script(script_name: &str, args: Vec<String>, _working_dir: &str) -> Result<String, String> {
    let python_dir = get_scripts_dir();
    let script_path = python_dir.join(script_name);

    if !script_path.exists() {
        return Err(format!(
            "Skripts nav atrasts: {}\nParbaudiet instalaciju.",
            script_path.display()
        ));
    }

    let python_cmd = find_python();

    let mut cmd = Command::new(&python_cmd);
    cmd.arg(&script_path);
    for arg in &args {
        cmd.arg(arg);
    }
    cmd.current_dir(&python_dir);

    let output = cmd.output().map_err(|e| {
        format!(
            "Nevar palaist Python ({}).\nParbaudiet, vai Python ir instalets un pievienots PATH.\nKluda: {}",
            python_cmd, e
        )
    })?;

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();

    if output.status.success() {
        Ok(stdout)
    } else {
        Err(if stderr.is_empty() { stdout } else { stderr })
    }
}

/// Pārbauda Python un svarīgākās pakotnes
#[tauri::command]
fn check_environment(working_dir: String) -> Result<String, String> {
    let python_cmd = find_python();

    let ver = Command::new(&python_cmd)
        .arg("--version")
        .output()
        .map_err(|_| String::from("Python nav atrasts! Instalejiet Python 3.10+ un pievienojiet PATH."))?;

    let version = String::from_utf8_lossy(&ver.stdout).to_string()
        + &String::from_utf8_lossy(&ver.stderr).to_string();

    let packages = ["anthropic", "datasets", "huggingface_hub", "requests", "tqdm", "pandas", "pyarrow"];
    let mut missing: Vec<&str> = vec![];

    for pkg in &packages {
        let ok = Command::new(&python_cmd)
            .args(["-c", &format!("import {}", pkg.replace("-", "_"))])
            .output()
            .map(|o| o.status.success())
            .unwrap_or(false);
        if !ok {
            missing.push(pkg);
        }
    }

    let mut result = format!("Python atrasts: {}\n", version.trim());
    result += &format!("Izmanto: {}\n", python_cmd);

    if missing.is_empty() {
        result += "Visas pakotnes ir instaletas!\n";
    } else {
        result += &format!("Trukstosas pakotnes: {}\n", missing.join(", "));
        result += &format!("Instalejiet: pip install {}\n", missing.join(" "));
    }

    let python_dir = get_scripts_dir();
    if python_dir.exists() {
        result += &format!("Python skriptu mape atrasta: {}\n", python_dir.display());
    } else {
        result += &format!("Python skriptu mape nav atrasta! ({}) Parbaudiet instalaciju.\n", python_dir.display());
    }

    let _ = working_dir; // nav izmantots vairs
    Ok(result)
}

#[tauri::command]
fn preview_dataset(
    folder: String,
    input_file: String,
    action: String,
    offset: i32,
    limit: i32,
    search: String,
    delete_indices: String,
) -> Result<String, String> {
    let input_path = std::path::Path::new(&folder).join(&input_file);
    let mut args = vec![
        "--input".to_string(),  input_path.to_string_lossy().to_string(),
        "--action".to_string(), action,
        "--offset".to_string(), offset.to_string(),
        "--limit".to_string(),  limit.to_string(),
        "--search".to_string(), search,
    ];
    if !delete_indices.is_empty() {
        args.push("--delete-indices".to_string());
        args.push(delete_indices);
        args.push("--output".to_string());
        args.push(input_path.to_string_lossy().to_string());
    }
    run_python_script("preview_dataset.py", args, &folder)
}

#[tauri::command]
fn diff_datasets(
    folder: String,
    file_a: String,
    file_b: String,
) -> Result<String, String> {
    let path_a = std::path::Path::new(&folder).join(&file_a);
    let path_b = std::path::Path::new(&folder).join(&file_b);
    run_python_script("diff_dataset.py",
        vec!["--file-a".to_string(), path_a.to_string_lossy().to_string(), "--file-b".to_string(), path_b.to_string_lossy().to_string()],
        &folder,
    )
}

#[tauri::command]
fn split_train_val_test(
    folder: String,
    input_file: String,
    train_pct: f64,
    val_pct: f64,
    test_pct: f64,
    shuffle: bool,
    format: String,
) -> Result<String, String> {
    let input_path = std::path::Path::new(&folder).join(&input_file);
    let mut args = vec![
        "--input".to_string(),      input_path.to_string_lossy().to_string(),
        "--output-dir".to_string(), folder.clone(),
        "--train-pct".to_string(),  train_pct.to_string(),
        "--val-pct".to_string(),    val_pct.to_string(),
        "--test-pct".to_string(),   test_pct.to_string(),
        "--format".to_string(),     format,
        "--seed".to_string(),       "42".to_string(),
    ];
    if shuffle { args.push("--shuffle".to_string()); }
    run_python_script("split_dataset.py", args, &folder)
}

#[tauri::command]
fn hf_upload(
    folder: String,
    input_file: String,
    repo: String,
    token: String,
    private: bool,
    branch: String,
) -> Result<String, String> {
    let input_path = format!("{}\\{}", folder, input_file);
    let python_dir = get_scripts_dir();
    let script_path = python_dir.join("hf_upload.py");
    let python_cmd = find_python();

    let mut cmd = std::process::Command::new(&python_cmd);
    cmd.arg(&script_path)
        .arg("--input")   .arg(&input_path)
        .arg("--repo")    .arg(&repo)
        .arg("--branch")  .arg(&branch);
    if private { cmd.arg("--private"); }
    cmd.env("HF_TOKEN", &token);
    cmd.arg("--token").arg(&token);
    cmd.current_dir(&python_dir);

    let output = cmd.output()
        .map_err(|e| format!("Nevar palaist Python: {}", e))?;
    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();

    if output.status.success() { Ok(stdout) }
    else { Err(if stderr.is_empty() { stdout } else { stderr }) }
}

/// Saglabā log failu diskā
#[tauri::command]
fn get_dashboard(folder: String) -> Result<String, String> {
    run_python_script("dashboard.py", vec!["--folder".to_string(), folder.clone()], &folder)
}

#[tauri::command]
fn score_dataset(
    folder: String,
    input_file: String,
    min_score: i32,
    max_score: i32,
    top: i32,
    stats_only: bool,
) -> Result<String, String> {
    let input_path  = std::path::Path::new(&folder).join(&input_file);
    let output_path = std::path::Path::new(&folder).join("scored_output.json");

    let mut args = vec![
        "--input".to_string(),     input_path.to_string_lossy().to_string(),
        "--output".to_string(),    output_path.to_string_lossy().to_string(),
        "--min-score".to_string(), min_score.to_string(),
        "--max-score".to_string(), max_score.to_string(),
        "--top".to_string(),       top.to_string(),
    ];
    if stats_only { args.push("--stats-only".to_string()); }

    run_python_script("score_dataset.py", args, &folder)
}

#[tauri::command]
fn filter_language(
    folder: String,
    input_file: String,
    lang: String,
    field: String,
    stats_only: bool,
    add_field: bool,
) -> Result<String, String> {
    let input_path  = std::path::Path::new(&folder).join(&input_file);
    let output_path = std::path::Path::new(&folder).join("lang_filtered.json");

    let mut args = vec![
        "--input".to_string(),  input_path.to_string_lossy().to_string(),
        "--output".to_string(), output_path.to_string_lossy().to_string(),
        "--lang".to_string(),   lang,
        "--field".to_string(),  field,
    ];
    if stats_only { args.push("--stats-only".to_string()); }
    if add_field  { args.push("--add-field".to_string()); }

    run_python_script("language_filter.py", args, &folder)
}

#[tauri::command]
fn save_log_file(path: String, content: String) -> Result<String, String> {
    std::fs::write(&path, &content)
        .map_err(|e| format!("Nevar saglabt failu: {}", e))?;
    Ok(format!("Saglabt: {}", path))
}

#[tauri::command]
fn split_jsonl(folder: String, max_mb: f64) -> Result<String, String> {
    run_python_script("split_jsonl.py", vec!["--folder".to_string(), folder.clone(), "--max-mb".to_string(), max_mb.to_string()], &folder)
}

#[tauri::command]
fn split_json(folder: String, max_mb: f64) -> Result<String, String> {
    run_python_script("split_json.py", vec!["--folder".to_string(), folder.clone(), "--max-mb".to_string(), max_mb.to_string()], &folder)
}

#[tauri::command]
fn parquet_to_json(folder: String) -> Result<String, String> {
    run_python_script("parquet_to_json.py", vec!["--folder".to_string(), folder.clone()], &folder)
}

#[tauri::command]
fn convert_to_alpaca(folder: String) -> Result<String, String> {
    run_python_script("convert_to_alpaca.py", vec!["--folder".to_string(), folder.clone()], &folder)
}

#[tauri::command]
fn merge_alpaca(folder: String) -> Result<String, String> {
    run_python_script("merge_alpaca.py", vec!["--folder".to_string(), folder.clone()], &folder)
}

#[tauri::command]
fn filter_dataset(
    folder: String,
    input_file: String,
    domain: String,
    min_output: i32,
    min_instr: i32,
    max_records: i32,
    remove_dupes: bool,
    require_code: bool,
    format: String,
    include_words: String,
    exclude_words: String,
) -> Result<String, String> {
    let input_path  = std::path::Path::new(&folder).join(&input_file);
    let output_path = std::path::Path::new(&folder).join("filtered_output.json");

    let mut args = vec![
        "--input".to_string(),       input_path.to_string_lossy().to_string(),
        "--output".to_string(),      output_path.to_string_lossy().to_string(),
        "--domain".to_string(),      domain,
        "--min-output".to_string(),  min_output.to_string(),
        "--min-instr".to_string(),   min_instr.to_string(),
        "--max-records".to_string(), max_records.to_string(),
        "--format".to_string(),      format,
        "--append".to_string(),
    ];
    if remove_dupes { args.push("--remove-dupes".to_string()); }
    if require_code  { args.push("--require-code".to_string()); }
    if !include_words.is_empty() { args.push("--include-words".to_string()); args.push(include_words); }
    if !exclude_words.is_empty() { args.push("--exclude-words".to_string()); args.push(exclude_words); }

    run_python_script("filter_dataset.py", args, &folder)
}

#[tauri::command]
fn smart_parse(folder: String, input_file: String) -> Result<String, String> {
    let input_path = std::path::Path::new(&folder).join(&input_file);
    run_python_script("smart_parse.py", vec!["--input".to_string(), input_path.to_string_lossy().to_string()], &folder)
}

#[tauri::command]
fn generate_variations(
    folder: String,
    input_file: String,
    api_key: String,
    count: i32,
    max_source: i32,
    style: String,
    delay: f64,
) -> Result<String, String> {
    let input_path  = std::path::Path::new(&folder).join(&input_file);
    let output_path = std::path::Path::new(&folder).join("variations_output.json");

    let cmd_args = vec![
        "--input".to_string(),      input_path.to_string_lossy().to_string(),
        "--output".to_string(),     output_path.to_string_lossy().to_string(),
        "--count".to_string(),      count.to_string(),
        "--max-source".to_string(), max_source.to_string(),
        "--style".to_string(),      style,
        "--delay".to_string(),      delay.to_string(),
    ];

    let python_dir = get_scripts_dir();
    let script_path = python_dir.join("generate_variations.py");
    let python_cmd = find_python();

    let mut cmd = Command::new(&python_cmd);
    cmd.arg(&script_path);
    for arg in &cmd_args {
        cmd.arg(arg);
    }
    cmd.env("ANTHROPIC_API_KEY", &api_key);
    cmd.current_dir(&python_dir);

    let output = cmd.output().map_err(|e| format!("Nevar palaist Python: {}", e))?;
    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();

    if output.status.success() {
        Ok(stdout)
    } else {
        Err(if stderr.is_empty() { stdout } else { stderr })
    }
}

#[tauri::command]
fn scrape_dataset(
    folder: String,
    url: String,
    hf_token: String,
    split: String,
    max_rows: i32,
    retries: i32,
) -> Result<String, String> {
    let mut args = vec![
        "--url".to_string(),      url,
        "--output".to_string(),   folder.clone(),
        "--split".to_string(),    split,
        "--max-rows".to_string(), max_rows.to_string(),
        "--retries".to_string(),  retries.to_string(),
    ];
    if !hf_token.is_empty() {
        args.push("--hf-token".to_string());
        args.push(hf_token);
    }
    run_python_script("smart_scraper.py", args, &folder)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            check_environment,
            save_log_file,
            get_dashboard,
            preview_dataset,
            diff_datasets,
            split_train_val_test,
            hf_upload,
            score_dataset,
            filter_language,
            split_jsonl,
            split_json,
            parquet_to_json,
            convert_to_alpaca,
            merge_alpaca,
            filter_dataset,
            smart_parse,
            generate_variations,
            scrape_dataset,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
