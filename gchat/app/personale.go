package main

import (
	"encoding/csv"
	"fmt"
	"log"
	"os"
	"strconv"
	"sync"
	"time"
)

type PersonaleRecord struct {
	ASL                             string `json:"asl"`
	DescrizioneAreaStrutturaComplessa string `json:"descrizione_area_struttura_complessa"`
	Descrizione                     string `json:"descrizione"`
	NameFirst                       string `json:"namefirst"`
	NameLast                        string `json:"namelast"`
	CodiceFiscale                   string `json:"codice_fiscale"`
	UserID                          int    `json:"user_id"`
}

// Cache structure for personale data
type personaleCache struct {
	data     map[int]PersonaleRecord
	modTime  time.Time
	mu       sync.RWMutex
}

var (
	cache     = &personaleCache{}
	csvFile   = "data/personale.csv"
)

// LoadPersonaleData loads data with caching based on file modification time
func LoadPersonaleData() (map[int]PersonaleRecord, error) {
	cache.mu.RLock()

	// Check if file exists and get modification time
	info, err := os.Stat(csvFile)
	if err != nil {
		cache.mu.RUnlock()
		return nil, fmt.Errorf("error accessing personale.csv: %v", err)
	}

	// If cache is valid (file hasn't been modified), return cached data
	if cache.data != nil && !info.ModTime().After(cache.modTime) {
		data := cache.data
		cache.mu.RUnlock()
		log.Printf("PERSONALE_CACHE: Using cached data (file unchanged since %s)", cache.modTime.Format("2006-01-02 15:04:05"))
		return data, nil
	}

	cache.mu.RUnlock()

	// Need to reload data - acquire write lock
	cache.mu.Lock()
	defer cache.mu.Unlock()

	// Double-check pattern - another goroutine might have loaded while we waited
	if cache.data != nil && !info.ModTime().After(cache.modTime) {
		log.Printf("PERSONALE_CACHE: Using cached data (loaded by another goroutine)")
		return cache.data, nil
	}

	log.Printf("PERSONALE_CACHE: Loading CSV file (last modified: %s)", info.ModTime().Format("2006-01-02 15:04:05"))

	file, err := os.Open(csvFile)
	if err != nil {
		return nil, fmt.Errorf("error opening personale.csv: %v", err)
	}
	defer file.Close()

	reader := csv.NewReader(file)
	records, err := reader.ReadAll()
	if err != nil {
		return nil, fmt.Errorf("error reading CSV: %v", err)
	}

	if len(records) == 0 {
		return nil, fmt.Errorf("empty CSV file")
	}

	// Skip header row
	records = records[1:]

	personaleMap := make(map[int]PersonaleRecord)
	validRecords := 0

	for _, record := range records {
		if len(record) < 7 {
			continue // Skip malformed records
		}

		userID, err := strconv.Atoi(record[6])
		if err != nil {
			continue // Skip records with invalid user_id
		}

		personale := PersonaleRecord{
			ASL:                             record[0],
			DescrizioneAreaStrutturaComplessa: record[1],
			Descrizione:                     record[2],
			NameFirst:                       record[3],
			NameLast:                        record[4],
			CodiceFiscale:                   record[5],
			UserID:                          userID,
		}

		personaleMap[userID] = personale
		validRecords++
	}

	// Update cache
	cache.data = personaleMap
	cache.modTime = info.ModTime()

	log.Printf("PERSONALE_CACHE: Loaded %d valid records from CSV", validRecords)
	return personaleMap, nil
}

func GetPersonaleByUserID(userID int) (*PersonaleRecord, error) {
	personaleMap, err := LoadPersonaleData()
	if err != nil {
		return nil, err
	}

	if record, exists := personaleMap[userID]; exists {
		return &record, nil
	}

	return nil, fmt.Errorf("user with ID %d not found", userID)
}