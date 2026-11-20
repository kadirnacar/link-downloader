# Link Downloader — Genel Bakış

## Amaç

Link Downloader (`ytdlp-studio`), YouTube video ve playlist bağlantılarını analiz etmek, içerik öğelerini seçmek, ses/video/altyazı seçeneklerini belirlemek ve indirme görevlerini masaüstü kuyruğundan yönetmek için geliştirilmiştir.

Uygulama **Wails v3.0.0 + Go + React/TypeScript** tabanlıdır. yt-dlp medya çözümleme/indirme motorudur; FFmpeg ve FFprobe medya işleme ve metadata görevlerinde kullanılır.

## Yetenekler

- URL parse ve video/playlist analizi.
- Playlist içeriğini thumbnail, süre ve sıra numarasıyla önizleme; arama ve toplu seçim.
- Ses formatı: MP3, M4A, OPUS, FLAC, WAV.
- Video çözünürlük ve kapsayıcı seçenekleri: MP4, MKV, WebM.
- Manuel ve otomatik altyazı dilleri, format seçimi ve video altyazı ayarları.
- Ayarlanabilir eşzamanlı worker sayısına sahip indirme kuyruğu.
- Pause, resume, cancel, retry, remove ve clear işlemleri.
- Görev/batch ilerlemesi; hız, ETA ve hata metni.
- Bağımlılık denetimi, kurulum ve yt-dlp güncellemesi.
- Kullanıcıya özel yerel ayarlar, günlük ve bildirim seçenekleri.

## Kullanıcı arayüzü

1. **Analiz:** bağlantı girilir, medya/playlist çözümlemesi yapılır ve öğeler listelenir.
2. **Hızlı kurallar:** ses/video/altyazı modu, kalite, format, çıktı klasörü ve adlandırma belirlenir.
3. **Kuyruk:** görevler ve batch durumu izlenir; görev eylemleri yürütülür.
4. **Ayarlar:** uygulama ve yt-dlp seçenekleri, bağımlılıklar ve argüman önizleme yönetilir.
5. **Günlük:** çalışma sırasında gelen log kayıtları filtrelenip kopyalanabilir.
6. **Hakkında:** uygulama ve çalışma zamanı bağımlılık bilgileri görüntülenir.

## Kapsam ve sınırlar

- Uygulamanın URL doğrulama ve analiz akışı YouTube bağlantıları için tasarlanmıştır; tüm yt-dlp destekli siteler için genel arayüz olarak belgelenmemelidir.
- İndirme kuyruğu çalışma sürecindeki görev durumlarını yönetir. Bu sürümün kuyruk kalıcılığı sunduğu varsayılmamalıdır.
- Android/iOS klasörleri Wails proje şablonlarının parçası olabilir; bunlar kararlı masaüstü uygulama desteğiyle eşdeğer kabul edilmemelidir.
- Ürün paketlerinin gerçek platform kapsamı her GitHub Release varlık listesinde kontrol edilmelidir.

## Lisans ve kullanım

Lisans bilgisi depo kökündeki `LICENSE` dosyasındadır. Platform kullanım koşulları ve telif haklarına uyum kullanıcının sorumluluğundadır.
