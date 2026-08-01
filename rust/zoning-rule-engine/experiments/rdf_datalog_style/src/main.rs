use rdf_datalog_style::{parse_ontology, parse_rule};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let ontology = parse_ontology(include_str!("../ontology.zonto"))?;
    let rule = parse_rule(include_str!("../article_iii.rules"), &ontology)?;
    println!("ONTOLOGY\n{}", serde_json::to_string_pretty(&ontology)?);
    println!(
        "\nNORMALIZED RULE\n{}",
        serde_json::to_string_pretty(&rule)?
    );
    Ok(())
}
