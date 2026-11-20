# ytdlp-studio — Proje Analiz ve Düzeltme Raporu

**İnceleme tarihi:** 20 Kasım 2026  
**İncelenen paket:** `link-downloader.zip`  
**Proje tipi:** Wails v3 masaüstü uygulaması — Go backend, React 18 / TypeScript / Zustand frontend, yt-dlp + FFmpeg indirme motoru

## 1. Yönetici özeti

Paket, YouTube video ve playlist indirme amacıyla geliştirilmiş bir masaüstü uygulamasıdır. Kaynak kodun ana akışı anlaşılır ve küçük/orta ölçekli bir masaüstü uygulaması için makul ölçüde yalındır. Wails servis kayıtları `main.go` içinde; analiz, indirme, bağımlılık ve ayar işlemleri `services`; yt-dlp argüman üretimi ve proses yürütme `internal/engine`; doğrulama ve veri modelleri `internal/model`; ekran ve istemci durumu ise `frontend/src` içindedir.

İncelemede özellikle indirme kuyruğunun yarış durumları, iptal/duraklatma sonuçları, URL kabul sınırı, bağımlılık güncelleme sıralaması, ayarların diske yazılması, frontend–backend sözleşmesi ve artık kullanılmayan kod kontrol edildi. Güvenle doğrulanan sorunlar doğrudan kaynak dosyalarda düzeltildi. Eski/atıl parçalar yalnızca gerçekten referanssız oldukları veya uygulamanın sunduğu masaüstü mimarisine uymadıkları doğrulandıktan sonra kaldırıldı.

**Önemli:** Bu teslimat statik kaynak incelemesi ve doğrudan kod düzenlemesidir. Proje scriptleri, Go build/test komutları, Wails build, npm install/build veya release otomasyonları çalıştırılmadı. Bu nedenle derleme ve test başarısı iddia edilmemektedir.

## 2. Mevcut mimari değerlendirmesi

| Katman | Mevcut sorumluluk | Değerlendirme |
|---|---|---|
| Uygulama composition root | `main.go`, Wails servis kaydı, başlangıç işleri | Sade ve anlaşılır. Başlangıç bağımlılık işleri UI açıldıktan sonra arka planda çalışıyor. |
| Uygulama servisleri | `services/analyze.go`, `download.go`, `deps.go`, `settings.go` | İş akışlarının çoğu doğru yerde. Ancak Wails event yayını ve işletim sistemi dosya gezgini çağrıları servislerin içine gömülü. |
| İndirme motoru | `internal/engine/builder.go`, `exec.go` | Komut üretimi ve subprocess yürütme ayrımı yerinde. Global binary-path state test izolasyonunu ve çoklu engine örneğini zorlaştırabilir. |
| Domain / model | `internal/model` | JSON/Wails sözleşmeleri için yalın DTO yaklaşımı uygun. Bazı model tipleri hem servis/domain hem UI kontratı olarak kullanılıyor. |
| Persistence | `services/settings.go` | Ayarlar kullanıcı config alanında saklanıyor; tekil dosya yazımı atomik ve POSIX izinleri sınırlandırılmış. Kuyruk/batch kalıcı değil. |
| Frontend | `frontend/src` ve üretilen `frontend/bindings` | Zustand store'ları görev, uygulama ve log state'ini ayırıyor. Bazı alanlarda event payload tipleri runtime cast ile ele alınıyor. |
| Build/release | kök ve `build/*/Taskfile.yml`, shell/PowerShell dosyaları | Masaüstü platform hedefleri mevcut. Sunucu modu vaat eden eski parça uygulama mimarisiyle uyumsuzdu ve kaldırıldı. |

Katmanlar arası en belirgin mimari borç, `services` paketinin doğrudan Wails `application` event API'sini çağırmasıdır. Şu anki uygulama için işlevsel olsa da servislerin framework dışı testini ve farklı bir UI/host'a taşınmasını zorlaştırır. Bunu düzeltmek için gereksiz bir interface/factory katmanı eklenmedi; ileride event yayınını composition root üzerinden enjekte etmek veya küçük bir event adapter'a almak yeterli olacaktır.

## 3. Bulunan sorunlar ve yapılan düzeltmeler

| Öncelik | İlk durum | Yapılan işlem |
|---|---|---|
| Kritik | Silinmiş veya eski denemeye ait kuyruk girdisi worker tarafından daha sonra çalıştırılabiliyordu. Duraklatıp hemen devam etme yeni deneme ile eski prosesi çakıştırabiliyordu. | Kuyruk girdileri attempt/generation ile doğrulanıyor; eski denemeler geçersiz kılınıyor; görev başına referans sayımlı çalışma kilidi eski prosesin çözülmesini bekliyor. Silinmiş/iptal edilmiş girdiler artık runnable kontrolünü geçemiyor. |
| Kritik | Cancel/Pause ile worker'ın başarı/hata sonucu yarıştığında eski sonuç kullanıcı kararını ezebiliyordu. Aynı görev birden çok terminal geçiş/batch bildirimi oluşturabiliyordu. | `finish` geçişi idempotent yapıldı; deneme numarası ve terminal state kontrolü eklendi; iptal/duraklatma işareti başarı/hata commit'ini engelliyor. Duraklatılmış görevden iptale geçiş ayrıca ele alındı. |
| Yüksek | İndirme kuyruğuna desteklenmeyen URL veya URL'deki video kimliği ile MediaEntry kimliği uyuşmayan öğe eklenebiliyordu. | `Enqueue` aşamasında URL HTTPS/YouTube allowlist kontrolünden geçiriliyor ve URL video kimliği ile entry kimliği eşleştiriliyor. |
| Yüksek | URL host kontrolü `youtube.com` metnine dayalı geniş bir eşleşme ile taklit alan adlarını kabul etme riski taşıyordu. | Kesin host allowlist'i, HTTPS, kullanıcı bilgisi ve port kontrolleri eklendi. Video ve playlist kimlikleri regex ile doğrulanıyor. |
| Yüksek | Başlangıç bağımlılık kontrolü ve yt-dlp otomatik güncellemesi paralel başlayabiliyordu. | `main.go` başlangıç işlerini tek goroutine içinde sıralı çalıştırıyor. `DepsService` içinde Check/Install/Ensure/Update işlemleri mutex ile seri hale getirildi. |
| Yüksek | `EnsureDeps` bazı mevcut fakat çalışmayan binary'leri yalnızca kurulu olarak raporlayabiliyordu. | yt-dlp, ffmpeg ve ffprobe için gerçek versiyon/çalıştırma doğrulaması yapılıyor; hatalı binary durumu hata olarak döndürülüyor. |
| Yüksek | yt-dlp stdout/stderr taraması 1 MiB üzerindeki tek satırda durabilir, tarama hatası yutulabilir ve child process pipe buffer'ı dolunca kilitlenebilirdi. | Scanner hatası artık raporlanıyor; hata alan akışın kalan pipe içeriği tüketilerek child process'in pipe üzerinde takılması önleniyor. |
| Yüksek | yt-dlp komut argümanları log'a yazılırken çerez/proxy gibi sırlar ve kullanıcıya özel yollar görünür olabiliyordu. | Kimlik bilgisi, proxy, referer, çerez, çıktı yolu/şablonu, archive, cache, FFmpeg ve config argümanlarının değerleri log kaydında maskeleniyor. |
| Orta | Ayar dosyaları daha geniş dosya izinleriyle oluşabiliyor ve geçici dosya doğrudan hedefe yazılabiliyordu. | POSIX'te config dizini `0700`, ayar dosyaları `0600`; yazma geçici dosya + sync + rename ile yapılıyor. |
| Orta | Ayar sıfırlama diske yazma hatalarını yutuyor ve UI yanlış başarı gösterebiliyordu. | `Reset` / `ResetApp` artık hata döndürüyor; frontend başarısızlığı kullanıcıya bildiriyor. |
| Orta | JSON ayarları bilinmeyen alanları sessizce kabul ediyor; bozuk/trailing veri tespiti zayıftı. | Strict decode (`DisallowUnknownFields`) ve tek JSON dokümanı kontrolü eklendi. Bu uygulama eski ayar formatına geriye dönük uyumluluk sağlamaz; geçersiz/eskimiş dosya varsayılanlara düşer. |
| Orta | Playlist ters sıralama seçeneği UI'da görünmesine rağmen analiz çağrısına taşınmıyordu. | `playlistReverse` analiz scope parametresine bağlandı; backend `--playlist-reverse` argümanını üretiyor. |
| Orta | Frontend bazı backend metodlarını dynamic lookup/`any` ile çağırıyordu ve gereksiz tekrar eden Snapshot hydration vardı. | Üretilmiş Wails binding'leri doğrudan kullanıldı; UI başlangıç hydration tek noktaya alındı; ayar ve queue bileşenlerindeki `any` kullanımları azaltıldı. |
| Orta | Worker ve batch ilerlemesinde iptal edilmiş/terminal görevler için geç ilerleme event'leri gelebiliyordu. | Attempt/state/cancel kontrolleri eklendi; batch yüzdesi sınırlandırıldı ve BatchTitle snapshot/event sözleşmesine eklendi. |
| Orta | Ayar kataloğunda backend modelinde artık kullanılmayan `Language` ve `LogLevel` alanları bulunuyordu. | Bu kullanılmayan alanlar Go modelinden, TS binding/modelinden, frontend varsayılanlarından ve ayar kataloğundan kaldırıldı. |
| Orta | `Retry` ayrı bir API gibi sunuluyor, gerçekte Resume ile aynı davranışı tekrarlıyordu. | Kullanılmayan `Retry` export/binding kaldırıldı; UI `Resume` kullanıyor. `YtDlpVersion`, `ToolDirectory`, `Version` ve `EntryURL` kullanılmayan yardımcıları da kaldırıldı. |
| Orta | `services/playlist_all.go` içinde yalnızca dosyanın kendi içinde çağrılan reflection tabanlı eski yardımcılar vardı. | Referanssız dosya kaldırıldı; aktif analiz servisi doğrudan tipli JSON decode kullanıyor. |
| Orta | Wails masaüstü uygulamasında HTTP server giriş noktası bulunmadığı hâlde Taskfile ve Docker server şablonu sunucu modu varmış izlenimi veriyordu. | Sunucu modu Taskfile hedefleri ve `build/docker/Dockerfile.server` kaldırıldı. Cross-compile Dockerfile'ları korundu. |
| Düşük | Tek seferlik exact-string refactor script'i kaynak kod/release akışına bağlı değildi. | Referanssız `apply_refactor.py` kaldırıldı. Aktif build/release scriptleri korunmuştur. |
| Düşük | README Node sürümü lockfile'daki Vite/eklenti engine gereksiniminden düşüktü; Go test yönergesi frontend'i gereksiz şekilde hazırlatıyordu. | Node alt sınırı Node 20.19 veya 22.12 olarak güncellendi; test talimatı ilgili Go paketleriyle sınırlandı; kurulumda `npm ci` kullanılıyor. |

### Düzenlenen ana dosyalar

- Backend: `main.go`, `services/analyze.go`, `services/deps.go`, `services/download.go`, `services/settings.go`, `internal/engine/exec.go`, `internal/engine/builder.go`, `internal/model/appsettings.go`.
- Backend test kaynakları: `services/analyze_test.go`, `services/download_test.go`, `internal/engine/args_test.go` (yeni regresyon senaryoları eklendi/güncellendi; çalıştırılmadı).
- Frontend: `frontend/src/App.tsx`, `components/DownloadButton.tsx`, `components/Field.tsx`, `components/PasteBar.tsx`, `components/QueuePanel.tsx`, `pages/SettingsPage.tsx`, `settings/catalog.ts`, `store.ts`, `taskStore.ts`, `logStore.ts`.
- Üretilen Wails binding'leri: `frontend/bindings/ytdlp-studio/...`.
- Doküman/build tanımları: `README.md`, `Taskfile.yml`, `build/Taskfile.yml`.

## 4. Kaldırılan dosyalar

1. `services/playlist_all.go` — tüm `plAll*` yardımcıları dosya içinde kapalıydı; dış çağrı noktası bulunmadı.
2. `build/docker/Dockerfile.server` — `server,production` tag ve HTTP portu bekleyen ama projede karşılık gelen server main/API bulunmayan masaüstü dışı şablon.
3. `apply_refactor.py` — tek seferlik, exact-string patch zinciri; aktif uygulama veya release sürecinden çağrılmıyor.

`build/docker/Dockerfile.cross`, `Dockerfile.linux`, macOS/Windows/Linux paketleme dosyaları, mobil platform şablonları ve gerçek build/release scriptleri korunmuştur. Sadece dosya adında eski/geçici izlenimi verdiği için silme yapılmamıştır.

## 5. Bağımlılık incelemesi

### Go

Doğrudan bağımlılıklar:

- `github.com/lrstanley/go-ytdlp` — yt-dlp/FFmpeg kurulum ve dağıtım yardımcıları.
- `github.com/wailsapp/wails/v3` — masaüstü uygulama kabuğu, servis bridge, event ve dialog API'leri.

Her iki doğrudan bağımlılığın kaynakta kullanım noktası vardır. Dolaylı bağımlılıklar Wails/go-ytdlp alt bağımlılıkları olarak tutuldu. Kullanılmayan olduğu kanıtlanmış doğrudan/dolaylı bir modül tespit edilmedi; bu nedenle `go.mod` / `go.sum` üzerinde tahmine dayalı silme yapılmadı.

### npm

React, React DOM, Zustand ve Wails runtime frontend kaynaklarında kullanılıyor. Vite, React eklentisi, TypeScript ve React type paketleri geliştirme/build zincirinin parçası. Güvenle kaldırılabilecek kullanılmayan npm bağımlılığı tespit edilmedi. Lockfile sürümleri değiştirilmedi.

## 6. Kalan eksiklikler ve önerilen sonraki işler

Aşağıdaki maddeler bu pakette tamamlanmış sayılmamalıdır. Bunlar kaynak incelemesinde tespit edilen sonraki geliştirme ihtiyaçlarıdır.

### P1 — İşletim ve veri güvenilirliği

1. **Kuyruk kalıcılığı:** Görev, batch ve ilerleme bilgileri yalnızca `DownloadService` belleğinde. Uygulama kapatılıp açıldığında kuyruk ve geçmiş kaybolur. İstenen davranışa göre SQLite veya küçük bir transactional store ile görev metadata'sı saklanmalı; devam ettirme politikası ayrıca tanımlanmalıdır.
2. **Graceful shutdown:** Wails uygulaması kapanırken worker goroutine'leri ve aktif yt-dlp/ffmpeg çocuk süreçleri için açık bir kapanış/iptal koordinasyonu bulunmuyor. App shutdown lifecycle'ına bağlanan servis durdurma akışı ve platforma göre process-group/tree terminate davranışı eklenmelidir.
3. **Başlangıç güncellemesi ile indirme koordinasyonu:** `DepsService` kendi kurulum/güncelleme metotlarını kilitliyor; fakat bu kilit aktif `DownloadService` prosesleriyle paylaşılmıyor. UI açılırken arka plandaki yt-dlp güncellemesi kullanıcı indirmesiyle çakışabilir. Tek bir dependency-operation gate veya başlangıç işi bitene kadar indirme başlatmayı engelleyen durum yönetimi eklenmelidir.
4. **Ayar yükleme hatalarının görünür kılınması:** `Load` / `LoadApp` dosya okunamadığında, JSON bozuk olduğunda veya tanınmayan alan bulunduğunda varsayılan döndürüyor; neden bilgisi UI'a taşınmıyor. En azından uyarı/log üretilmeli. `Reset` ve `ResetApp` iki ayrı yazım olduğundan ikinci dosya başarısızsa diskte kısmi sıfırlama oluşabilir; ortak atomik ResetAll işlemi tercih edilmelidir.

### P2 — Mimari ve güvenlik

5. **Wails event bağımlılığı:** Servislerin `application.Get().Event.Emit` çağırması domain akışını Wails'e bağlıyor. Küçük bir event publisher adapter'ı veya composition root tarafından sağlanan callback, framework bağımlılığını sınırlar.
6. **Engine global path state:** `engine.SetPaths` ile binary yolları paket seviyesinde global tutuluyor. Şu an mutex ile data race riski azaltılmış olsa da servis/test izolasyonu için `Engine` yapılandırmasının örnek bazlı olması daha güvenli.
7. **Günlüklerde araç çıktısı:** Komut argümanlarının hassas kısımları maskeleniyor; ancak yt-dlp stdout/stderr içeriği de doğrudan log'a aktarılıyor. Araç hata metinleri URL, yerel yol veya başka hassas bilgileri yine içerebilir. Log redaction filtresi ve log dışa aktarma politikası ayrıca ele alınmalı.
8. **Gelişmiş argüman alanı:** `extraArgs` içinde `--exec` / `--exec-before-download` gibi yerel komut çalıştırabilen yt-dlp seçenekleri kullanılabilir. UI uyarısı eklendi, fakat uygulama bu argümanları sandbox'a almıyor. Güvenilmeyen yapılandırma/profil içeriği çalıştırılmamalı.
9. **Ayar şeması:** Eski veya bilinmeyen alanı bulunan ayar dosyası strict decode nedeniyle varsayılana düşer. Geriye dönük uyumluluk istenmediği için migration eklenmedi; kullanıcıya sürüm sonrası ayar sıfırlanabileceği açıkça bildirilmeli.

### P3 — Kalite ve dağıtım

10. **Subprocess testleri:** URL parser, queue state ve argüman üretimi için regresyon testleri mevcut/güncellendi. Gerçek yt-dlp binary, FFmpeg dönüşüm, yarıda kesilen pipe, çok uzun stdout/stderr satırı, Windows process tree ve ağ hatası senaryoları için entegrasyon testleri eklenmeli.
11. **Platform kabul testleri:** macOS ana hedef olsa da Windows/Linux için Finder/Explorer/`xdg-open`, dosya izinleri, atomik config replace, WebView bağımlılıkları ve paket kurulumları gerçek makinelerde doğrulanmalı.
12. **CI:** Arşivde `.github/workflows` CI tanımı yok. macOS/Windows/Linux build matrix'i, Go testleri, TypeScript typecheck/build, release artifact ve imza kontrolleri eklenmeli.
13. **Mobil şablonlar:** `build/ios` ve `build/android` Wails şablonları arşivde var; fakat uygulamanın yt-dlp/FFmpeg binary ve `os/exec` temelli masaüstü akışı mobilde çalışır kabul edilemez. Mobil hedefler ya gerçek cihaz kabul testleriyle desteklenmeli ya da desteklenmeyen scaffold olarak açıkça işaretlenmelidir.
14. **Batch/UI hydration sırası:** UI event aboneliği sonrası backend Snapshot çağrısı yapıyor. Çok erken gelen event ile snapshot yanıtının sırası ters düşerse eski snapshot son event'i geçici olarak ezebilir. Snapshot version/sequence alanı veya event timestamp ile reconciliation uygulanabilir.
15. **Girdi doğrulama kapsamı:** Temel format, çözünürlük, retry ve timeout alanları doğrulanıyor; kullanıcı kontrollü `ExtraArgs`, format sort, referer, proxy ve dosya adı şablonu için daha ayrıntılı uzunluk/karakter sınırları ve kullanıcı rehberliği eklenebilir.

## 7. Doğrulama durumu ve sınırlar

- Kaynaklar ve frontend–backend çağrıları statik olarak incelendi.
- Düzenlenen Go dosyaları `gofmt` ile biçimlendirildi.
- Proje scriptleri çalıştırılmadı.
- `go test`, `go build`, `wails3 build`, `npm ci`, `npm run build`, release/package scriptleri çalıştırılmadı.
- Bu nedenle build/test sonucu **doğrulanmamıştır**. Yeni/yenilenen test senaryoları pakete dahildir ancak çalıştırılmamıştır.
- macOS, Windows ve Linux üzerinde gerçek uygulama çalıştırma / yt-dlp indirme kabul testi yapılmadı.

## 8. Önerilen doğrulama sırası

Kullanıcı ortamında şu sırayla doğrulanması önerilir:

1. Go iş mantığı testleri: `go test ./internal/... ./services/...`
2. Frontend bağımlılık kurulumu ve tip kontrolü: `cd frontend && npm ci && npm run build`
3. Wails binding üretimi gerekiyorsa generated API kontrolü ve ardından masaüstü derleme: `wails3 build`
4. Gerçek uygulamada URL host kötüye kullanımı, playlist reverse, pause/resume/cancel, silinen queued task, batch completion, uzun log satırı ve yt-dlp güncellemesi senaryoları.
5. Windows ve Linux paketleri için ayrı platform smoke testleri.

**Sonuç:** Paket içinde doğrulanabilir kritik kuyruk/URL/iptal sorunları düzeltilmiş, gereksiz ve mimariyle uyumsuz üç parça kaldırılmış, frontend/backend sözleşmeleri sadeleştirilmiş ve README/build tanımları masaüstü uygulamasının gerçek kapsamıyla hizalanmıştır. En önemli kalan işler kalıcı kuyruk, kontrollü kapanış, başlangıç güncelleme–indirme koordinasyonu ve CI/platform kabul testleridir.


## 9. Ürün sitesi, masaüstü UX ve son hata düzeltme turu

Bu ek tur, kullanıcının `wails3 dev` sırasında paylaştığı TypeScript derleme çıktısı ve ürün sitesi/dokümantasyon talebi üzerine gerçekleştirildi.

### 9.1 Paylaşılan TypeScript hataları

| Dosya / konum | Hata | Düzeltme |
|---|---|---|
| `frontend/src/App.tsx` | `info?.kind` okunuyor ancak component içinde `info` selector'ı tanımlı değil (`TS2304`). | `useStore((s) => s.info)` selector'ı eklendi. |
| `frontend/src/components/QueuePanel.tsx` | `upsertBatch` selector'ı tanımlanmış fakat hiç kullanılmıyor (`TS6133` ve `noUnusedLocals`). | Ölü selector kaldırıldı. |

Bu iki düzeltme paylaşılan derleme hatalarının doğrudan kaynaklarına yöneliktir. Wails dev/build yeniden çalıştırılmadığından düzeltmelerin tamamının kullanıcı ortamında başarılı derleme verdiği iddia edilmemektedir.

### 9.2 Masaüstü UX ve ürün kimliği

- Go uygulama adı ve pencere başlığı `Link Downloader` olarak hizalandı; iç Go modülü (`ytdlp-studio`) ve veri klasörü adı değiştirilmedi.
- Bengsoft ürün kimliği, bundle identifier, Windows/macOS/Linux paket metadatası güncellendi; binary/artefact isimleri mevcut release otomasyonuyla uyumlu kalacak şekilde `ytdlp-studio` olarak korundu.
- React ana ekranına ürün yönlendirme metni, analiz–özelleştirme–takip adımları ve bağımlılık durum göstergesi eklendi.
- Sidebar marka alanı ve sistem durumu, analiz boş durumu, kuyruk boş durumu ve önizleme alanı görsel hiyerarşi açısından yenilendi.
- `frontend/src/index.css` üzerinde koyu lacivert, mavi ve turkuaz temelli masaüstü tasarım sistemi; kartlar, form alanları, durum etiketleri, geçişler, klavye odak stilleri, responsive ölçüler ve reduced-motion desteği eklendi.
- Inter Medium font asset'i ve lisans metni pakette tutuldu.

### 9.3 Ürün sitesi ve dokümantasyon

`website/` klasörü tamamen bağımsız statik yayın kökü olacak şekilde oluşturuldu:

- `index.html`: ürün tanıtımı, özellikler, ekran görüntüsü, kullanım akışı, indirme CTA'ları ve GitHub bağlantıları.
- `docs.html`: kullanıcı kurulumu, ekranlar/özellikler, bağımlılıklar, geliştirici ortamı, build, environment değişkenleri, mimari, konfigürasyon ve sorun giderme.
- `styles.css` ve `script.js`: responsive tasarım, hafif scroll reveal, mobil navigasyon ve reduced-motion saygısı.
- `assets/appicon.png`, `assets/screenshot.png`: website dışındaki proje dosyalarına ihtiyaç duymayan, pakete gömülü görsel varlıklar.
- `CNAME`, `robots.txt`, `sitemap.xml`, `README.md`: alan adı ve yayınlama bilgileri.

Site bağlantıları kullanıcı tarafından verilen GitHub deposuna ve GitHub Releases sayfasına yönelir. Gerçek release varlık adları/sürüm numaraları arşivde veya erişilebilen kaynaklarda doğrulanamadığından sabit indirme dosyası URL'si uydurulmadı; ziyaretçi doğrudan Releases sayfasına yönlendirilir.

Kök `README.md` genişletildi; ayrıca `docs/OVERVIEW.md`, `INSTALLATION.md`, `DEVELOPMENT.md`, `ARCHITECTURE.md`, `CONFIGURATION.md` ve `RELEASES.md` proje içi dokümantasyon olarak tutuldu.

### 9.4 Temizleme ve doğruluk düzeltmeleri

- Wails/Vite başlangıç şablonundan kalan ve kaynaklarda kullanılmayan `react.svg`, `wails.png`, `bg-desktop.jpg`, `bg-mobile.jpg` kaldırıldı.
- Sadece npm'in desteklemediği `minimum-release-age` config değerini taşıyan `frontend/.npmrc` kaldırıldı; bu, kullanıcının npm çıktısında gördüğü `Unknown project config` uyarısının kaynağıydı.
- Kaynakta referansı olmayan `build/linux/desktop` şablon klasörü kaldırıldı.
- Taskfile veya paketleme akışında kullanılmayan `build/windows/msix/app_manifest.xml` ve `template.xml` Wails başlangıç örnekleri kaldırıldı; aktif MSIX üretimi `wails3 tool msix` ve `build/config.yml` üzerinden devam eder.
- `build/config.yml` içindeki işlevsel olmayan `My Other Data` örnek metaveri girdisi kaldırıldı.
- Kullanıcıya ait toplu Linux derleme yardımındaki WebKitGTK 4.1 hata metni, scriptin fiilen denetlediği GTK4 + WebKitGTK 6.0 + libsoup-3.0 paketleriyle hizalandı.
- macOS `Taskfile` deployment target ve dev plist minimum sürümü, üretim `Info.plist` ve release script varsayılanıyla aynı olacak şekilde 13.0'a çekildi.
- `docs/RELEASES.md` ve kök README'ye `VERSION`, `TARGETS`, macOS imza/notarization değişkenleri ve gizli bilgilerin güvenli tutulması eklendi.
- Vite 8 sürüm koşulu resmi dokümana göre Node 20.19+ veya 22.12+ olarak güncellendi. Vite 8 bu iki Node hattını belirtir; projedeki `go.mod` ise Go 1.27 ister. 【turn819450search6】【turn819450search1】
- Go test yönergeleri mevcut `scripts/check.sh` içindeki kapsamla uyumlu `go test ./internal/... ./services/...` ve `go vet ./internal/... ./services/...` olarak değiştirildi. Tam Wails binary build öncesinde frontend `dist` çıktısı gerekir.
- Platform gereksinimleri Wails v3.0.0 resmi kurulum bilgisinden ayrıştırılarak yazıldı: Windows WebView2, macOS Xcode Command Line Tools, Linux varsayılan GTK4/WebKitGTK 6.0; iOS/Android desteği deneysel olarak işaretlendi. 【turn819450search0】【turn819450search1】【turn819450search4】

### 9.5 Yayınlama sınırı

`website/` statik dosyaları hazırdır ve GitHub Pages/custom domain kullanımı için `CNAME` içerir. Bununla birlikte `ytdlp.bengsoft.com` alan adı üzerinde DNS değişikliği, hosting hesabı yapılandırması, TLS ve gerçek yayına alma bu çalışma alanından yapılmadı. Site dosyaları `website/` klasörünün içeriği olarak statik host'un web root'una kopyalanmalıdır.

### 9.6 Bu turun doğrulama sınırları

- Kullanıcının gönderdiği hata mesajları üzerinden iki TypeScript kaynağı statik olarak düzeltildi.
- HTML/CSS/JS ve dokümanlar statik içerik incelemesinden geçirildi; görsel tarayıcı testi yapılmadı.
- `wails3 dev`, `wails3 build`, `npm ci`, `npm run build`, Taskfile, `go test`, `go vet` veya release scriptleri çalıştırılmadı.
- Bu nedenle uygulama build'i, site browser davranışı ve işletim sistemi paketlerinin çalışırlığı doğrulanmış değildir.
