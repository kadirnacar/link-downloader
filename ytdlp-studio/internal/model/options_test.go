// ytdlp-studio:generated v1
package model

import "testing"

func TestDefaultOptionsValid(t *testing.T) {
	o := DefaultOptions()
	if o.OutputDir == "" {
		t.Skip("home dizini bulunamadı")
	}
	if err := Validate(o); err != nil {
		t.Fatalf("varsayılanlar geçersiz: %v", err)
	}
}

func TestValidateRejects(t *testing.T) {
	base := DefaultOptions()
	muts := []func(o *DownloadOptions){
		func(o *DownloadOptions) { o.Mode = "gif" },
		func(o *DownloadOptions) { o.AudioFormat = "ogg" },
		func(o *DownloadOptions) { o.AudioQuality = "99" },
		func(o *DownloadOptions) { o.OutputDir = "" },
		func(o *DownloadOptions) { o.NameTemplate = "%(title)s" },
		func(o *DownloadOptions) { o.ConcurrentFragments = 0 },
	}
	for i, mut := range muts {
		o := base
		mut(&o)
		if err := Validate(o); err == nil {
			t.Fatalf("case %d: hata bekleniyordu", i)
		}
	}
}
