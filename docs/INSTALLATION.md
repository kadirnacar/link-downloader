# Kurulum ve Kullanım

## Yayın paketini indirme

Güncel paketler: https://github.com/kadirnacar/link-downloader/releases

Release sayfasında işletim sistemi ve mimarinize uygun varlığı seçin. Paket adları, imzalama durumu ve platform kapsamı sürüme göre değişebilir; release açıklamasını okuyun.

## İlk çalıştırma

1. İndirilen paketi release notlarında belirtilen şekilde kurun veya arşivi çıkarın.
2. Link Downloader'ı başlatın.
3. Uygulamanın Bileşenler ekranında yt-dlp, FFmpeg, FFprobe ve JavaScript runtime durumunu kontrol edin.
4. Eksik bileşenler varsa uygulamadaki kurulum seçeneğini kullanın. Kurulum için internet erişimi gerekir.
5. Analiz ekranındaki alana YouTube video veya playlist URL'si yapıştırın.

## Analiz ve indirme

1. Bağlantıyı analiz edin. Playlist URL'sinde kapsam seçimi sunulursa sadece video veya tüm playlist seçin.
2. Önizleme listesindeki öğeleri kontrol edin. Kullanılamayan içerikler devre dışı gösterilir.
3. Ses, video veya altyazı modunu seçin.
4. Format, kalite/çözünürlük, çıktı klasörü ve dosya adı şablonunu ayarlayın.
5. İndir düğmesiyle seçilen öğeleri kuyruğa gönderin.
6. Kuyruk ekranından ilerleme, hız, kalan süre ve görev durumlarını takip edin.

## Kuyruk eylemleri

- **Duraklat / Devam:** tek bir görevi veya toplu işlemi yönetir.
- **İptal:** etkin görevi sonlandırır.
- **Yeniden:** başarısız/iptal edilmiş görevi tekrar kuyruğa alır.
- **Klasörde göster:** tamamlanmış dosyanın konumunu dosya yöneticisinde açar.
- **Sil / Bitenleri temizle / Tümünü temizle:** kuyruk kayıtlarını temizler.

## Sistem gereksinimleri

### Release paketini çalıştırma

Platforma özel gereksinimler release açıklamasında belirtilir. Wails v3 masaüstü hedeflerinde Windows WebView2 kullanır, macOS native WebView ile çalışır ve Linux GTK/WebKitGTK bağımlılıklarına ihtiyaç duyar. Bazı release paketleri ek bağımlılıkları paketleyebilir veya sistemde bulunmasını bekleyebilir; varlık notlarını kontrol edin.

### Kaynak koddan çalıştırma

- Go 1.27 (bu deponun `go.mod` hedef sürümü)
- Node.js 20.19+ veya 22.12+ ve npm
- Wails CLI v3.0.0
- macOS: macOS 13.0+, Xcode Command Line Tools
- Windows: WebView2 Runtime
- Linux: GCC/build-essential, pkg-config, GTK4, WebKitGTK 6.0 ve libsoup 3.0 geliştirme paketleri (varsayılan yol Ubuntu 24.04+, Debian 13+, Fedora 40+ gibi güncel dağıtımlar)

## Sorun giderme

| Durum | Kontrol |
| --- | --- |
| Eksik bileşen uyarısı | Ayarlar → Bileşenler ekranında durumu kontrol edin; eksikleri kurup yeniden denetleyin. |
| URL analiz edilemiyor | URL'nin YouTube video/playlist bağlantısı olduğunu ve içeriğin erişilebilir olduğunu kontrol edin. |
| İndirme hatası | Günlük ekranındaki hata metnini inceleyin; yt-dlp sürümünü ve ağ/çerez seçeneklerini kontrol edin. |
| macOS/Linux uygulaması açılmıyor | OS native WebView ve build gereksinimlerini, `wails3 doctor` çıktısını ve release açıklamasını kontrol edin. |
| Kuyrukta görev takıldı | Görevi kontrollü biçimde iptal edin; ardından gerekirse yeniden deneyin. |

## Yasal sorumluluk

İçerik indirmeden önce ilgili platformun kullanım şartlarına, içerik sahibinin izinlerine ve yerel mevzuata uyun.
