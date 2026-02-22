package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestUIConfigHasEnableStreaming(t *testing.T) {
	// Test che UIConfig abbia il campo EnableStreaming
	config := UIConfig{
		WelcomeMessage:  "Test message",
		EnableStreaming: true,
	}

	if !config.EnableStreaming {
		t.Error("EnableStreaming should be true")
	}

	config.EnableStreaming = false
	if config.EnableStreaming {
		t.Error("EnableStreaming should be false after setting")
	}
}

func TestLLMServerConfigFields(t *testing.T) {
	// Test che LLMServerConfig abbia URL e Timeout
	config := LLMServerConfig{
		URL:     "http://localhost:5005",
		Timeout: 60,
	}

	if config.URL != "http://localhost:5005" {
		t.Errorf("URL mismatch: got %s, want http://localhost:5005", config.URL)
	}
	if config.Timeout != 60 {
		t.Errorf("Timeout mismatch: got %d, want 60", config.Timeout)
	}
}

func TestDefaultConfigHasEnableStreaming(t *testing.T) {
	// Test che il default config abbia EnableStreaming = true
	defaultConfig := getDefaultConfig()

	if !defaultConfig.UI.EnableStreaming {
		t.Error("Default config should have EnableStreaming = true")
	}
}

func TestDefaultConfigLLMServer(t *testing.T) {
	// Test che il default config abbia LLM server configurato
	defaultConfig := getDefaultConfig()

	if defaultConfig.LLMServer.URL == "" {
		t.Error("Default LLMServer.URL should not be empty")
	}
	if defaultConfig.LLMServer.Timeout <= 0 {
		t.Error("Default LLMServer.Timeout should be positive")
	}
}

func TestConfigJSONParsing(t *testing.T) {
	// Test parsing JSON
	jsonData := `{
		"server": {"port": "8080", "host": "localhost"},
		"llm_server": {
			"url": "http://localhost:5005",
			"timeout": 60
		},
		"log": {"level": "info", "file": "test.log"},
		"predefined_questions": [],
		"ui": {
			"welcome_message": "Test",
			"enable_streaming": false
		},
		"transcription": {"enabled": false, "url": ""}
	}`

	var config Config
	err := json.Unmarshal([]byte(jsonData), &config)
	if err != nil {
		t.Fatalf("Failed to parse JSON: %v", err)
	}

	// Verifica LLM server
	if config.LLMServer.URL != "http://localhost:5005" {
		t.Errorf("URL mismatch: got %s, want http://localhost:5005", config.LLMServer.URL)
	}
	if config.LLMServer.Timeout != 60 {
		t.Errorf("Timeout mismatch: got %d, want 60", config.LLMServer.Timeout)
	}

	// Verifica EnableStreaming
	if config.UI.EnableStreaming != false {
		t.Error("EnableStreaming should be false from JSON")
	}
}

func TestConfigJSONParsingEnableStreamingTrue(t *testing.T) {
	// Test parsing JSON con enable_streaming: true
	jsonData := `{
		"server": {"port": "8080", "host": "localhost"},
		"llm_server": {"url": "http://localhost:5005", "timeout": 60},
		"log": {"level": "info", "file": "test.log"},
		"predefined_questions": [],
		"ui": {
			"welcome_message": "Test",
			"enable_streaming": true
		},
		"transcription": {"enabled": false, "url": ""}
	}`

	var config Config
	err := json.Unmarshal([]byte(jsonData), &config)
	if err != nil {
		t.Fatalf("Failed to parse JSON: %v", err)
	}

	if config.UI.EnableStreaming != true {
		t.Error("EnableStreaming should be true from JSON")
	}
}

func TestLoadConfigFromFile(t *testing.T) {
	// Test caricamento config dal file reale se esiste
	configPath := "config/config.json"

	// Cambia directory al root del progetto per trovare il config
	originalDir, _ := os.Getwd()
	if filepath.Base(originalDir) == "app" {
		os.Chdir("..")
		defer os.Chdir(originalDir)
	}

	if _, err := os.Stat(configPath); os.IsNotExist(err) {
		t.Skip("Config file not found, skipping file load test")
	}

	config := LoadConfig()

	// Il file config.json dovrebbe avere enable_streaming configurato
	if !config.UI.EnableStreaming {
		t.Log("Warning: config.json has enable_streaming: false")
	}

	// Verifica che LLM server sia configurato
	if config.LLMServer.URL == "" {
		t.Error("config.json missing llm_server.url")
	}
}
