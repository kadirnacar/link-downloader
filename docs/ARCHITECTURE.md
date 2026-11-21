# Mimari

## Katman görünümü

```text
┌──────────────────────────────────────────────────────┐
│ React + TypeScript frontend                           │
│ Pages / Components / Zustand stores / Wails bindings  │
└───────────────────────┬──────────────────────────────┘
                        │ generated service bindings + events
┌───────────────────────▼──────────────────────────────┐
│ Wails application (main.go)                           │
│ app lifecycle · native window · service registration  │
└───────────────────────┬──────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────┐
│ Application services                                 │
│ AnalyzeService · DownloadService                     │
│ SettingsService · DepsService                        │
└──────────────┬──────────────────┬────────────────────┘
               │                  │
┌──────────────▼─────────┐  ┌─────▼────────────────────┐
│ internal/model         │  │ internal/engine          │
│ options / media / DTO  │  │ yt-dlp args / execution  │
│ validation             │  │ process output           │
└────────────────────────┘  └──────────┬───────────────┘
                                       │
                             yt-dlp / FFmpeg / OS
```

## Bootstrap ve dependency direction

`main.go` uygulama başlangıcında Settings, Deps, Download ve Analyze servislerini oluşturur ve Wails service registry'ye ekler. UI, Go package import etmek yerine Wails tarafından üretilen `frontend/bindings` katmanını kullanır. Backend servisleri `internal/model` ve `internal/engine` katmanlarına bağımlıdır.

`internal/model`, frontend framework veya Wails UI ayrıntılarını bilmeyen ortak data contract ve validasyon alanıdır. `internal/engine`, yt-dlp argümanlarını/çalıştırma ayrıntılarını kapsar. `services`, uygulama kullanım senaryolarını birleştirir ve Wails event/servis adaptasyonunu yapar.

## Go servisleri

### AnalyzeService — `services/analyze.go`

- Desteklenen YouTube URL türlerini ayrıştırır.
- URL'den video veya playlist meta verisini getirir.
- Playlist öğelerini frontend'in kullanabileceği model formatına dönüştürür.
- Mevcut altyazı dil/format seçeneklerini sorgular.

### DownloadService — `services/download.go`

- Gönderilen öğeleri ve indirme seçeneklerini doğrular.
- Batch ve task kimlikleri üretir.
- Worker goroutine'leri ile task kuyruğunu yürütür.
- Pause/resume/cancel/retry ve toplu temizleme eylemlerini yönetir.
- Task snapshot ve batch progress bilgilerini UI'a açar.

### DepsService — `services/deps.go`

- yt-dlp, FFmpeg, FFprobe ve JS runtime varlığını/yolunu denetler.
- Gereken araçların kurulması ve yt-dlp güncellenmesi süreçlerini yönetir.
- Dependency durumunu frontend'e sunar.

### SettingsService — `services/settings.go`

- Download options ve uygulama ayarlarını JSON olarak okur/yazar.
- Ayar validasyonunu model katmanına devreder.
- yt-dlp argüman önizlemesi sağlar.

## Engine ve model

- `internal/model/options.go`: download options, varsayılanlar ve validasyon.
- `internal/model/appsettings.go`: uygulama ayarları ve doğrulama.
- `internal/model/media.go`: URL/medya/playlist modelleri.
- `internal/engine/builder.go`: yt-dlp komut argümanlarının üretilmesi.
- `internal/engine/exec.go`: process yürütme ve çıktı akışları.

## Frontend

- `src/api.ts`: generated Wails service binding'lerini tek noktadan export eder.
- `src/store.ts`: aktif sekme, analiz, seçenekler, uygulama ayarları, dependency ve batch state'i.
- `src/taskStore.ts`: download task listesi ve task progress state'i.
- `src/logStore.ts`: log satırları.
- `src/components`: analiz, seçenekler, kuyruk, sidebar, toast ve alan bileşenleri.
- `src/pages`: settings, logs ve about ekranları.

Backend event adları UI içinde `task:progress`, `batch:progress`, `batch:completed`, `deps:status` ve `log:line` olarak dinlenir.

## Serialization ve persistence

Wails binding'leri JSON uyumlu Go service dönüş/parametre tiplerinden üretilir. UI modelleri, `frontend/bindings` içindeki generated tiplerden import edilir. Kullanıcı ayarları `settings.json` ve `app.json` dosyalarında; görev/batch kuyruk snapshot'ı ise sürümlü `queue.json` dosyasında yerel kullanıcı config dizinine atomik olarak yazılır. Ayar sıfırlaması `settings-reset.json` işlem günlüğüyle kurtarılabilir.

## Threading ve lifecycle

DownloadService görevleri worker goroutine'lerinde yürütür; UI güncellemeleri Wails event kanalıyla iletilir. Wails `OnShutdown` callback'i yeni işleri durdurur, aktif analiz/indirmeleri iptal eder, kuyruk snapshot'ını kaydeder ve worker/process ağacının kapanmasını bekler. Unix process group, Windows process-tree terminasyonu kullanılır. Dependency güncellemesi ile çalışan araçlar `toolOperationGate` üzerinden koordine edilir.


## Queue persistence and shutdown lifecycle

`DownloadService` owns the in-memory queue and delegates durable snapshots to `queueStore`. The store writes a versioned `queue.json` file under the application configuration directory using a temporary file, file sync, and atomic rename. The persisted snapshot contains task options, playlist context, batch projection, attempt number, queue order, state, last progress, and output path.

On startup, queued tasks are restored in their original order. Tasks saved as `downloading` or `converting` are restored as `paused`; they are not automatically restarted. Before resuming a persisted task, its download options and YouTube URL are validated again.

The Wails `OnShutdown` callback cancels the application context and calls `services.ShutdownServices`. The analyzer cancels outstanding metadata/subtitle operations. The downloader rejects new work, persists active jobs as paused, cancels workers, and waits for their completion. yt-dlp is started in a process group on Unix-like systems; Windows uses `taskkill /T /F` for process-tree termination.

## Tool operation coordination

`services.toolOperationGate` is a process-local reader/writer gate. Downloads and metadata/subtitle extraction acquire shared read access. Dependency detection, installation, update, and engine path refresh acquire exclusive write access. This prevents an in-process dependency update from replacing yt-dlp or FFmpeg while an operation is using the tool. The gate is not an inter-process mutex.

