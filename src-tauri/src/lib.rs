use std::process::Command;
use std::path::PathBuf;

fn run_python_script(script_name: &str, args: Vec<String>, working_dir: &str) -> Result<String, String> {
    let script_path = PathBuf::from(working_dir)
        .join("python")
        .join(script_name);

    let python_dir = PathBuf::from(working_dir).join("python");

    let mut cmd = Command::new("python");
    cmd.arg(&script_path);
    for arg in &args {
        cmd.arg(arg);
    }
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
fn split_jsonl(folder: String, max_mb: f64) -> Result<String, String> {
    run_python_script("split_jsonl.py", vec!["--max-mb".to_string(), max_mb.to_string()], &folder)
}

#[tauri::command]
fn split_json(folder: String, max_mb: f64) -> Result<String, String> {
    run_python_script("split_json.py", vec!["--max-mb".to_string(), max_mb.to_string()], &folder)
}

#[tauri::command]
fn parquet_to_json(folder: String) -> Result<String, String> {
    run_python_script("parquet_to_json.py", vec![], &folder)
}

#[tauri::command]
fn convert_to_alpaca(folder: String) -> Result<String, String> {
    run_python_script("convert_to_alpaca.py", vec![], &folder)
}

#[tauri::command]
fn merge_alpaca(folder: String) -> Result<String, String> {
    run_python_script("merge_alpaca.py", vec![], &folder)
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
    let input_path  = format!("{}\\{}", folder, input_file);
    let output_path = format!("{}\\filtered_output.json", folder);

    let mut args = vec![
        "--input".to_string(),       input_path,
        "--output".to_string(),      output_path,
        "--domain".to_string(),      domain,
        "--min-output".to_string(),  min_output.to_string(),
        "--min-instr".to_string(),   min_instr.to_string(),
        "--max-records".to_string(), max_records.to_string(),
        "--format".to_string(),      format,
    ];
    if remove_dupes { args.push("--remove-dupes".to_string()); }
    if require_code  { args.push("--require-code".to_string()); }
    if !include_words.is_empty() { args.push("--include-words".to_string()); args.push(include_words); }
    if !exclude_words.is_empty() { args.push("--exclude-words".to_string()); args.push(exclude_words); }

    run_python_script("filter_dataset.py", args, &folder)
}

#[tauri::command]
fn smart_parse(folder: String, input_file: String) -> Result<String, String> {
    let input_path = format!("{}\\{}", folder, input_file);
    run_python_script("smart_parse.py", vec!["--input".to_string(), input_path], &folder)
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
    let input_path  = format!("{}\\{}", folder, input_file);
    let output_path = format!("{}\\variations_output.json", folder);

    let args = vec![
        "--input".to_string(),      input_path,
        "--output".to_string(),     output_path,
        "--api-key".to_string(),    api_key,
        "--count".to_string(),      count.to_string(),
        "--max-source".to_string(), max_source.to_string(),
        "--style".to_string(),      style,
        "--delay".to_string(),      delay.to_string(),
    ];

    run_python_script("generate_variations.py", args, &folder)
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
        "--url".to_string(),     url,
        "--output".to_string(),  folder.clone(),
        "--split".to_string(),   split,
        "--max-rows".to_string(), max_rows.to_string(),
        "--retries".to_string(), retries.to_string(),
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
