//! Startup project resolution for `gs-editor` (no implicit repo-root open).

use std::path::{Path, PathBuf};

/// Pick the project directory to `project.open`, or `None` (demo IR, no `.gs/` in cwd).
///
/// 1. `argv[1]` if it is a directory.
/// 2. `cwd/project.json` exists → `cwd`.
/// 3. `cwd/games/snake` exists and has `project.json`.
/// 4. `cwd/games/platformer` exists.
pub fn resolve_startup_project(cwd: &Path, argv1: Option<&Path>) -> Option<PathBuf> {
    if let Some(arg) = argv1 {
        if arg.is_dir() {
            return Some(arg.to_path_buf());
        }
    }
    if cwd.join("project.json").is_file() {
        return Some(cwd.to_path_buf());
    }
    let snake = cwd.join("games").join("snake");
    if snake.is_dir() && snake.join("project.json").is_file() {
        return Some(snake);
    }
    let platformer = cwd.join("games").join("platformer");
    if platformer.is_dir() && platformer.join("project.json").is_file() {
        return Some(platformer);
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use tempfile::TempDir;

    fn touch_dir(path: &Path) {
        fs::create_dir_all(path).expect("mkdir");
    }

    fn touch_file(path: &Path) {
        if let Some(parent) = path.parent() {
            touch_dir(parent);
        }
        fs::write(path, "{}\n").expect("write");
    }

    #[test]
    fn resolve_uses_argv_directory() {
        let dir = TempDir::new().expect("tempdir");
        let argv = dir.path().join("explicit");
        touch_dir(&argv);
        touch_file(&dir.path().join("project.json"));
        let got = resolve_startup_project(dir.path(), Some(&argv)).expect("argv");
        assert_eq!(got, argv);
    }

    #[test]
    fn resolve_ignores_argv_file_and_uses_cwd_project_json() {
        let dir = TempDir::new().expect("tempdir");
        let file = dir.path().join("not-a-dir.txt");
        touch_file(&file);
        touch_file(&dir.path().join("project.json"));
        let got = resolve_startup_project(dir.path(), Some(&file)).expect("cwd");
        assert_eq!(got, dir.path());
    }

    #[test]
    fn resolve_games_snake_when_it_has_project_json() {
        let dir = TempDir::new().expect("tempdir");
        let snake = dir.path().join("games").join("snake");
        touch_file(&snake.join("project.json"));
        let got = resolve_startup_project(dir.path(), None).expect("snake");
        assert_eq!(got, snake);
    }

    #[test]
    fn resolve_games_platformer_when_snake_missing() {
        let dir = TempDir::new().expect("tempdir");
        let platformer = dir.path().join("games").join("platformer");
        touch_file(&platformer.join("project.json"));
        let got = resolve_startup_project(dir.path(), None).expect("platformer");
        assert_eq!(got, platformer);
    }

    #[test]
    fn resolve_none_without_project_or_games() {
        let dir = TempDir::new().expect("tempdir");
        assert_eq!(resolve_startup_project(dir.path(), None), None);
    }

    #[test]
    fn resolve_skips_snake_without_project_json() {
        let dir = TempDir::new().expect("tempdir");
        touch_dir(&dir.path().join("games").join("snake"));
        let platformer = dir.path().join("games").join("platformer");
        touch_file(&platformer.join("project.json"));
        let got = resolve_startup_project(dir.path(), None).expect("platformer");
        assert_eq!(got, platformer);
    }
}
