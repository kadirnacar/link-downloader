// ytdlp-studio:playlist-all v2
package services

import (
	"reflect"
	"strconv"
	"strings"

	"github.com/lrstanley/go-ytdlp"
	"ytdlp-studio/internal/model"
)

func plAllHasEntries(e *ytdlp.ExtractedInfo) bool {
	if e == nil {
		return false
	}
	return len(e.Entries) > 0
}

func plAllFlatten(infos []*ytdlp.ExtractedInfo) []*ytdlp.ExtractedInfo {
	var out []*ytdlp.ExtractedInfo

	var walk func(e *ytdlp.ExtractedInfo, depth int)
	walk = func(e *ytdlp.ExtractedInfo, depth int) {
		if e == nil {
			return
		}
		if len(e.Entries) == 0 || depth > 8 {
			out = append(out, e)
			return
		}
		for _, child := range e.Entries {
			walk(child, depth+1)
		}
	}

	for _, info := range infos {
		walk(info, 0)
	}

	return out
}

func plAllDedupe(infos []*ytdlp.ExtractedInfo) []*ytdlp.ExtractedInfo {
	seen := make(map[string]bool)
	var out []*ytdlp.ExtractedInfo

	for _, e := range infos {
		if e == nil {
			continue
		}

		id := plAllString(e, "ID", "")
		url := plAllString(e, "WebpageURL", "")
		key := id + "|" + url

		if key == "|" {
			out = append(out, e)
			continue
		}
		if seen[key] {
			continue
		}
		seen[key] = true
		out = append(out, e)
	}

	return out
}

func plAllPlaylistTitle(infos []*ytdlp.ExtractedInfo, fallback string) string {
	if len(infos) == 0 {
		if fallback != "" {
			return fallback
		}
		return "Playlist"
	}

	root := infos[0]
	if plAllHasEntries(root) {
		if t := plAllString(root, "Title", ""); t != "" {
			return t
		}
	}

	fields := []string{"PlaylistTitle", "Playlist", "Album", "Uploader", "Channel"}
	for _, info := range infos {
		if info == nil {
			continue
		}
		for _, f := range fields {
			if t := plAllString(info, f, ""); t != "" {
				return t
			}
		}
	}

	if root != nil {
		if t := plAllString(root, "Title", ""); t != "" {
			return t
		}
	}

	if fallback != "" {
		return fallback
	}
	return "Playlist"
}

func plAllFirstTitle(infos []*ytdlp.ExtractedInfo) string {
	for _, e := range infos {
		if e == nil {
			continue
		}
		if t := plAllString(e, "Title", ""); t != "" {
			return t
		}
	}
	return ""
}

func plAllIsUnavailable(title string) bool {
	if title == "" {
		return true
	}
	lower := strings.ToLower(title)
	return strings.Contains(lower, "[private video]") ||
		strings.Contains(lower, "[deleted video]") ||
		strings.Contains(lower, "private video") ||
		strings.Contains(lower, "deleted video") ||
		strings.Contains(lower, "unavailable")
}

func plAllEntry(index int, e *ytdlp.ExtractedInfo) model.MediaEntry {
	id := plAllString(e, "ID", "")
	url := plAllString(e, "WebpageURL", "")
	title := plAllString(e, "Title", "")
	duration := plAllFloat(e, "Duration", 0)

	if idx := plAllInt(e, "PlaylistIndex", 0); idx > 0 {
		index = idx
	}

	displayTitle := title
	if displayTitle == "" {
		displayTitle = id
	}

	available := id != "" && !plAllIsUnavailable(title)

	return model.MediaEntry{
		ID:          id,
		URL:         url,
		Title:       displayTitle,
		DurationSec: duration,
		Thumbnail:   "",
		Index:       index,
		Available:   available,
	}
}

func plAllThumbnail(e *ytdlp.ExtractedInfo) string {
	if e == nil {
		return ""
	}

	f := plAllField(reflect.ValueOf(e), "Thumbnails")
	if f.IsValid() {
		if f.Kind() == reflect.Ptr || f.Kind() == reflect.Interface {
			if !f.IsNil() {
				f = f.Elem()
			}
		}
		if f.Kind() == reflect.Slice {
			for i := f.Len() - 1; i >= 0; i-- {
				item := f.Index(i)
				if u := plAllStringFromValue(item, "URL", ""); u != "" {
					return u
				}
			}
		}
	}

	id := plAllString(e, "ID", "")
	if len(id) == 11 {
		return "https://i.ytimg.com/vi/" + id + "/hqdefault.jpg"
	}
	return ""
}

func plAllStringFromValue(v reflect.Value, name string, fallback string) string {
	if !v.IsValid() {
		return fallback
	}
	f := plAllField(v, name)
	if !f.IsValid() {
		return fallback
	}
	return plAllValueString(f, fallback)
}

func plAllString(e *ytdlp.ExtractedInfo, name string, fallback string) string {
	if e == nil {
		return fallback
	}
	f := plAllField(reflect.ValueOf(e), name)
	if !f.IsValid() {
		return fallback
	}
	return plAllValueString(f, fallback)
}

func plAllFloat(e *ytdlp.ExtractedInfo, name string, fallback float64) float64 {
	if e == nil {
		return fallback
	}
	f := plAllField(reflect.ValueOf(e), name)
	if !f.IsValid() {
		return fallback
	}
	return plAllValueFloat(f, fallback)
}

func plAllInt(e *ytdlp.ExtractedInfo, name string, fallback int) int {
	if e == nil {
		return fallback
	}
	f := plAllField(reflect.ValueOf(e), name)
	if !f.IsValid() {
		return fallback
	}
	return plAllValueInt(f, fallback)
}

func plAllField(v reflect.Value, name string) reflect.Value {
	switch v.Kind() {
	case reflect.Ptr, reflect.Interface:
		if v.IsNil() {
			return reflect.Value{}
		}
		return plAllField(v.Elem(), name)
	case reflect.Struct:
		f := v.FieldByName(name)
		if f.IsValid() {
			return f
		}

		t := v.Type()
		for i := 0; i < t.NumField(); i++ {
			sf := t.Field(i)
			if !sf.Anonymous || sf.PkgPath != "" {
				continue
			}
			if res := plAllField(v.Field(i), name); res.IsValid() {
				return res
			}
		}
	}
	return reflect.Value{}
}

func plAllValueString(f reflect.Value, fallback string) string {
	switch f.Kind() {
	case reflect.String:
		return f.String()
	case reflect.Ptr, reflect.Interface:
		if f.IsNil() {
			return fallback
		}
		return plAllValueString(f.Elem(), fallback)
	case reflect.Float32, reflect.Float64:
		return strconv.FormatFloat(f.Float(), 'f', -1, 64)
	case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64:
		return strconv.FormatInt(f.Int(), 10)
	case reflect.Uint, reflect.Uint8, reflect.Uint16, reflect.Uint32, reflect.Uint64:
		return strconv.FormatUint(f.Uint(), 10)
	}
	return fallback
}

func plAllValueFloat(f reflect.Value, fallback float64) float64 {
	switch f.Kind() {
	case reflect.Float32, reflect.Float64:
		return f.Float()
	case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64:
		return float64(f.Int())
	case reflect.Uint, reflect.Uint8, reflect.Uint16, reflect.Uint32, reflect.Uint64:
		return float64(f.Uint())
	case reflect.String:
		if parsed, err := strconv.ParseFloat(strings.TrimSpace(f.String()), 64); err == nil {
			return parsed
		}
	case reflect.Ptr, reflect.Interface:
		if f.IsNil() {
			return fallback
		}
		return plAllValueFloat(f.Elem(), fallback)
	}
	return fallback
}

func plAllValueInt(f reflect.Value, fallback int) int {
	switch f.Kind() {
	case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64:
		return int(f.Int())
	case reflect.Uint, reflect.Uint8, reflect.Uint16, reflect.Uint32, reflect.Uint64:
		return int(f.Uint())
	case reflect.Float32, reflect.Float64:
		return int(f.Float())
	case reflect.String:
		if parsed, err := strconv.Atoi(strings.TrimSpace(f.String())); err == nil {
			return parsed
		}
	case reflect.Ptr, reflect.Interface:
		if f.IsNil() {
			return fallback
		}
		return plAllValueInt(f.Elem(), fallback)
	}
	return fallback
}
