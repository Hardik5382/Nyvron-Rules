use std::fs;
use adblock::engine::Engine;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("Fetching filter lists...");

    // 1. Core Ad Blocking & Site Repair (Combined into Ad Engine)
    let easylist = reqwest::get("https://easylist.to/easylist/easylist.txt").await?.text().await?;
    let ublock_filters = reqwest::get("https://raw.githubusercontent.com/uBlockOrigin/uAssets/master/filters/filters.txt").await?.text().await?;
    let ublock_unbreak = reqwest::get("https://raw.githubusercontent.com/uBlockOrigin/uAssets/master/filters/unbreak.txt").await?.text().await?;
    let adguard_anti_adblock = reqwest::get("https://filters.adtidy.org/extension/ublock/filters/3.txt").await?.text().await?; // AdGuard Base / Anti-Adblock

    // 2. Privacy, Annoyances, Cookies & Malware (Combined into Tracker/Privacy Engine)
    let easyprivacy = reqwest::get("https://easylist.to/easylist/easyprivacy.txt").await?.text().await?;
    let ublock_privacy = reqwest::get("https://raw.githubusercontent.com/uBlockOrigin/uAssets/master/filters/privacy.txt").await?.text().await?;
    let fanboy_annoyances = reqwest::get("https://easylist.to/easylist/fanboy-annoyance.txt").await?.text().await?;
    let adguard_cookies = reqwest::get("https://filters.adtidy.org/extension/ublock/filters/14.txt").await?.text().await?;
    let urlhaus = reqwest::get("https://urlhaus.abuse.ch/downloads/text/").await?.text().await?;

    // Combine strings logically
    let combined_ads = format!("{}\n{}\n{}\n{}", easylist, ublock_filters, ublock_unbreak, adguard_anti_adblock);
    let combined_privacy = format!("{}\n{}\n{}\n{}\n{}", easyprivacy, ublock_privacy, fanboy_annoyances, adguard_cookies, urlhaus);

    // 3. Compile into adblock engines
    println!("Compiling engines...");
    let ad_engine = Engine::from_str(&combined_ads, true)?;
    let tracker_engine = Engine::from_str(&combined_privacy, true)?;

    let ad_payload = ad_engine.serialize();
    let tracker_payload = tracker_engine.serialize();

    // 4. Construct the V2 envelope binary format expected by the Android app
    let mut envelope = Vec::new();
    envelope.push(2u8); // V2 version marker byte
    
    envelope.extend_from_slice(&(ad_payload.len() as u32).to_le_bytes());
    envelope.extend_from_slice(&ad_payload);

    envelope.extend_from_slice(&(tracker_payload.len() as u32).to_le_bytes());
    envelope.extend_from_slice(&tracker_payload);

    // 5. Write out the final binary
    fs::write("latest.nyv", envelope)?;
    println!("Successfully generated latest.nyv with all comprehensive filter lists!");

    Ok(())
}
