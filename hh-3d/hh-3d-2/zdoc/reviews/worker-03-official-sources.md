I'll verify the official docs from the listed URLs first, then record only what those pages actually return.Two Godot networking pages timed out. I'll retry those exact URLs with a read-only HTTPS request and read the GDExtension page that was saved.The GDExtension fetch stored a docs dump. I'll pull the official stable GDExtension page and scan the multiplayer doc for DTLS and auth.The exact stable GDExtension URL returned a docs dump, not the article. I'll do one read-only HTTPS GET of that URL to capture the live title and status.WebSearch/WebFetch worked in this session. Two later Godot-docs retries timed out; a read-only `Invoke-WebRequest` on the GDExtension URLs then got **HTTP 429** and was not retried. No binaries, installs, clones, or repo edits.

## Direct answers

**Is 4.7.1 current stable actually verified?**  
**No.** On 2026-09-05 the official current Godot 4 stable is **4.7.2-stable** (18 August 2026). 4.7.1-stable is still an archived stable maintenance release, not the Windows current-download line. 4.8 is **dev4**, not stable.

**New-project safe pin (independent of the old VF 4.7.1 pin)**  
Pin the official stock editor **and matching export templates** from [godotengine.org](https://godotengine.org/download/windows/), not Steam/EGS if you need .NET (store builds omit C#). For a **new** product, pin **4.7.2-stable**, date **18 August 2026**, official blog commit **ed1daf0bf**. Record version + date + commit; do not float to 4.8-dev. Official blog: no known incompatibilities with 4.7.1; upgrade is encouraged. VF may stay on 4.7.1; that is a product pin, not the current official default. Choose standard vs .NET up front: Godot 4 C# cannot export to web. Extract-and-run; pair editor + templates of the same archive build.

**Stock plugins / UndoRedo / native extension without a core fork?**  
**Yes, on stock official binaries.** `EditorUndoRedoManager` is for editor plugins via `EditorPlugin.get_undo_redo()`. GDExtension loads native shared libraries at runtime **without compiling them into the engine**. C++ modules need an engine rebuild (deeper integration, not a C++ fork, but not the stock prebuilt). **Large-world double precision is not a stock prebuilt switch**; docs require recompiling editor + templates with `precision=double`, and GDExtensions must be rebuilt for that ABI.

**Does Godot ENet have DTLS, and is that game-account auth?**  
**DTLS: yes. Account auth: no.** `ENetConnection.dtls_client_setup` / `dtls_server_setup` are a Godot DTLS **transport-encryption** extension (hostname/cert via `TLSOptions`). That is not login, identity, or account linking. High-level multiplayer has a **separate** `SceneMultiplayer` hook (`auth_callback`, `send_auth`, `complete_auth`); the sample is “your logic, e.g. username/password against a database.” RPC `"authority"` is **node multiplayer authority**, not user accounts. HTML5 lacks raw TCP/UDP.

**Play Together: documented vs backend guesses**  
Documented on the official hub page: social town; knockout minigames; house parties; fishing; school; camping; pets; avatar/house decorate; Phone (minigames, party, decorate, recycle, quests, map, friends, collection); account-wide Achievements (gems, 5 stages); PlayTV; inbox; settings (audio, vibrate, invites, language, push, FPS, resolution, **account linking**, support); Bag (vehicles, pets, tools, fish, food, recycle); Kaia travel as **server transfer** via flight-attendant NPC (East Asia, Southeast Asia, Europe, Americas, Vietnam; passport stamps; free home return); weekend Lost Island / Captain Jack / digging; friends Follow/Summon; Game Party (30-player last-one-standing; race/obstacle/survival; Phone or Game Center); pet shop/eggs/wishes/bond/3 stages/tricks/combine.

**Not documented (do not treat as fact):** shard vs instance vs interest-management architecture; CCU/tick/capacity; Photon vs Godot vs custom backend; auth protocol; replication/AOI internals; monetization backend; map-stream implementation. “Travel = chuyển máy chủ” is a player-facing label, not a backend spec.

**No performance/capacity guarantees.** Photon interest is **replication culling**, not world sharding and not a CCU number. Godot large-world tables are float-precision ranges, not multiplayer capacity.

---

## Primary-source ledger (accessed 2026-09-05)

1. **https://godotengine.org/download/windows/** — *Download for Windows – Godot Engine* — **success**. Windows current line dated 18 August 2026; .NET build labeled **4.7.2**; extract-and-run; Vulkan 1.0 rec / GL 3.3 min; store builds omit .NET.

2. **https://godotengine.org/download/archive/** — *Godot download archive* — **success**. **4.7.2 current state: stable**; 4.7.1 also listed stable; **4.8 current state: dev4**.

3. **https://godotengine.org/download/archive/4.7.2-stable/** — *Download Godot 4.7.2 (stable)* — **success**. **4.7.2-stable**, 18 August 2026; Windows/Linux/macOS/Android + export templates.

4. **https://godotengine.org/article/maintenance-release-godot-4-7-2/** — *Maintenance release: Godot 4.7.2* — **success**. Built from **ed1daf0bf**; 57 fixes since 4.7.1; “no known incompatibilities”; “upgrade to 4.7.2.”

5. **https://docs.godotengine.org/en/stable/tutorials/scripting/gdextension/what_is_gdextension.html** — **partial**. First WebFetch HTTP-ok but extracted **docs chrome/nav**, not the article body. Later GET: **HTTP 429**. **Article body on this exact URL not verified.** Same-path **4.6** and **4.4** pages were read (items 6–7).

6. **https://docs.godotengine.org/en/4.6/tutorials/scripting/gdextension/what_is_gdextension.html** — *What is GDExtension?* — **success**. Native shared libs at runtime **without compiling them with the engine**; `gdextension_interface.h`, `extension_api.json`, `*.gdextension`.

7. **https://docs.godotengine.org/en/4.4/tutorials/scripting/gdextension/what_is_gdextension.html** — *What is GDExtension?* — **success**. Not a scripting language; vs modules: no engine compile, same lib in editor + export; modules = deeper, static. Must match float precision / `extension_api.json`. **4.4 page still labels GDExtension experimental** (version-bound; do not treat as 4.7 claim).

8. **https://docs.godotengine.org/en/stable/engine_details/engine_api/gdextension/what_is_gdextension.html** and **https://docs.godotengine.org/en/stable/about/release_policy.html** — **failed** (WebFetch timeout, then HTTP 429). Not used as verified.

9. **https://docs.godotengine.org/en/stable/classes/class_editorundoredomanager.html** — *EditorUndoRedoManager* — **success** (docs branded **Godot Engine 4.7**). Scene/global undo for **editor plugins**; `EditorPlugin.get_undo_redo()`; `create_action` / do-undo / `commit_action`. Non-editor use: `UndoRedo`.

10. **https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html** — *Exporting for the Web* — **success**. HTML5/Wasm/WebGL 2.0 only; Godot 4 C# **cannot** web-export; single-thread default since 4.3; native Android/iOS “always perform better by a significant margin” (no numbers); web networking = HTTP/WebSocket/WebRTC only, **no low-level TCP/UDP**; GDExtension needs Extension Support + web-built libs + COOP/COEP if threads.

11. **https://docs.godotengine.org/en/stable/tutorials/physics/large_world_coordinates.html** — *Large world coordinates* — **success**. Double-precision physics; mainly 3D; enable by **recompiling** editor + templates (`precision=double`); perf/memory cost, especially 32-bit; 2D render does not gain precision; multiplayer should use the same build type; GDExtension ABI changes (`REAL_T_IS_DOUBLE`). Recommended single-precision playable ranges in the table; **not** a CCU/capacity spec.

12. **https://docs.godotengine.org/en/stable/tutorials/networking/high_level_multiplayer.html** — *High-level multiplayer* — **success** (after one timeout). `ENetMultiplayerPeer` / WebRTC / WebSocket; HTML5 lacks some high-level + raw TCP/UDP; SceneTree `MultiplayerAPI`; RPC `@rpc` + **authority ≠ accounts**; optional `SceneMultiplayer` auth is **app-supplied**; “does not automatically make gameplay logic secure.”

13. **https://docs.godotengine.org/en/stable/classes/class_enetconnection.html** — *ENetConnection* — **success** (after one timeout). UDP ENet wrapper; **`dtls_client_setup` / `dtls_server_setup`**: “custom Godot extension allowing **DTLS encryption**”; `refuse_new_connections` only after DTLS server setup. No account API.

14. **https://hub.playtogether.haegin.kr/vi/homegame-guide/whats-the-play-together** — *“Play Together” là gì?* — **success**. Player-facing features listed above; travel described as server transfer; closing line says more activities exist beyond the list. **No backend/capacity text.**

15. **https://doc.photonengine.com/fusion/current/manual/advanced/interest-management** — *Interest Management* (Fusion 2) — **success**. Server→client **data culling** (`Object Interest`: AOI / Global / Explicit; `Behaviour Interest`; Fusion 2.1 Send Priority). Needs `Scheduling and Interest Management`. **Not sharding.** No CCU/capacity guarantees.

16. **https://www.openstreetmap.org/copyright** — *Copyright and License* — **success**. Data **ODbL** (OSMF): copy/adapt **with OSM credit** and **share-alike** if you build on the data; docs **CC BY-SA 2.0**; attribution rules vary by map type; **no free third-party map API/tiles** (API/Tile/Nominatim policies); do not import copyrighted sources (e.g. Google Maps); OSM marks are trademarks.

**WebSearch** of official Godot download/archive/4.7.2 pages corroborated 4.7.2 as current Windows stable (18 August 2026). Not used in place of the fetches above.
