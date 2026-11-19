// ytdlp-studio:generated v1
package model

type ParsedURL struct {
	Kind         string `json:"kind"`
	VideoID      string `json:"videoId"`
	ListID       string `json:"listId"`
	CanonicalURL string `json:"canonicalUrl"`
	Ambiguous    bool   `json:"ambiguous"`
	IsMix        bool   `json:"isMix"`
}

type MediaEntry struct {
	ID          string  `json:"id"`
	URL         string  `json:"url"`
	Title       string  `json:"title"`
	DurationSec float64 `json:"durationSec"`
	Thumbnail   string  `json:"thumbnail"`
	Index       int     `json:"index"`
	Available   bool    `json:"available"`
}

type MediaInfo struct {
	Kind    string       `json:"kind"`
	ID      string       `json:"id"`
	Title   string       `json:"title"`
	Entries []MediaEntry `json:"entries"`
}
