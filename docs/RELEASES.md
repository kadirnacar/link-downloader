# Release ve Yayınlama

## Yayın bağlantıları

- Kaynak kod: https://github.com/kadirnacar/link-downloader
- Sürümler ve indirilebilir varlıklar: https://github.com/kadirnacar/link-downloader/releases
- Ürün sitesi: https://ytdlp.bengsoft.com/

## Release kontrol listesi

1. Uygulama metadata'sını (`build/config.yml`) ve frontend marka/sürüm bilgisini gözden geçirin.
2. Wails TypeScript binding'lerinin Go servisleriyle güncel olduğunu doğrulayın.
3. Frontend build ve Go testlerini çalıştırın.
4. Hedef işletim sistemi/mimarisi için üretim build ve paketleme görevlerini çalıştırın.
5. Windows, macOS ve Linux hedeflerinde uygulamayı gerçek masaüstü ortamında açarak smoke test yapın.
6. URL analizi, tekil video, playlist, audio, video, altyazı, pause/resume/cancel, retry, dependency install ve output reveal akışlarını test edin.
7. Release varlıklarını doğru platform/mimari etiketleriyle ekleyin; dosya boyutu, hash ve imza doğrulama bilgilerini paylaşın.
8. Release notlarında desteklenen OS sürümlerini, paket türlerini ve gerekli sistem runtime'larını açıkça yazın.
9. `website/` statik site içeriğini `ytdlp.bengsoft.com` hedefinde yayınlayın.

## Paketleme notları

Repo içinde macOS, Windows ve Linux Taskfile'ları bulunur. Platform paketlerinin gerçekten üretilmiş olması ve release'e eklenmesi, sadece Taskfile varlığından çıkarılamaz; her GitHub Release sayfasındaki varlık listesi esas alınmalıdır.

Wails iOS/Android şablon klasörleri, bu masaüstü ürününün kararlı mobil dağıtım desteği sunduğu anlamına gelmez.

## Yayın güvenilirliği

Release yayınlarında platform başına smoke test, SHA-256 checksum, kaynak sürüm etiketi ve bağımlılık/runtime notlarının birlikte verilmesi önerilir. Kod imzalama ve otomatik güncelleme destekleniyorsa kapsamı ve güven zinciri ayrıca belgelenmelidir; mevcut kodda doğrulanmamış bir release yeteneği kullanıcıya vaat edilmemelidir.


## Release environment değişkenleri

`release.sh` macOS host üzerinde çalışır; değişkenler isteğe bağlıdır ve verilmediklerinde script varsayılanlarını kullanır:

| Değişken | Kullanım | Varsayılan |
| --- | --- | --- |
| `VERSION` | Paket sürümü | `1.0.1` (script içindeki varsayılan; release öncesi sürüm metadatasını da güncelleyin) |
| `TARGETS` | Paketlenecek hedefler (`darwin windows linux`) | `darwin windows linux` |
| `MACOSX_DEPLOYMENT_TARGET` | macOS minimum deployment target | `13.0` |
| `CODESIGN_IDENTITY` | macOS codesign kimliği; `-` ad-hoc imza anlamına gelir | `-` |
| `APPLE_ID` | Notarization için Apple hesabı | Boş; notarization atlanır |
| `APPLE_TEAM_ID` | Notarization Apple Developer Team ID | Boş; notarization atlanır |
| `APPLE_APP_PASSWORD` | Notarization app-specific password | Boş; notarization atlanır |

Notarization için üç Apple değişkeninin de sağlanması ve uygun Developer ID sertifikasının bulunması gerekir. Gerçek kimlik bilgilerini repository dosyalarına, issue'lara veya release loglarına yazmayın; CI secret / güvenli ortam değişkeni kullanın.

Windows imzalama, Wails signing yapılandırması veya Taskfile `SIGN_CERTIFICATE` / `SIGN_THUMBPRINT` değişkenleriyle ayrıca ayarlanır. Linux paketleme araçlarının ek native geliştirme bağımlılıkları ilgili platform Taskfile'larında belirtilir.
