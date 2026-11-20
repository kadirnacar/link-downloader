# Yapılandırma ve Yerel Veri

## Konfigürasyon kökü

Go `os.UserConfigDir()` kullanılır; alt klasör `ytdlp-studio` olarak belirlenmiştir.

| Platform | Konum |
| --- | --- |
| macOS | `~/Library/Application Support/ytdlp-studio/` |
| Windows | `%AppData%\ytdlp-studio\` |
| Linux | `${XDG_CONFIG_HOME:-~/.config}/ytdlp-studio/` |

## Dosyalar

| Dosya / klasör | İçerik |
| --- | --- |
| `settings.json` | İndirme ve yt-dlp seçenekleri (`DownloadOptions`). |
| `app.json` | Worker sayısı, tema, accent, bildirimler, başlangıç dependency kontrolü ve diğer `AppSettings`. |
| `bin/` | Uygulama tarafından yönetilen araç binary'lerinin yerel dizini. |

SettingsService, varsayılan değerlerle başlar; JSON yüklemesi veya model validasyonu başarısız olursa varsayılan ayarlara döner. Kaydetme/sıfırlama işlemleri validasyon uygular. Dosya yazımı geçici dosya ve rename akışıyla yapılır; POSIX sistemlerde klasör/dosya izinleri kullanıcıya özel tutulur.

## İndirme seçenekleri

UI'daki ayarlar model sözleşmesiyle tanımlanır. Temel başlıklar:

- Mode: audio, video, subtitle.
- Audio format/quality.
- Video height/FPS/container/remux.
- Subtitle language, automatic subtitles, format, embed davranışı.
- Output directory ve output filename template.
- Overwrite/continue/mtime/thumbnail/metadata/chapter seçenekleri.
- Fragment concurrency, rate limit, retries, socket timeout.
- Proxy, IP family, geo bypass, user-agent, referer, browser/file cookies.
- Playlist item filter ve reverse order.
- SponsorBlock remove/mark ve uyku aralığı.
- Ek yt-dlp argümanları.

Uygulama, UI'da gösterilen seçenekleri model validasyonundan geçirerek yt-dlp engine argümanlarına dönüştürür.

## Uygulama tercihleri

Uygulama ayarları worker adedi, açık/koyu tema, accent rengi, bildirimler, kuyruk temizleme onayı, panodan otomatik analiz, başlangıç dependency kontrolü, yt-dlp otomatik güncelleme/kanalı, log limit ve varsayılan sekmeyi içerir.

## Environment

`XDG_CONFIG_HOME` Linux config kökünü etkiler. `WAILS_VITE_PORT` yalnızca geliştirme server portunu etkiler. `GOOS`, `GOARCH` ve `CGO_ENABLED` build hedefi/derleme yoluyla ilgilidir; kullanıcı ayarlarının yerine geçmez.
