// ytdlp-studio:generated v1
package services

import "testing"

func TestParseURL(t *testing.T) {
	s := &AnalyzeService{}
	cases := []struct {
		name, raw, kind, video, list string
		ambiguous, mix, wantErr      bool
	}{
		{"video", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "video", "dQw4w9WgXcQ", "", false, false, false},
		{"short", "https://youtu.be/dQw4w9WgXcQ?si=abc", "video", "dQw4w9WgXcQ", "", false, false, false},
		{"playlist", "https://www.youtube.com/playlist?list=PLabc123", "playlist", "", "PLabc123", false, false, false},
		{"ambiguous", "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLabc123", "video", "dQw4w9WgXcQ", "PLabc123", true, false, false},
		{"shorts", "https://www.youtube.com/shorts/dQw4w9WgXcQ", "video", "dQw4w9WgXcQ", "", false, false, false},
		{"mix", "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=RDdQw4w9WgXcQ", "video", "dQw4w9WgXcQ", "RDdQw4w9WgXcQ", true, true, false},
		{"music", "https://music.youtube.com/watch?v=dQw4w9WgXcQ", "video", "dQw4w9WgXcQ", "", false, false, false},
		{"other", "https://vimeo.com/123456", "unknown", "", "", false, false, false},
		{"invalid", "bu bir url değil", "unknown", "", "", false, false, true},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			p, err := s.ParseURL(c.raw)
			if c.wantErr {
				if err == nil {
					t.Fatalf("hata bekleniyordu")
				}
				return
			}
			if err != nil {
				t.Fatalf("beklenmeyen hata: %v", err)
			}
			if p.Kind != c.kind || p.VideoID != c.video || p.ListID != c.list || p.Ambiguous != c.ambiguous || p.IsMix != c.mix {
				t.Fatalf("uyuşmazlık: %+v", p)
			}
		})
	}
}
