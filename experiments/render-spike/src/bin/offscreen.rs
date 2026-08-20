use std::process::ExitCode;

use render_spike::{demo_atlas, demo_snapshot, out_dir, render_offscreen_png};

fn main() -> ExitCode {
    let path = out_dir().join("spike.png");
    match render_offscreen_png(&demo_snapshot(), &demo_atlas(), 640, 360, &path) {
        Ok(adapter) => {
            let bytes = std::fs::metadata(&path).map(|m| m.len()).unwrap_or(0);
            println!("wrote {} ({} bytes) via {adapter}", path.display(), bytes);
            if bytes == 0 {
                eprintln!("error: spike.png is 0 bytes");
                return ExitCode::from(2);
            }
            ExitCode::SUCCESS
        }
        Err(e) => {
            eprintln!("offscreen FAILED: {e}");
            ExitCode::from(1)
        }
    }
}
