// ytdlp-studio:generated v1
package services

import "github.com/wailsapp/wails/v3/pkg/application"

func init() {
	application.RegisterEvent[TaskProgress]("task:progress")
	application.RegisterEvent[DepStatus]("deps:status")
}
