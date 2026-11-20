# Geliştirme ve Derleme

## Araç zinciri

| Araç | Sürüm / gereksinim | Kaynak |
| --- | --- | --- |
| Go | 1.27 (`go.mod`) | https://go.dev/dl/ |
| Node.js | 20.19+ veya 22.12+ (Vite 8 toolchain) | https://nodejs.org/ |
| npm | Node.js ile gelir; `npm ci` kullanılır | https://docs.npmjs.com/ |
| Wails CLI | v3.0.0; `@wailsio/runtime` paketi de 3.0.0 | https://v3.wails.io/ |
| Task | Root/platform Taskfile görevlerini kullanmak için | https://taskfile.dev/ |

Wails platform önkoşulları ve kurulum detayları: https://v3.wails.io/getting-started/installation/

## İlk kurulum

```bash
git clone https://github.com/kadirnacar/link-downloader.git
cd link-downloader

go install github.com/wailsapp/wails/v3/cmd/wails3@v3.0.0

go mod download

cd frontend
npm ci
cd ..

wails3 generate bindings -clean=true -ts -i
```

Wails servis imzaları veya Go model tipleri değiştiğinde TypeScript binding'leri yeniden üretilmelidir. `frontend/bindings` dosyalarını kaynak API'nin yerine elle düzenlemeyin.

## Dev çalıştırma

```bash
wails3 dev
```

Task CLI kullanılıyorsa:

```bash
task dev
```

`build/config.yml`, geliştirme modunda frontend dev server'ını ve Wails build/run sürecini koordine eder. Taskfile'da `WAILS_VITE_PORT` varsayılanı `9245` olarak tanımlanmıştır.

## Build

```bash
wails3 build
```

veya:

```bash
task build
```

Platform hedefi örnekleri (Taskfile cross-target dispatch):

```bash
GOOS=windows GOARCH=amd64 task build
GOOS=linux GOARCH=amd64 task build
GOOS=darwin GOARCH=arm64 task build
```

Linux/Windows çapraz derlemesinde CGO seçimi ve Docker kullanımı, ilgili platform Taskfile görevlerine bağlıdır. Linux GUI hedefinde GTK/WebKitGTK geliştirme paketleri gerekir. Hedef işletim sistemi ve mimarisi için `wails3 doctor` ve Wails resmi yönergelerini takip edin.

## Frontend build ve Go testleri

`main.go`, `frontend/dist` klasörünü `go:embed` ile üretim derlemesine alır. Bu nedenle uygulama binary'sini derlemeden önce frontend build çıktısı oluşturulmalıdır. Birim testleri için depodaki doğrulama kapsamı, `scripts/check.sh` ile aynı şekilde `internal` ve `services` paketleriyle sınırlıdır:

```bash
go test ./internal/... ./services/...
go vet ./internal/... ./services/...
```

Tam uygulama derlemesi için önce `frontend` içinde `npm ci` ve `npm run build`, ardından `wails3 build` çalıştırılır.

Frontend TypeScript compiler `noUnusedLocals` denetimini etkin kullanır. Kullanılmayan selector/import/değişkenler build hatası oluşturur.

## Kullanılan build dosyaları

- `build/config.yml`: Wails uygulama metadata ve dev server yapılandırması.
- `Taskfile.yml`: platform görevlerini dispatch eder.
- `build/Taskfile.yml`: ortak Go modülü, frontend, binding ve build yardımcı görevleri.
- `build/darwin/Taskfile.yml`: macOS build/package (minimum deployment target 13.0).
- `build/windows/Taskfile.yml`: Windows build/installer.
- `build/linux/Taskfile.yml`: Linux build ve paket türleri.

## Environment

| Değişken | İşlev |
| --- | --- |
| `WAILS_VITE_PORT` | Vite geliştirme sunucusunun portu; Taskfile varsayılanı `9245`. |
| `GOOS` | Go hedef işletim sistemi (`windows`, `linux`, `darwin`). |
| `GOARCH` | Go hedef mimarisi (`amd64`, `arm64`). |
| `CGO_ENABLED` | CGO derleme yolunun açık olup olmadığını belirler. |
| `XDG_CONFIG_HOME` | Linux uygulama konfigürasyon kök dizini; tanımlı değilse `~/.config`. |

## Platform gereksinimleri

- Windows: WebView2 Runtime; Windows 10/11'de çoğunlukla ön yüklüdür.
- macOS: macOS 13.0+, Xcode Command Line Tools.
- Linux: GCC/build-essential, pkg-config, GTK4, WebKitGTK 6.0 ve libsoup 3.0 geliştirme paketleri. Varsayılan GTK4/WebKitGTK 6.0 yolu Ubuntu 24.04+, Debian 13+ ve Fedora 40+ gibi dağıtımları hedefler. Daha eski desteklenen dağıtımlar GTK3/WebKit2GTK 4.1 için `-tags gtk3` yoluna ihtiyaç duyabilir; proje cross-build imajı varsayılan GTK4 hattını kullanır.

## Önerilen geliştirme akışı

1. Go servisleri ve model sözleşmelerini değiştirin.
2. Wails TypeScript binding'lerini yeniden üretin.
3. Frontend store/component tiplerini güncelleyin.
4. `npm run build:dev`, `go test ./internal/... ./services/...` ve `go vet ./internal/... ./services/...` ile yerel doğrulama yapın.
5. Hedef platformda `wails3 build` veya platform Taskfile build/package görevlerini çalıştırın.
6. Release paketlerini hedef işletim sistemlerinde gerçek masaüstü ortamında kontrol edin.
