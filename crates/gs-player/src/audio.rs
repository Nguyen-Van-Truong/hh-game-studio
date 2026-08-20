//! kira playback for `SfxRequest`. Headless/CI uses the mock (null) backend.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use gs_runtime_core::{SfxRequest, World};
use kira::backend::mock::MockBackend;
use kira::sound::static_sound::StaticSoundData;
use kira::{AudioManager, AudioManagerSettings, Decibels, DefaultBackend};
use serde_json::Value;

enum Mixer {
    Device(Box<AudioManager<DefaultBackend>>),
    Null(Box<AudioManager<MockBackend>>),
    Off,
}

/// Play-process audio. Never panics on a missing file or missing device (GS-EC-33).
pub(crate) struct AudioEngine {
    play_dir: PathBuf,
    assets: BTreeMap<String, PathBuf>,
    mixer: Mixer,
    headless: bool,
    pub played: Vec<SfxRequest>,
    warnings: Vec<String>,
}

impl AudioEngine {
    pub(crate) fn headless(play_dir: Option<&Path>) -> Self {
        let play_dir = play_dir.unwrap_or_else(|| Path::new(".")).to_path_buf();
        let assets = load_asset_paths(&play_dir);
        Self {
            play_dir,
            assets,
            mixer: open_null(),
            headless: true,
            played: Vec::new(),
            warnings: Vec::new(),
        }
    }

    pub(crate) fn window(play_dir: &Path) -> Self {
        let assets = load_asset_paths(play_dir);
        Self {
            play_dir: play_dir.to_path_buf(),
            assets,
            mixer: open_device_or_null(),
            headless: false,
            played: Vec::new(),
            warnings: Vec::new(),
        }
    }

    /// GS-EC-33: drop the current output and rebuild (device → mock → off).
    pub(crate) fn rebuild_output(&mut self) {
        if self.headless {
            if matches!(self.mixer, Mixer::Off) {
                self.mixer = open_null();
            }
            return;
        }
        self.mixer = open_device_or_null();
    }

    /// Test helper: pretend the output device vanished.
    #[cfg(test)]
    pub(crate) fn simulate_device_loss(&mut self) {
        self.mixer = Mixer::Off;
        self.rebuild_output();
    }

    pub(crate) fn drain(&mut self, world: &mut World) {
        let queued = std::mem::take(&mut world.sfx_queue);
        for req in queued {
            self.played.push(req.clone());
            self.play_one(&req);
        }
        world.warnings.append(&mut self.warnings);
    }

    fn play_one(&mut self, req: &SfxRequest) {
        let Some(path) = resolve_asset_file(&self.play_dir, &self.assets, &req.asset_id) else {
            self.warnings.push(format!(
                "audio: missing file for {} (skip play)",
                req.asset_id
            ));
            return;
        };
        let data = match StaticSoundData::from_file(&path) {
            Ok(data) => data,
            Err(err) => {
                self.warnings.push(format!(
                    "audio: failed to load {} ({}): {err}",
                    req.asset_id,
                    path.display()
                ));
                return;
            }
        };
        let data = apply_sfx_settings(data, req);
        if let Err(err) = play_on(&mut self.mixer, data.clone()) {
            self.warnings
                .push(format!("audio: play failed ({err}); rebuilding output"));
            self.rebuild_output();
            if let Err(err) = play_on(&mut self.mixer, data) {
                self.warnings
                    .push(format!("audio: play skipped after rebuild ({err})"));
            }
        }
    }
}

fn apply_sfx_settings(data: StaticSoundData, req: &SfxRequest) -> StaticSoundData {
    let data = data
        .volume(amplitude_to_decibels(req.volume))
        .panning(req.pan);
    if req.looping {
        data.loop_region(0.0..)
    } else {
        data
    }
}

fn amplitude_to_decibels(volume: f32) -> Decibels {
    if !volume.is_finite() || volume <= 0.0 {
        Decibels::SILENCE
    } else {
        Decibels(20.0 * volume.log10())
    }
}

fn play_on(mixer: &mut Mixer, data: StaticSoundData) -> Result<(), String> {
    match mixer {
        Mixer::Device(manager) => manager.play(data).map(|_| ()).map_err(|e| e.to_string()),
        Mixer::Null(manager) => manager.play(data).map(|_| ()).map_err(|e| e.to_string()),
        Mixer::Off => Ok(()),
    }
}

fn open_null() -> Mixer {
    match AudioManager::<MockBackend>::new(AudioManagerSettings::default()) {
        Ok(manager) => Mixer::Null(Box::new(manager)),
        Err(_) => Mixer::Off,
    }
}

fn open_device_or_null() -> Mixer {
    match AudioManager::<DefaultBackend>::new(AudioManagerSettings::default()) {
        Ok(manager) => Mixer::Device(Box::new(manager)),
        Err(_) => open_null(),
    }
}

fn load_asset_paths(play_dir: &Path) -> BTreeMap<String, PathBuf> {
    let path = play_dir.join("asset-manifest.json");
    let Ok(bytes) = std::fs::read(&path) else {
        return BTreeMap::new();
    };
    let Ok(Value::Object(map)) = serde_json::from_slice::<Value>(&bytes) else {
        return BTreeMap::new();
    };
    let mut out = BTreeMap::new();
    for (id, record) in map {
        if let Some(rel) = record.get("path").and_then(Value::as_str) {
            out.insert(id, PathBuf::from(rel));
        }
    }
    out
}

fn resolve_asset_file(
    play_dir: &Path,
    assets: &BTreeMap<String, PathBuf>,
    asset_id: &str,
) -> Option<PathBuf> {
    let listed = assets.get(asset_id)?;
    if listed.is_file() {
        return Some(listed.clone());
    }
    let joined = play_dir.join(listed);
    if joined.is_file() {
        return Some(joined);
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn gs_ec_33_missing_device_does_not_panic() {
        let mut engine = AudioEngine::headless(None);
        engine.simulate_device_loss();
        let mut world = World::from_scene(gs_scene::Scene::default(), 1);
        world.sfx_queue.push(SfxRequest {
            asset_id: "a_missing".into(),
            volume: 1.0,
            pan: 0.0,
            looping: false,
        });
        engine.drain(&mut world);
        assert_eq!(engine.played.len(), 1);
        assert_eq!(engine.played[0].asset_id, "a_missing");
        assert!(world.warnings.iter().any(|w| w.contains("missing file")));
    }
}
