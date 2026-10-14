# Nghiên cứu lựa chọn công nghệ — Superagent 2D Web

Ngày cập nhật: 2026-10-14  
Phạm vi: bản web chơi trực tiếp trên desktop và mobile browser, giữ Classic-first: arena platform shooter 2D, trước khi mở các nâng cấp lớn.

## Khuyến nghị ngắn

Dùng **Phaser 4.2.1 (TypeScript/JavaScript) + Vite**, pin đúng phiên bản đã kiểm thử trong lockfile. Bản 4.2.1 được phát hành ngày 09-07-2026; nếu spike cho thấy plugin nội bộ chưa tương thích thì thử riêng Phaser 3.90, không tự động dùng `latest`. Dùng Phaser Canvas/WebGL để vẽ world, DOM/CSS cho menu/HUD và một lớp touch controls. Bắt đầu bằng Arcade Physics cho platform/collider hình chữ nhật; chỉ bật Matter khi mechanic thật sự cần rigid-body/constraint. Tự định nghĩa simulation fixed 60 Hz, input pressed/held/released và replay/hash ở lớp game để không phụ thuộc cadence render.

Phaser là framework 2D HTML5, hỗ trợ WebGL và Canvas, JavaScript/TypeScript, Scene, unified input cho keyboard/gamepad/mouse/touch, Arcade và Matter physics. Đây là sự cân bằng tốt giữa parity nhanh và quyền kiểm soát code.

Vite chỉ là build tool: dev server/HMR giúp thử nhanh, còn `vite build` tạo static assets cho CDN. Cần pin browser target và kiểm thử trên Chrome/Edge/Firefox desktop cùng Safari iOS/macOS và Chrome Android; default target của Vite có thể cao hơn các máy cũ.

## So sánh

| Lựa chọn | Ưu điểm | Nhược điểm / rủi ro | Vai trò đề xuất |
|---|---|---|---|
| HTML/CSS/JS + Canvas 2D/WebGL | Tải nhỏ, kiểm soát tuyệt đối, tích hợp DOM dễ, không lock-in | Tự viết scene graph, sprite atlas/animation, physics/collision, camera, input/touch, asset cache, pause/replay, WebGL batching/shader | Prototype kỹ thuật hoặc engine custom nhỏ; CSS cho HUD/menu |
| **Phaser** | 2D-first; WebGL + Canvas fallback; Scene/input/loader/camera/animation; Arcade + Matter; JS/TS và web-first | Arcade chỉ rectangle/circle; Matter nặng hơn; vẫn phải tự thiết kế deterministic simulation/replay/network; cần pin API | **Runtime Classic chính** |
| PixiJS | Renderer 2D modular, WebGL/WebGL2 stable; WebGPU có đường nâng cấp; batching/texture pipeline mạnh | Renderer-first, thiếu game scene/physics/combat loop; phải ghép physics/ECS/input | Chọn khi xây runtime custom hoặc ưu tiên visual pipeline |
| Three.js | WebGL2 mature, camera/scene/render cho 2.5D/3D | Thư viện 3D overkill cho 2D; tự lo sprite/physics/input/state; bundle/pipeline lớn | Chỉ mở khi đã có kế hoạch 2.5D/3D |
| Godot Web | Giữ scene/editor/physics và GDScript hiện có; WASM + WebGL2; có thể chia sẻ desktop/web | Godot 4 C# chưa export web; threads cần SharedArrayBuffer + cross-origin isolation; payload/startup lớn và DOM integration khó | Secondary export nếu reuse bản Godot là ưu tiên |
| Unity WebGL | Editor, asset, animation, physics 2D phong phú | Yêu cầu WebGL2 + 64-bit WebAssembly; tài liệu Unity nêu WebGL không hỗ trợ mobile; build/memory/license/CI nặng | Không chọn cho Y8-style desktop + mobile web |
| PlayCanvas | Browser-first JS/TS MIT; WebGL2 mặc định, WebGPU tùy chọn có fallback; hợp 2.5D/3D | Trọng tâm 3D, convention 2D/physics ít sẵn hơn Phaser; cần test browser matrix | Chỉ khi dự định nâng lên 2.5D/3D hoặc dùng editor cloud |
| Construct 3 | Editor chạy ngay trong browser; visual event workflow; export HTML5/offline | Subscription/editor-centric; semantic command, deterministic replay và custom collision khó kiểm soát | Prototype/content spike |
| GDevelop | No-code/event; export web và host gd.games nhanh | Abstraction/editor lock-in; khó kiểm soát deterministic physics/replay/bot phức tạp; phụ thuộc account/hosting | Prototype mechanic/level, không làm runtime Classic |

## Tài liệu nguồn chính thức

- Phaser overview: <https://docs.phaser.io/>; input: <https://docs.phaser.io/phaser/concepts/input>; physics: <https://docs.phaser.io/phaser/concepts/physics>; scenes: <https://docs.phaser.io/phaser/concepts/scenes>
- Phaser v4.2.1 release: <https://github.com/phaserjs/phaser/releases/tag/v4.2.1>
- Vite guide/build: <https://vite.dev/guide/>; <https://vite.dev/guide/build>
- Canvas 2D: <https://developer.mozilla.org/en-US/docs/Web/API/CanvasRenderingContext2D>; rendering contexts: <https://developer.mozilla.org/en-US/docs/Web/API/HTMLCanvasElement/getContext>
- Browser loop: <https://developer.mozilla.org/en-US/docs/Web/API/Window/requestAnimationFrame>; game-loop trade-offs: <https://developer.mozilla.org/en-US/docs/Games/Anatomy>
- PixiJS renderers: <https://pixijs.download/dev/docs/rendering.html>; renderer API: <https://api.pixijs.io/%40pixi/core/PIXI/Renderer.html>
- Three.js scene setup: <https://threejs.org/manual/pages/creating-a-scene.html>; WebGLRenderer: <https://threejs.org/docs/pages/WebGLRenderer.html>
- Godot web export: <https://docs.godotengine.org/en/4.4/tutorials/export/exporting_for_web.html>
- Unity WebGL browser requirements: <https://docs.unity.cn/Manual/webgl-browsercompatibility.html>; performance: <https://docs.unity.com/en-us/engine/7000.0/manual/platform-specific/webgl/develop/performance>
- PlayCanvas engine: <https://developer.playcanvas.com/user-manual/engine/>; browser support and WebGPU fallback: <https://developer.playcanvas.com/user-manual/engine/supported-browsers/>; graphics: <https://developer.playcanvas.com/user-manual/graphics/>
- Construct browser editor: <https://www.construct.net/en/make-games/manuals/construct-3/getting-started/get-construct-3>; publishing: <https://www.construct.net/en/make-games/manuals/construct-3/overview/publishing-projects>
- GDevelop publishing: <https://wiki.gdevelop.io/gdevelop5/publishing/>; HTML5 export: <https://wiki.gdevelop.io/gdevelop5/publishing/html5_game_in_a_local_folder/>
- Matter.js API: <https://brm.io/matter-js/docs/index.html>
- Web Audio API and autoplay/user gesture: <https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API>; <https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API/Using_Web_Audio_API>
- Pointer Events and multi-touch: <https://developer.mozilla.org/en-US/docs/Web/API/Pointer_events>; <https://developer.mozilla.org/en-US/docs/Web/API/Pointer_events/Multi-touch_interaction>
- Gamepad API: <https://developer.mozilla.org/en-US/docs/Web/API/Gamepad_API>
- PWA cache/service worker: <https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Caching>; <https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API/Using_Service_Workers>
- WebSocket/WebTransport: <https://developer.mozilla.org/en-US/docs/Web/API/WebSocket>; <https://developer.mozilla.org/en-US/docs/Web/API/WebTransport_API>
- Screen orientation/page visibility: <https://developer.mozilla.org/en-US/docs/Web/API/ScreenOrientation/lock>; <https://developer.mozilla.org/en-US/docs/Web/API/Page_Visibility_API>

## Lộ trình được đề xuất

1. **Web vertical slice**: Phaser + TypeScript/Vite; một map arena nguyên bản; hai fighter; đi/chạy/nhảy/thang; đấm/bắn/ném; pickup; bot đơn giản; pit/hazard; pause/restart; menu; touch overlay.
2. **Determinism gate**: simulation fixed 60 Hz tách render `requestAnimationFrame`; input trace seed; post-transition snapshot/hash; replay trên Chrome/Firefox/Edge/Safari desktop và Android/iOS.
3. **Presentation gate**: authored pixel fighters, map/props, FX/SFX, responsive HUD; test audio sau user gesture.
4. **Classic acceptance**: chỉ sau khi mechanic parity và browser matrix ổn định mới mở Pixi custom renderer, PlayCanvas/Three 2.5D, online hoặc các mode nâng cấp.

Phạm vi bản đầu chỉ dùng cơ chế và topology arena platform shooter làm tham chiếu; tên, code, art, âm thanh, map layout cụ thể và asset phải nguyên bản theo clean-room policy.

## Tooling web bổ trợ

Vite tạo bundle tĩnh `dist` bằng `vite build`, có `vite preview` để kiểm tra bản build; nên dùng cho dev/build chứ không coi preview server là production server. TypeScript thêm kiểm tra kiểu trước runtime, có ích khi game state và input command tăng. Pointer Events gom mouse, pen và touch vào một model chung; touch overlay vẫn cần `touch-action` và vùng bấm đủ lớn.

- Vite static deploy/build: <https://vite.dev/guide/static-deploy.html>, <https://vite.dev/guide/build>
- TypeScript Handbook: <https://www.typescriptlang.org/docs/handbook/intro>
- Pointer Events: <https://developer.mozilla.org/en-US/docs/Web/API/Pointer_events>
