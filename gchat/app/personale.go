package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"sync"
	"time"
)

type PersonaleRecord struct {
	ASL                              string `json:"asl"`
	DescrizioneAreaStrutturaComplessa string `json:"descrizione_area_struttura_complessa"`
	Descrizione                      string `json:"descrizione"`
	NameFirst                        string `json:"namefirst"`
	NameLast                         string `json:"namelast"`
	CodiceFiscale                    string `json:"codice_fiscale"`
	UserID                           int    `json:"user_id"`
	UOS                              string `json:"uos"`
}

// Backend URL impostato da main() dopo LoadConfig()
var backendURL string

func SetBackendURL(url string) {
	backendURL = url
	log.Printf("PERSONALE: Backend URL configurato: %s", url)
}

// Cache per-utente con TTL
type personaleCache struct {
	entries map[int]personaleCacheEntry
	mu      sync.RWMutex
}

type personaleCacheEntry struct {
	record    PersonaleRecord
	fetchedAt time.Time
}

const personaleCacheTTL = 5 * time.Minute

var cache = &personaleCache{
	entries: make(map[int]personaleCacheEntry),
}

func GetPersonaleByUserID(userID int) (*PersonaleRecord, error) {
	if backendURL == "" {
		return nil, fmt.Errorf("backend URL non configurato")
	}

	// Controlla cache
	cache.mu.RLock()
	if entry, ok := cache.entries[userID]; ok && time.Since(entry.fetchedAt) < personaleCacheTTL {
		cache.mu.RUnlock()
		record := entry.record
		return &record, nil
	}
	cache.mu.RUnlock()

	// Chiamata HTTP al backend
	url := fmt.Sprintf("%s/api/personale/%d", backendURL, userID)
	resp, err := shortHTTPClient.Get(url)
	if err != nil {
		return nil, fmt.Errorf("errore chiamata backend personale: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusNotFound {
		return nil, fmt.Errorf("user with ID %d not found", userID)
	}
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("backend personale risposta %d per user_id=%d", resp.StatusCode, userID)
	}

	var record PersonaleRecord
	if err := json.NewDecoder(resp.Body).Decode(&record); err != nil {
		return nil, fmt.Errorf("errore decodifica risposta personale: %v", err)
	}

	// Aggiorna cache
	cache.mu.Lock()
	cache.entries[userID] = personaleCacheEntry{
		record:    record,
		fetchedAt: time.Now(),
	}
	cache.mu.Unlock()

	log.Printf("PERSONALE_API: Caricato user_id=%d da backend", userID)
	return &record, nil
}
