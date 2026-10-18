# ✈️ Travel Planner — Hafta Sonu Bilet Fırsatı Avcısı

Türk pasaportuyla gidilebilecek **tüm ülkeler** (vizesiz, kapıda vize, e-vize ve vizeli)
için önümüzdeki tüm hafta sonlarında **cuma gidiş – pazar dönüş** uçak biletlerini tarar.
Bir bilet, o rotanın **normal fiyatından** belirgin şekilde ucuzsa size **"🔥 FIRSAT VAR!"**
bildirimi gönderir (Telegram, telefon push bildirimi / ntfy, e-posta).

## Nasıl çalışır?

1. `src/travel_planner/data/countries.json` içindeki ~190 ülkeden (filtrelere göre) hedef havalimanları seçilir.
2. Bugünden itibaren `weeks_ahead` (varsayılan 52) hafta boyunca her cuma → pazar çifti hesaplanır.
3. Her rota için uçuş fiyatları ay ay çekilir ve **sadece cuma gidiş / pazar dönüş** olan teklifler tutulur;
   her hafta sonu için en ucuz teklif SQLite geçmişine yazılır.
4. **Normal fiyat** = o rotanın son 90 gündeki hafta sonu fiyatlarının **medyanı**.
   Fiyat, normalden en az `%25` ucuzsa (ayarlanabilir) fırsat sayılır.
   İsterseniz `always_notify_below` ile "şu fiyatın altı her zaman fırsattır" diyebilirsiniz.
5. Aynı uçuş tekrar tekrar bildirilmez; sadece fiyat %5 daha düşerse yeniden haber verilir.

Örnek bildirim:

```
🔥 FIRSAT VAR! 1 uygun hafta sonu bileti bulundu

✈️ SAW → BEG · Sırbistan (🟢 Vizesiz)
📅 Cum 06.11.2026 → Paz 08.11.2026
💰 2.450 TL (normal ~4.100 TL, %40 ucuz)
🛫 PC · aktarmasız
🔗 https://www.aviasales.com/search/...
```

## Kurulum

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp config.example.toml config.toml
```

### Uçuş verisi: Travelpayouts (ücretsiz)

1. https://www.travelpayouts.com adresinde ücretsiz hesap açın.
2. Profil → **API token** değerini alın: `export TRAVELPAYOUTS_TOKEN=...`

> Not: Travelpayouts fiyatları son ~48 saatte Aviasales'te yapılan aramalardan önbelleğe alınır.
> Anlık değildir, popüler olmayan rotalarda/tarihlerde veri olmayabilir; tıklayınca güncel fiyatı görürsünüz.
> Yeni bir sağlayıcı eklemek için `providers/base.py` içindeki `FlightProvider` sınıfını uygulamanız yeterli.

### Bildirim kanalları (en az birini seçin)

| Kanal | Ortam değişkenleri | Not |
|---|---|---|
| **ntfy** (en kolay) | `NTFY_TOPIC=benim-gizli-konum-123` | Telefona ntfy uygulamasını kurun, aynı konuya abone olun. Konu adı tahmin edilemez olsun. |
| **Telegram** | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | @BotFather ile bot açın, bota bir mesaj atın, chat id'yi `https://api.telegram.org/bot<TOKEN>/getUpdates` ile bulun. |
| **E-posta** | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_TO` | Gmail için "Uygulama şifresi" kullanın (`smtp.gmail.com`). |

Deneme: `travel-planner test-notify`

## Kullanım

```bash
# API anahtarı olmadan sahte veriyle deneme
travel-planner scan --provider mock --dry-run

# Tüm ülkeler, tüm hafta sonları
travel-planner scan

# Sadece vizesiz + kapıda vize, Avrupa ve Kafkasya, İstanbul ve Ankara çıkışlı
travel-planner scan --visa vizesiz,kapida_vize --region Avrupa,Kafkasya --origin IST,ESB

# Ülke/vize listesi, taranacak tarihler, son taramada her hafta sonunun en ucuzları
travel-planner countries --visa vizesiz
travel-planner weekends
travel-planner cheapest --top 5
```

Tüm ülkeler × 52 hafta sonu taraması yaklaşık 240 rota × 16 ay-çifti ≈ 3.900 API isteğidir
(saniyede ~4 istek ile ~16 dk). Daha hızlı tarama için `[countries]` filtrelerini veya `weeks_ahead` değerini kısın.

## Otomatik çalıştırma

### GitHub Actions (sunucu gerekmez)

`.github/workflows/scan.yml` günde 2 kez tarama yapar ve fiyat geçmişini önbellekte saklar.
Repo → Settings → Secrets and variables → Actions altında `TRAVELPAYOUTS_TOKEN` ve
bildirim kanalınızın değişkenlerini secret olarak ekleyin. Ayarları `config.example.toml` üzerinden değiştirebilirsiniz.

### Kendi bilgisayarınızda / sunucuda (cron)

```cron
17 7,19 * * * cd /yol/Travel-planner && .venv/bin/travel-planner scan >> scan.log 2>&1
```

## Vize verisi hakkında ⚠️

`countries.json` dosyasındaki vize durumları (bordo/umuma mahsus pasaport için) bilgi amaçlıdır,
kurallar sık değişir. Seyahatten önce mutlaka [T.C. Dışişleri Bakanlığı](https://www.mfa.gov.tr)
ve ilgili ülkenin konsolosluğundan teyit edin. Dosyayı düzenleyerek durum, havalimanı veya not ekleyebilirsiniz.
Havalimanı olmayan mikro devletler (Andorra, Lihtenştayn, Monako, San Marino, Vatikan), Filistin ve Kuzey Kore listede yoktur.

## Geliştirme

```bash
pytest -q
```
