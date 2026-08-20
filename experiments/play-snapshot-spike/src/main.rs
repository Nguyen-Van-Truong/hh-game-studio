use std::env;
use std::path::PathBuf;
use std::process::ExitCode;

use play_snapshot_spike::{verify_snapshot, SpikeError};

fn main() -> ExitCode {
    match run() {
        Ok((play_id, revision)) => {
            println!("OK {play_id} {revision}");
            ExitCode::SUCCESS
        }
        Err(err) => {
            eprintln!("REJECT {err}");
            ExitCode::from(1)
        }
    }
}

fn run() -> Result<(String, String), SpikeError> {
    let manifest = parse_args(env::args().skip(1))?;
    let verified = verify_snapshot(&manifest)?;
    Ok((verified.play_id, verified.document_revision))
}

fn parse_args<I>(args: I) -> Result<PathBuf, SpikeError>
where
    I: IntoIterator<Item = String>,
{
    let args: Vec<String> = args.into_iter().collect();
    match args.as_slice() {
        [flag, path] if flag == "--snapshot" => Ok(PathBuf::from(path)),
        _ => Err(SpikeError::Usage(
            "usage: gs-player-stub --snapshot <manifest.json>".to_string(),
        )),
    }
}
