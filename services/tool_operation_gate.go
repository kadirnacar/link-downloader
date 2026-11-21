// ytdlp-studio:tool-operation-gate v1
package services

import (
	"context"
	"sync"
	"time"
)

// toolOperationGate prevents a dependency update/replacement from racing with
// any yt-dlp or FFmpeg operation. Readers are downloads and metadata queries;
// writers are install, update and dependency-path refresh operations.
var toolOperationGate sync.RWMutex

func acquireToolRead(ctx context.Context) (func(), error) {
	ticker := time.NewTicker(40 * time.Millisecond)
	defer ticker.Stop()
	for {
		if toolOperationGate.TryRLock() {
			return toolOperationGate.RUnlock, nil
		}
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		case <-ticker.C:
		}
	}
}
