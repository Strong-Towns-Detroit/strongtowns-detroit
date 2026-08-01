//! Command-line compiler for authored zoning-language modules.

use std::{env, fs, process};

use zoning_rule_engine::{SourceDocument, compile, diagnose, extract, parse};

fn main() {
    let args = env::args().collect::<Vec<_>>();
    if args.len() < 3
        || !matches!(
            args[1].as_str(),
            "compile" | "compile-all" | "diagnose" | "extract"
        )
    {
        eprintln!(
            "usage: zoning-dsl <compile|diagnose|extract> PATH | zoning-dsl compile-all PATH..."
        );
        process::exit(2);
    }
    if args[1] == "compile-all" {
        let modules = args[2..]
            .iter()
            .map(|path| compile_path(path))
            .collect::<Vec<_>>();
        write_json(&modules);
        return;
    }
    if args.len() != 3 {
        eprintln!("compile and extract accept exactly one path");
        process::exit(2);
    }
    let source = match fs::read_to_string(&args[2]) {
        Ok(source) => source,
        Err(error) => {
            eprintln!("{}: {error}", args[2]);
            process::exit(1);
        }
    };
    if args[1] == "extract" {
        let extraction = extract(SourceDocument::new(args[2].clone(), source));
        write_json(&extraction);
        return;
    }
    if args[1] == "diagnose" {
        write_json(&diagnose(&source));
        return;
    }
    write_json(&compile_source(&source));
}

fn compile_path(path: &str) -> zoning_rule_engine::CompiledModule {
    let source = fs::read_to_string(path).unwrap_or_else(|error| {
        eprintln!("{path}: {error}");
        process::exit(1);
    });
    compile_source(&source)
}

fn compile_source(source: &str) -> zoning_rule_engine::CompiledModule {
    let syntax = match parse(source) {
        Ok(module) => module,
        Err(error) => {
            eprintln!("{error}");
            process::exit(1);
        }
    };
    match compile(&syntax) {
        Ok(module) => module,
        Err(error) => {
            eprintln!("{error}");
            process::exit(1);
        }
    }
}

fn write_json(value: &impl serde::Serialize) {
    match serde_json::to_string_pretty(value) {
        Ok(json) => println!("{json}"),
        Err(error) => {
            eprintln!("could not serialize compiled module: {error}");
            process::exit(1);
        }
    }
}
