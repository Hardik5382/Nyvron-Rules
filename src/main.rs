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
const BINARY_MAGIC: &[u8; 8] = b"NYVRONv1";

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
        Self {
            rules_by_domain: HashMap::new(),
        }
    }

    fn rule_count(&self) -> usize {
        self.rules_by_domain.values().map(Vec::len).sum()
    }

    fn add_rule(&mut self, line: &str) {
        let parts: Vec<&str> = line.split("##+js(").collect();
        if parts.len() != 2 || !parts[1].ends_with(')') {
            return;
        }

        let domain = parts[0].trim().to_lowercase();
        let body = &parts[1][..parts[1].len() - 1];

        let tokens: Vec<String> = body
            .split(',')
            .map(|s| s.trim().trim_matches('\'').trim_matches('"').to_string())
            .filter(|s| !s.is_empty())
            .collect();

        if tokens.is_empty() {
            return;
        }

        let rule = ScriptletRule {
            name: tokens[0].clone(),
            args: tokens[1..].to_vec(),
        };

        self.rules_by_domain
            .entry(domain)
            .or_insert_with(Vec::new)
            .push(rule);
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

    let (ad_network, ad_cosmetic) = parse_filters(&ad_rules, false, ParseOptions::default());
    let (tracker_network, tracker_cosmetic) =
        parse_filters(&tracker_rules, false, ParseOptions::default());

    let rule_count =
        (ad_network.len() + ad_cosmetic.len() + tracker_network.len() + tracker_cosmetic.len())
            as u64;

    let ad_engine = Engine::from_rules(&ad_rules, ParseOptions::default());
    let tracker_engine = Engine::from_rules(&tracker_rules, ParseOptions::default());

    // Use modern .serialize() for 0.12.5 compilation
    let ad_payload = ad_engine.serialize();
    let tracker_payload = tracker_engine.serialize();
    
    // RESTORED: Exactly the binary header your Kotlin app expects to pass state 0
    let binary = encode_engine_binary(&ad_payload, &tracker_payload, rule_count);

    let mut output = File::create(OUTPUT_PATH)?;
    output.write_all(&binary)?;
    output.sync_all()?;

    println!("Wrote {}", OUTPUT_PATH);
    println!("Network/cosmetic rule count: {}", rule_count);
    println!("Parsed scriptlet rule count: {}", scriptlets.rule_count());
    println!("Binary size: {} bytes", binary.len());

    Ok(())
}

async fn download_rules(url: &str) -> Result<String, Box<dyn std::error::Error>> {
    let response = reqwest::Client::new()
        .get(url)
        .header("User-Agent", "Nyvron-Rules-Compiler/1.0")
        .send()
        .await?
        .error_for_status()?;

    Ok(response.text().await?)
}

fn collect_rules(sources: &[&str], scriptlets: &mut ScriptletEngine) -> Vec<String> {
    let mut rules = Vec::new();

    for source in sources {
        for line in source.lines() {
            let trimmed = line.trim();

            if trimmed.is_empty() || trimmed.starts_with('!') {
                continue;
            }

            if trimmed.contains("##+js(") {
                scriptlets.add_rule(trimmed);
            }

            rules.push(trimmed.to_string());
        }
    }

    rules
}

// RESTORED: The strict 32-byte header parser format
fn encode_engine_binary(ad_payload: &[u8], tracker_payload: &[u8], rule_count: u64) -> Vec<u8> {
    let ad_len = ad_payload.len() as u64;
    let tracker_len = tracker_payload.len() as u64;

    let mut output = Vec::with_capacity(32 + ad_payload.len() + tracker_payload.len());
    output.extend_from_slice(BINARY_MAGIC);
    output.extend_from_slice(&rule_count.to_le_bytes());
    output.extend_from_slice(&ad_len.to_le_bytes());
    output.extend_from_slice(&tracker_len.to_le_bytes());
    output.extend_from_slice(ad_payload);
    output.extend_from_slice(tracker_payload);
    output
}
