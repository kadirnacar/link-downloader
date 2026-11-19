// ytdlp-studio:generated v1
import { useEffect, useState } from "react";
import { DepsService, SettingsService } from "../api";
import { useStore } from "../store";
import { SECTIONS } from "../settings/catalog";
import { Field } from "../components/Field";

export function SettingsPage() {
  const section = useStore((s) => s.settingsSection);
  const options = useStore((s) => s.options);
  const app = useStore((s) => s.app);
  const deps = useStore((s) => s.deps);
  const installing = useStore((s) => s.installing);
  const set = useStore((s) => s.set);
  const patchOptions = useStore((s) => s.patchOptions);
  const patchApp = useStore((s) => s.patchApp);
  const [preview, setPreview] = useState<string[] | null>(null);
  const [msg, setMsg] = useState("");
  const [cfgPath, setCfgPath] = useState("");

  useEffect(() => { SettingsService.ConfigPath().then(setCfgPath).catch(() => undefined); }, []);

  async function save() {
    try {
      await SettingsService.Save(options);
      await SettingsService.SaveApp(app);
      setMsg("Ayarlar kaydedildi.");
    } catch (e) { setMsg(String(e)); }
  }
  async function reset() {
    const o = await SettingsService.Reset();
    const a = await SettingsService.ResetApp();
    set({ options: o, app: a });
    setMsg("Varsayılanlara dönüldü.");
  }
  async function showPreview() {
    setPreview(await SettingsService.PreviewArgs(options));
  }
  async function install() {
    set({ installing: true });
    try { set({ deps: await DepsService.InstallDeps() }); setMsg("Bileşenler hazır."); }
    catch (e) { setMsg(String(e)); }
    finally { set({ installing: false }); }
  }
  async function update() {
    setMsg("yt-dlp güncelleniyor…");
    try { setMsg((await DepsService.UpdateYtDlp(app.ytDlpChannel)).trim() || "Güncel."); }
    catch (e) { setMsg(String(e)); }
  }

  const active = SECTIONS.find((s) => s.id === section) ?? SECTIONS[0];
  const store: any = active.target === "app" ? app : options;
  const patch = active.target === "app" ? patchApp : patchOptions;

  return (
    <div className="settings">
      <nav className="settings-nav">
        {SECTIONS.map((s) => (
          <button key={s.id} className={s.id === active.id ? "active" : ""} onClick={() => set({ settingsSection: s.id })}>
            <span className="ico">{s.icon}</span>{s.title}
          </button>
        ))}
        <button className={section === "deps" ? "active" : ""} onClick={() => set({ settingsSection: "deps" })}>
          <span className="ico">⚒</span>Bileşenler
        </button>
      </nav>

      <div className="settings-body">
        <div className="card">
          <div className="card-head">
            <h3>{section === "deps" ? "Bileşenler" : active.title}</h3>
            <div className="inline">
              <button className="btn small" onClick={() => void showPreview()}>Komut önizleme</button>
              <button className="btn small" onClick={() => void reset()}>Sıfırla</button>
              <button className="btn small primary" onClick={() => void save()}>Kaydet</button>
            </div>
          </div>

          {msg && <div className="notice" onClick={() => setMsg("")}>{msg}</div>}

          {section === "deps" ? (
            <div className="deps-grid">
              <div className="status-row"><span>yt-dlp</span><span className={deps?.ytDlp ? "tag good" : "tag bad"}>{deps?.ytDlp ? "Kurulu" : "Eksik"}</span></div>
              <div className="status-row"><span>Sürüm</span><strong>{deps?.ytDlpVersion || "—"}</strong></div>
              <div className="status-row"><span>Yol</span><code>{deps?.ytDlpPath || "—"}</code></div>
              <div className="status-row"><span>ffmpeg</span><span className={deps?.ffmpeg ? "tag good" : "tag bad"}>{deps?.ffmpeg ? "Kurulu" : "Eksik"}</span></div>
              <div className="status-row"><span>ffprobe</span><span className={deps?.ffprobe ? "tag good" : "tag bad"}>{deps?.ffprobe ? "Kurulu" : "Eksik"}</span></div>
              <div className="status-row"><span>JS runtime</span><strong>{deps?.jsRuntime || "—"}</strong></div>
              <div className="field">
                <label>Güncelleme kanalı</label>
                <select value={app.ytDlpChannel} onChange={(e) => patchApp({ ytDlpChannel: e.target.value })}>
                  <option value="stable">stable</option><option value="nightly">nightly</option><option value="master">master</option>
                </select>
              </div>
              <label className="switch">
                <input type="checkbox" checked={app.ytDlpAutoUpdate} onChange={(e) => patchApp({ ytDlpAutoUpdate: e.target.checked })} />
                <span>Açılışta yt-dlp güncelle</span>
              </label>
              <label className="switch">
                <input type="checkbox" checked={app.checkDepsOnStart} onChange={(e) => patchApp({ checkDepsOnStart: e.target.checked })} />
                <span>Açılışta bileşenleri denetle</span>
              </label>
              <div className="inline">
                <button className="btn" onClick={() => void DepsService.CheckDeps().then((d) => set({ deps: d }))}>Yeniden denetle</button>
                <button className="btn primary" disabled={installing} onClick={() => void install()}>{installing ? "Kuruluyor…" : "Eksikleri kur"}</button>
                <button className="btn" onClick={() => void update()}>yt-dlp güncelle</button>
              </div>
            </div>
          ) : (
            <div className="fields-grid">
              {active.fields.map((f) => (
                <Field key={f.k} def={f} value={store[f.k]} onChange={(v) => patch({ [f.k]: v } as any)} />
              ))}
            </div>
          )}

          {preview && (
            <>
              <hr className="divider" />
              <div className="card-head"><h3>yt-dlp komut önizleme</h3>
                <button className="btn small ghost" onClick={() => setPreview(null)}>Kapat</button></div>
              <pre className="console">yt-dlp {preview.join(" ")}</pre>
            </>
          )}
          {cfgPath && <div className="hint">Yapılandırma: <code>{cfgPath}</code></div>}
        </div>
      </div>
    </div>
  );
}
