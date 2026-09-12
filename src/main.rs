use adblock::lists::{parse_filters, ParseOptions};
use adblock::Engine;
use sha2::{Digest, Sha256};
use std::fs::File;
use std::io::Write;

const EASYLIST_URL: &str = "https://easylist.to/easylist/easylist.txt";
const EASYPRIVACY_URL: &str = "https://easylist.to/easylist/easyprivacy.txt";
const UBLOCK_FILTERS_URL: &str = "https://ublockorigin.github.io/uAssets/filters/filters.txt";
const UBLOCK_QUICK_FIXES_URL: &str =
    "https://raw.githubusercontent.com/uBlockOrigin/uAssets/master/filters/quick-fixes.txt";

const OUTPUT_PATH: &str = "v2/latest-v0.12.5.nyv";
const SIGNATURE_PATH: &str = "v2/latest-v0.12.5.nyv.sha256";
const BINARY_MAGIC: &[u8; 8] = b"NYVRONv2";

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("Fetching essential high-performance filter lists...");
    let easylist = download_rules(EASYLIST_URL).await?;
    let ublock_filters = download_rules(UBLOCK_FILTERS_URL).await?;
    let ublock_quick_fixes = download_rules(UBLOCK_QUICK_FIXES_URL).await?;
    let easyprivacy = download_rules(EASYPRIVACY_URL).await?;

    let ad_rules = collect_rules(&[&easylist, &ublock_filters, &ublock_quick_fixes]);
    let tracker_rules = collect_rules(&[&easyprivacy]);

    let (ad_network, ad_cosmetic) = parse_filters(&ad_rules, false, ParseOptions::default());
    let (tracker_network, tracker_cosmetic) =
        parse_filters(&tracker_rules, false, ParseOptions::default());

    let rule_count =
        (ad_network.len() + ad_cosmetic.len() + tracker_network.len() + tracker_cosmetic.len())
            as u64;

    let ad_engine = Engine::from_rules(&ad_rules, ParseOptions::default());
    let tracker_engine = Engine::from_rules(&tracker_rules, ParseOptions::default());

    let ad_payload = ad_engine.serialize();
    let tracker_payload = tracker_engine.serialize();

    let scriptlet_rules = ad_rules
        .iter()
        .chain(tracker_rules.iter())
        .filter(|rule| rule.contains("##+js("))
        .cloned()
        .collect::<Vec<_>>()
        .join("\n");
    let binary = encode_engine_binary(
        &ad_payload,
        &tracker_payload,
        rule_count,
        scriptlet_rules.as_bytes(),
    );

    if let Some(parent) = std::path::Path::new(OUTPUT_PATH).parent() {
        std::fs::create_dir_all(parent)?;
    }
    let mut output = File::create(OUTPUT_PATH)?;
    output.write_all(&binary)?;
    output.sync_all()?;

    let signature = format!("{:x}", Sha256::digest(&binary));
    let mut signature_output = File::create(SIGNATURE_PATH)?;
    signature_output.write_all(signature.as_bytes())?;
    signature_output.sync_all()?;

    println!(
        "Successfully generated V2 latest.nyv ({} bytes, sha256={signature})",
        binary.len()
    );
    Ok(())
}

async fn download_rules(url: &str) -> Result<String, Box<dyn std::error::Error>> {
    let response = reqwest::Client::new()
        .get(url)
        .header("User-Agent", "Nyvron-Compiler/1.0")
        .send()
        .await?
        .error_for_status()?;
    Ok(response.text().await?)
}

fn collect_rules(sources: &[&str]) -> Vec<String> {
    let mut rules = Vec::new();
    for source in sources {
        for line in source.lines() {
            let trimmed = line.trim();
            if trimmed.is_empty() || trimmed.starts_with('!') {
                continue;
            }
            rules.push(trimmed.to_string());
        }
    }
    rules
}

fn encode_engine_binary(
    ad_payload: &[u8],
    tracker_payload: &[u8],
    rule_count: u64,
    scriptlet_rules: &[u8],
) -> Vec<u8> {
    let ad_len = ad_payload.len() as u64;
    let tracker_len = tracker_payload.len() as u64;

    let mut output = Vec::with_capacity(32 + ad_payload.len() + tracker_payload.len());
    output.extend_from_slice(BINARY_MAGIC);
    output.extend_from_slice(&rule_count.to_le_bytes());
    output.extend_from_slice(&ad_len.to_le_bytes());
    output.extend_from_slice(&tracker_len.to_le_bytes());
    output.extend_from_slice(ad_payload);
    output.extend_from_slice(tracker_payload);
    if !scriptlet_rules.is_empty() {
        output.extend_from_slice(b"NYVSCRP1");
        output.extend_from_slice(&(scriptlet_rules.len() as u64).to_le_bytes());
        output.extend_from_slice(scriptlet_rules);
    }
    output
}
