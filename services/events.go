// ytdlp-studio:generated v1
// ytdlp-studio:events v3
package services

import "github.com/wailsapp/wails/v3/pkg/application"

func init() {
	application.RegisterEvent[TaskProgress]("task:progress")
	application.RegisterEvent[BatchProgress]("batch:progress")
	application.RegisterEvent[BatchProgress]("batch:completed")
	application.RegisterEvent[DepStatus]("deps:status")
	application.RegisterEvent[LogLine]("log:line")
}
