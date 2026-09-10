use adblock::lists::{parse_filters, ParseOptions};
use adblock::Engine;
use std::collections::HashMap;
use std::fs::File;
use std::io::Write;

const EASYLIST_URL: &str = "https://easylist.to/easylist/easylist.txt";
const EASYPRIVACY_URL: &str = "https://easylist.to/easylist/easyprivacy.txt";
const UBLOCK_FILTERS_URL: &str = "https://ublockorigin.github.io/uAssets/filters/filters.txt";
const URLHAUS_URL: &str = "https://urlhaus.abuse.ch/downloads/text/";

const OUTPUT_PATH: &str = "latest.nyv";

#[derive(Debug, Clone)]
struct ScriptletRule {
    name: String,
    args: Vec<String>,
}

struct ScriptletEngine {
    rules_by_domain: HashMap<String, Vec<ScriptletRule>>,
}

impl ScriptletEngine {
    fn new() -> Self {
        Self { rules_by_domain: HashMap::new() }
    }
    fn add_rule(&mut self, line: &str) {
        let parts: Vec<&str> = line.split("##+js(").collect();
        if parts.len() != 2 || !parts[1].ends_with(')') { return; }
        let domain = parts[0].trim().to_lowercase();
        let body = &parts[1][..parts[1].len() - 1];
        let tokens: Vec<String> = body.split(',')
            .map(|s| s.trim().trim_matches('\'').trim_matches('"').to_string())
            .filter(|s| !s.is_empty()).collect();
        if tokens.is_empty() { return; }
        self.rules_by_domain.entry(domain).or_insert_with(Vec::new).push(ScriptletRule {
            name: tokens[0].clone(),
            args: tokens[1..].to_vec(),
        });
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("Fetching essential high-performance filter lists...");
    let easylist = download_rules(EASYLIST_URL).await?;
    let ublock_filters = download_rules(UBLOCK_FILTERS_URL).await?;
    let easyprivacy = download_rules(EASYPRIVACY_URL).await?;
    let urlhaus = download_rules(URLHAUS_URL).await?;

    let mut scriptlets = ScriptletEngine::new();
    let ad_rules = collect_rules(&[&easylist, &ublock_filters], &mut scriptlets);
    let tracker_rules = collect_rules(&[&easyprivacy, &urlhaus], &mut scriptlets);

    let ad_engine = Engine::from_rules(&ad_rules, ParseOptions::default());
    let tracker_engine = Engine::from_rules(&tracker_rules, ParseOptions::default());

    let ad_payload = ad_engine.serialize();
    let tracker_payload = tracker_engine.serialize();
    
    // EXACT V2 Envelope: 2u8 marker + u32 lengths + payloads
    let mut envelope = Vec::new();
    envelope.push(2u8); 
    
    envelope.extend_from_slice(&(ad_payload.len() as u32).to_le_bytes());
    envelope.extend_from_slice(&ad_payload);
    envelope.extend_from_slice(&(tracker_payload.len() as u32).to_le_bytes());
    envelope.extend_from_slice(&tracker_payload);

    let mut output = File::create(OUTPUT_PATH)?;
    output.write_all(&envelope)?;
    output.sync_all()?;

    println!("Successfully generated V2 latest.nyv ({} bytes)", envelope.len());
    Ok(())
}

async fn download_rules(url: &str) -> Result<String, Box<dyn std::error::Error>> {
    let response = reqwest::Client::new().get(url).header("User-Agent", "Nyvron-Compiler/1.0").send().await?.error_for_status()?;
    Ok(response.text().await?)
}

fn collect_rules(sources: &[&str], scriptlets: &mut ScriptletEngine) -> Vec<String> {
    let mut rules = Vec::new();
    for source in sources {
        for line in source.lines() {
            let trimmed = line.trim();
            if trimmed.is_empty() || trimmed.starts_with('!') { continue; }
            if trimmed.contains("##+js(") { scriptlets.add_rule(trimmed); }
            rules.push(trimmed.to_string());
        }
    }
    rules
}
