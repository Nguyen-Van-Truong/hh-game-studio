use std::process::ExitCode;

use gs_render2d::{demo_atlas, demo_snapshot, out_dir, render_offscreen_png};

fn main() -> ExitCode {
    let path = out_dir().join("offscreen.png");
    match render_offscreen_png(640, 360, &demo_snapshot(), &demo_atlas()) {
        Ok(bytes) => {
            if let Some(parent) = path.parent() {
                if let Err(e) = std::fs::create_dir_all(parent) {
                    eprintln!("mkdir FAILED: {e}");
                    return ExitCode::from(1);
                }
            }
            if let Err(e) = std::fs::write(&path, &bytes) {
                eprintln!("write FAILED: {e}");
                return ExitCode::from(1);
            }
            println!("wrote {} ({} bytes)", path.display(), bytes.len());
            if bytes.is_empty() {
                eprintln!("error: offscreen.png is 0 bytes");
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
