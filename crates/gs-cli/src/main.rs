//! Thin CLI used by `tools/gs.ps1`. Prints host/port/actor_id/command_id/result.
//! Never prints the bus token (I8).

use std::env;
use std::fs;
use std::path::PathBuf;
use std::process::ExitCode;
use std::time::Duration;

use gs_cli::{
    commands_from_jsonl, ensure_command_id, jobs_claim, jobs_finish, jobs_heartbeat, run_doctor,
    transaction_params, BusClient, Error, RpcError,
};
use gs_jobs::JobResult;
use serde_json::{json, Value};

fn main() -> ExitCode {
    match run(env::args().skip(1).collect()) {
        Ok(code) => code,
        Err(err) => {
            print_error(&err);
            ExitCode::from(1)
        }
    }
}

fn run(args: Vec<String>) -> Result<ExitCode, Error> {
    let parsed = parse_args(args)?;
    match parsed.verb.as_str() {
        "hello" => cmd_hello(&parsed).map(|()| ExitCode::SUCCESS),
        "send" => cmd_send(&parsed).map(|()| ExitCode::SUCCESS),
        "txn" => cmd_txn(&parsed).map(|()| ExitCode::SUCCESS),
        "events" => cmd_events(&parsed).map(|()| ExitCode::SUCCESS),
        "doctor" => Ok(cmd_doctor()),
        "jobs-claim" => cmd_jobs_claim(&parsed).map(|()| ExitCode::SUCCESS),
        "jobs-heartbeat" => cmd_jobs_heartbeat(&parsed).map(|()| ExitCode::SUCCESS),
        "jobs-finish" => cmd_jobs_finish(&parsed).map(|()| ExitCode::SUCCESS),
        other => Err(Error::Args(format!(
            "unknown verb '{other}'; expected hello|send|txn|events|doctor|jobs-claim|jobs-heartbeat|jobs-finish"
        ))),
    }
}

struct Parsed {
    root: PathBuf,
    client_name: String,
    verb: String,
    rest: Vec<String>,
    wait_ms: u64,
    params_file: Option<PathBuf>,
    worker_id: Option<String>,
    job_id: Option<String>,
    result_file: Option<PathBuf>,
}

fn parse_args(args: Vec<String>) -> Result<Parsed, Error> {
    let mut root = env::var_os("GS_ROOT")
        .map(PathBuf::from)
        .unwrap_or_else(|| env::current_dir().unwrap_or_else(|_| PathBuf::from(".")));
    let mut client_name = env::var("GS_CLIENT_NAME").unwrap_or_else(|_| "gs.ps1".into());
    let mut wait_ms = 1500_u64;
    let mut params_file = None;
    let mut worker_id = None;
    let mut job_id = None;
    let mut result_file = None;
    let mut verb = None;
    let mut rest = Vec::new();
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--root" => {
                i += 1;
                let value = args
                    .get(i)
                    .ok_or_else(|| Error::Args("--root requires a path".into()))?;
                root = PathBuf::from(value);
            }
            "--client-name" => {
                i += 1;
                let value = args
                    .get(i)
                    .ok_or_else(|| Error::Args("--client-name requires a value".into()))?;
                client_name = value.clone();
            }
            "--wait-ms" => {
                i += 1;
                let value = args
                    .get(i)
                    .ok_or_else(|| Error::Args("--wait-ms requires a number".into()))?;
                wait_ms = value
                    .parse()
                    .map_err(|_| Error::Args("--wait-ms must be an integer".into()))?;
            }
            "--params-file" => {
                i += 1;
                let value = args
                    .get(i)
                    .ok_or_else(|| Error::Args("--params-file requires a path".into()))?;
                params_file = Some(PathBuf::from(value));
            }
            "--worker-id" => {
                i += 1;
                let value = args
                    .get(i)
                    .ok_or_else(|| Error::Args("--worker-id requires a value".into()))?;
                worker_id = Some(value.clone());
            }
            "--job-id" => {
                i += 1;
                let value = args
                    .get(i)
                    .ok_or_else(|| Error::Args("--job-id requires a value".into()))?;
                job_id = Some(value.clone());
            }
            "--result-file" => {
                i += 1;
                let value = args
                    .get(i)
                    .ok_or_else(|| Error::Args("--result-file requires a path".into()))?;
                result_file = Some(PathBuf::from(value));
            }
            flag if flag.starts_with("--") => {
                return Err(Error::Args(format!("unknown flag {flag}")));
            }
            value if verb.is_none() => verb = Some(value.to_owned()),
            value => rest.push(value.to_owned()),
        }
        i += 1;
    }
    let verb = verb.ok_or_else(|| {
        Error::Args(
            "usage: gs-cli [--root PATH] hello|send|txn|events|doctor|jobs-claim|jobs-heartbeat|jobs-finish ..."
                .into(),
        )
    })?;
    Ok(Parsed {
        root,
        client_name,
        verb,
        rest,
        wait_ms,
        params_file,
        worker_id,
        job_id,
        result_file,
    })
}

fn cmd_doctor() -> ExitCode {
    let report = run_doctor();
    print!("{report}");
    if report.exit_ok() {
        ExitCode::SUCCESS
    } else {
        ExitCode::from(1)
    }
}

fn cmd_jobs_claim(parsed: &Parsed) -> Result<(), Error> {
    let worker_id = parsed
        .worker_id
        .clone()
        .or_else(|| env::var("GS_WORKER_ID").ok())
        .or_else(|| parsed.rest.first().cloned())
        .unwrap_or_else(|| format!("worker-{}", std::process::id()));
    let value = jobs_claim(&parsed.root, &worker_id)?;
    println!("{}", compact_json(&value)?);
    Ok(())
}

fn cmd_jobs_heartbeat(parsed: &Parsed) -> Result<(), Error> {
    let job_id = parsed
        .job_id
        .clone()
        .or_else(|| parsed.rest.first().cloned())
        .ok_or_else(|| Error::Args("jobs-heartbeat requires --job-id".into()))?;
    let worker_id = parsed
        .worker_id
        .clone()
        .or_else(|| env::var("GS_WORKER_ID").ok())
        .or_else(|| parsed.rest.get(1).cloned())
        .ok_or_else(|| Error::Args("jobs-heartbeat requires --worker-id".into()))?;
    let value = jobs_heartbeat(&parsed.root, &job_id, &worker_id)?;
    println!("{}", compact_json(&value)?);
    Ok(())
}

fn cmd_jobs_finish(parsed: &Parsed) -> Result<(), Error> {
    let job_id = parsed
        .job_id
        .clone()
        .or_else(|| parsed.rest.first().cloned())
        .ok_or_else(|| Error::Args("jobs-finish requires --job-id".into()))?;
    let raw = if let Some(path) = &parsed.result_file {
        fs::read_to_string(path)?
    } else if let Some(json) = parsed.rest.get(1) {
        json.clone()
    } else {
        return Err(Error::Args(
            "jobs-finish requires --result-file or a JSON argument".into(),
        ));
    };
    let map: std::collections::BTreeMap<String, Value> =
        serde_json::from_str(raw.trim()).map_err(|err| Error::json(err.to_string()))?;
    let result = JobResult::from_map(&map);
    let value = jobs_finish(&parsed.root, &job_id, &result)?;
    println!("{}", compact_json(&value)?);
    Ok(())
}

fn cmd_hello(parsed: &Parsed) -> Result<(), Error> {
    let client = BusClient::connect_named(&parsed.root, parsed.client_name.as_str())?;
    print_hello(&client);
    Ok(())
}

fn cmd_send(parsed: &Parsed) -> Result<(), Error> {
    let method = parsed
        .rest
        .first()
        .ok_or_else(|| Error::Args("send requires <method> [json-params]".into()))?;
    let params = read_send_params(parsed)?;
    let mut client = BusClient::connect_named(&parsed.root, parsed.client_name.as_str())?;
    if method == "session.hello" {
        print_hello(&client);
        println!("{}", compact_json(&client.hello().result)?);
        return Ok(());
    }
    let (params, command_id) = ensure_command_id(method, params);
    if let Some(command_id) = &command_id {
        println!("command_id: {command_id}");
    }
    match client.invoke(method, params) {
        Ok(invoked) => {
            println!("{}", compact_json(&invoked.result)?);
            Ok(())
        }
        Err(err) => Err(Error::Rpc(err)),
    }
}

fn cmd_txn(parsed: &Parsed) -> Result<(), Error> {
    let file = parsed
        .rest
        .first()
        .ok_or_else(|| Error::Args("txn requires <file.jsonl>".into()))?;
    let text = fs::read_to_string(file)?;
    let commands = commands_from_jsonl(&text)?;
    let (params, command_id) = transaction_params(commands, Some("gstxn"));
    let mut client = BusClient::connect_named(&parsed.root, parsed.client_name.as_str())?;
    println!("command_id: {command_id}");
    match client.call("transaction.execute", params) {
        Ok(result) => {
            println!("{}", compact_json(&result)?);
            Ok(())
        }
        Err(err) => Err(Error::Rpc(err)),
    }
}

fn cmd_events(parsed: &Parsed) -> Result<(), Error> {
    let mut client = BusClient::connect_named(&parsed.root, parsed.client_name.as_str())?;
    print_hello(&client);
    let notes = client.subscribe_and_collect(
        &["scene", "session", "confirmation"],
        Duration::from_millis(parsed.wait_ms),
    )?;
    for note in notes {
        let line = json!({
            "method": note.method,
            "params": note.params,
        });
        println!("{}", compact_json(&line)?);
    }
    Ok(())
}

fn print_hello(client: &BusClient) {
    println!(
        "actor_id: {} host: {} port: {}",
        client.actor_id(),
        client.host(),
        client.port()
    );
}

fn read_send_params(parsed: &Parsed) -> Result<Value, Error> {
    if let Some(path) = &parsed.params_file {
        let raw = fs::read_to_string(path)?;
        return parse_params(&raw);
    }
    parse_params(parsed.rest.get(1).map(String::as_str).unwrap_or("{}"))
}

fn parse_params(raw: &str) -> Result<Value, Error> {
    let raw = raw.trim();
    if raw.is_empty() {
        return Ok(json!({}));
    }
    serde_json::from_str(raw).map_err(|err| Error::json(err.to_string()))
}

fn compact_json(value: &Value) -> Result<String, Error> {
    serde_json::to_string(value).map_err(|err| Error::json(err.to_string()))
}

fn print_error(err: &Error) {
    let rpc = match err {
        Error::Rpc(rpc) => rpc.clone(),
        other => RpcError::with_data(
            gs_protocol::INVALID_REQUEST,
            other.to_string(),
            gs_protocol::ErrorData::new("E_IO"),
        ),
    };
    match serde_json::to_string(&rpc) {
        Ok(line) => eprintln!("{line}"),
        Err(_) => eprintln!("{{\"code\":-32600,\"message\":\"unprintable error\"}}"),
    }
}
