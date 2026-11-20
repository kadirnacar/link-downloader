
# ytdlp-studio 🎧

YouTube video ve playlist'lerinden ses/video indirmek için tasarlanmış masaüstü stüdyosu.
[Wails v3](https://wails.io) üzerinde Go backend + React/TypeScript frontend ile geliştirilmiştir;
indirme motoru olarak [yt-dlp](https://github.com/yt-dlp/yt-dlp) ve ffmpeg kullanır.

![ytdlp-studio analiz ekranı](docs/screenshot.png)

---

## ✨ Özellikler

- 🔗 **Akıllı URL analizi** — HTTPS YouTube video, playlist, shorts, live ve mix URL'lerini otomatik ayrıştırır; desteklenmeyen alan adlarını kabul etmez.
- 📋 **Playlist önizleme** — tüm öğeler kapak görseli, sıra no ve süre ile listelenir; arama + toplu seçim.
- 🎵 **Ses / Video kuralları** — MP3/M4A/OPUS/FLAC/WAV + kalite; video için çözünürlük ve kap (mp4/mkv/webm).
- 📁 **Dosya adı şablonları** — `%(playlist_index)03d - %(title)s.%(ext)s` vb.; playlist indeksi uygulama
  tarafında gerçek sıra numarasıyla doldurulur (dosya adında `NA`/`000` oluşmaz).
- ⬇️ **Çok iş parçacıklı kuyruk** — varsayılan 3; ayarlardan 1–8 eşzamanlı worker.
- ⏯️ **Görev kontrolleri** — Duraklat, Devam, İptal, Yeniden dene, Finder'da göster, Tekil sil.
- 🧹 **Toplu işlemler** — Tümünü iptal et, Bitenleri temizle, Tümünü temizle.
- 📊 **Canlı ilerleme** — dosya bazında yüzde/hız/ETA; playlist bazında toplam ilerleme
  (başarısız öğeler de ilerlemeye dahil) ve işlem bitince toast bildirimi.
- 🧰 **Bağımlılık yönetimi** — yt-dlp / ffmpeg / ffprobe / JS runtime eksikse uygulama içinden
  tek tıkla otomatik kurulum; "yt-dlp Güncelle" ile sürüm tazeleme.
- 💾 **Kalıcı ayarlar** — seçenekler OS kullanıcı yapılandırma dizininde atomik olarak ve kullanıcıya özel dosya izinleriyle saklanır.

## 🧱 Teknoloji Yığını

| Katman          | Teknoloji                                    |
| --------------- | -------------------------------------------- |
| Masaüstü kabuk  | Wails v3 (native webview)                    |
| Backend         | Go 1.27, [go-ytdlp](https://github.com/lrstanley/go-ytdlp) |
| Frontend        | React 18, TypeScript, Zustand, Vite          |
| İndirme motoru  | yt-dlp + ffmpeg / ffprobe                    |

## 📦 Gereksinimler

- macOS (geliştirme hedefi; Wails v3 çoklu platform destekler)
- Go **≥ 1.27**
- Node.js **≥ 20.19** (veya **≥ 22.13**) + npm; Vite 8 ve eklentilerinin engine gereksinimi
- Wails v3 CLI:
  ```bash
  go install github.com/wailsapp/wails/v3/cmd/wails3@latest
  ```
- yt-dlp / ffmpeg / ffprobe: **zorunlu değil** — uygulama ilk açılışta eksikleri otomatik kurabilir.

---

## 🚀 Kurulum

```bash
# 1) Depoyu klonla
git clone https://github.com/KULLANICI_ADI/link-downloader.git
cd link-downloader

# 2) Go bağımlılıklarını çöz
go mod tidy

# 3) Frontend bağımlılıklarını kur
cd frontend && npm ci && cd ..

# 4) Wails TypeScript binding'lerini üret
wails3 generate bindings -clean=true -ts -i
```

## 🔨 Derleme

### Geliştirme modu (hot-reload)
```bash
wails3 dev
# veya
task dev
```

### Üretim derlemesi
```bash
wails3 build
# veya
task build
```

#### Windows
```bash
GOOS=windows GOARCH=amd64 wails3 build
```

### macOS paketleme (.app)
```bash
task package
```

### Testler
İş mantığı ve servis testleri:
```bash
go test ./internal/... ./services/...
```
Masaüstü uygulamasının tam derlemesi için `wails3 build` kullanın; bu işlem
`frontend/dist` çıktısını üretip Go uygulamasına gömer.

---

## 🖥️ Kullanım

1. **URL yapıştır** — Analiz sekmesindeki kutuya YouTube bağlantısını yapıştır
   (yapıştırınca analiz otomatik başlar) ya da `Enter` / **Analiz Et** düğmesini kullan.
2. **Kapsam seç** — URL hem video hem playlist içeriyorsa *Sadece video / Tüm playlist* seçicisi görünür.
3. **Öğeleri seç** — Önizleme listesinde arama yap; tek tek veya başlıktaki checkbox ile tümünü işaretle.
   Private/silinmiş öğeler pasif gösterilir ve seçilemez.
4. **Kuralları ayarla** — Sağ panelden Ses/Video modu, format, kalite, çıktı klasörü ve dosya adı şablonunu belirle.
   "Gelişmiş" bölümünde hız limiti, eşzamanlı parça sayısı ve çerez kaynağı bulunur.
5. **İndir** — `⬇ N öğeyi indir` düğmesi kuyruğu başlatır ve otomatik olarak Kuyruk sekmesine geçer.
6. **Kuyruğu yönet** — Her görev satırında: Duraklat / Devam / İptal / Yeniden / Finder'da göster / Sil.
   Üst çubukta: *Tümünü iptal et*, *Bitenleri temizle*, *Tümünü temizle*.
7. **Playlist ilerlemesini izle** — Kuyruk üstündeki özet kartı `tamamlanan/toplam` ve yüzde ilerlemeyi gösterir;
   başarısız öğeler ilerlemeye dahil edilir, işlem bitince sağ altta toast bildirimi çıkar.

### Dosya adı şablonları
| Şablon | Açıklama |
| --- | --- |
| `%(playlist_index)03d - %(title)s.%(ext)s` | Varsayılan; playlistte `001 - Şarkı.mp3` üretir |
| `%(title)s.%(ext)s` | İndeksiz sade ad |
| `%(uploader)s/%(title)s.%(ext)s` | Kanal adıyla alt klasör |

> Playlist indeksi uygulama tarafından doldurulur; tekil video indirmelerinde indeks parçası otomatik kaldırılır.

## ⚙️ Ayarlar

Seçenekler, işletim sisteminin kullanıcı yapılandırma dizinindeki `ytdlp-studio`
klasöründe saklanır:

- macOS: `~/Library/Application Support/ytdlp-studio/`
- Windows: `%AppData%\ytdlp-studio\`
- Linux: `$XDG_CONFIG_HOME/ytdlp-studio/` (tanımlı değilse `~/.config/ytdlp-studio/`)

## 🗂️ Proje Yapısı

```
.
├── main.go                    # Wails uygulaması + servis kayıtları
├── internal/
│   ├── engine/builder.go      # yt-dlp komut satırı kurulumu + şablon çözümü
│   └── model/                 # Ortak modeller ve doğrulama (options, media)
├── services/
│   ├── analyze.go             # URL ayrıştırma + playlist analizi
│   ├── download.go            # Kuyruk, pause/resume, batch ilerleme, olaylar
│   ├── deps.go                # yt-dlp/ffmpeg/ffprobe kurulumu ve güncelleme
│   ├── settings.go            # Kalıcı ayarlar servisi
│   └── events.go              # Wails özel olay kayıtları
└── frontend/
    ├── src/                   # React uygulaması (store, componentler)
    └── bindings/              # Wails tarafından üretilen TS binding'leri
```

<!-- ytdlp-studio:xcompile v1 -->
## 🌍 Cross-Compile (macOS → Windows / Linux)

Wails v3, kök `Taskfile.yml` üzerindeki `GOOS` değişkeni ile görevleri platform
Taskfile'lerine dispatch eder (`windows:`, `linux:`, `darwin:`…). Host işletim
sisteminden farklı bir hedef seçildiğinde derleme, `task setup:docker` ile kurulan
cross-compile Docker imajı içinde gerçekleştirilir.

### Ön hazırlık (tek seferlik)

```bash
task setup:docker     # ~800 MB cross-compile imajı (Linux/Windows araç zincirleri)
wails3 doctor         # ortam doğrulaması
```

### Windows hedefi (macOS üzerinden)

```bash
# Derleme (portable EXE)
GOOS=windows GOARCH=amd64 task build
# eşdeğeri:
wails3 build GOOS=windows GOARCH=amd64
# çıktı: bin/ytdlp-studio.exe
```

- Windows hedefi CGO gerektirmez; hedef makinede **WebView2 Runtime** bulunmalıdır.
- **Paketleme (MSIX):** `makeappx`/`signtool` gibi Windows SDK araçları gerektirir, macOS'ta
  üretilemez. MSIX için bir Windows makinesinde veya CI'da (GitHub Actions `windows-latest`)
  `task install:msix:tools` + `task package` çalıştırın; ya da `bin/ytdlp-studio.exe`
  dosyasını portable olarak dağıtın.

### Linux hedefi (macOS üzerinden)

```bash
# Derleme
GOOS=linux GOARCH=amd64 task build
# Paketleme (çıktı yolu için build/linux/Taskfile.yml / task --list-all)
GOOS=linux GOARCH=amd64 task package
```

- Linux GUI hedefi CGO + WebKitGTK başlıkları gerektirdiğinden **Docker imajı zorunludur**
  (`task setup:docker`).
- Hedef makinede `libwebkit2gtk-4.1` çalışma zamanı kütüphaneleri bulunmalıdır.

### Mimari varyantları

```bash
GOOS=linux GOARCH=arm64 task build      # örn. Raspberry Pi / ARM sunucu
GOOS=windows GOARCH=arm64 task build    # Windows on ARM
```

### Cross-compile notları

- Frontend (`frontend/dist`) platformdan bağımsızdır ve binary'ye gömülür (`//go:embed`).
- yt-dlp / ffmpeg / ffprobe / bun, hedef platforma uygun sürümleriyle **çalışma zamanında**
  otomatik indirilir; cross-build imajına dahil etmenize gerek yoktur.
- `DownloadService.Reveal` macOS'ta Finder, Windows'ta Explorer kullanır; Linux'ta
  dosyanın bulunduğu klasörü `xdg-open` ile açar.
- CI önerisi: matrix kullanarak `windows-latest` üzerinde `task package` (MSIX dahil),
  `ubuntu-latest` + Docker imajı ile `GOOS=linux task build/package`.
<!-- ytdlp-studio:xcompile v1:end -->

## 🧯 Sorun Giderme

| Sorun | Çözüm |
| --- | --- |
| "Eksik bileşenler" bandı görünüyor | Banttaki **Otomatik Kur** düğmesini kullanın |
| İndirme hataları / yaşlı yt-dlp | Üst çubuktan **yt-dlp Güncelle** |
| TS binding hataları | `wails3 generate bindings -clean=true -ts -i` komutunu yeniden çalıştırın |
| Kuyruk takıldı | Görev satırındaki **İptal** ardından **Yeniden** düğmesini kullanın |

## ⚖️ Yasal Uyarı

Bu araç kişisel kullanım amaçlıdır. Telif hakkıyla korunan içerikleri indirmeden önce
ilgili platformun hizmet şartlarını ve yerel yasaları kontrol etmek kullanıcının sorumluluğundadır.