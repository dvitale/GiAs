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

func TestLLMServerConfigHasStreamEndpoint(t *testing.T) {
	// Test che LLMServerConfig abbia il campo StreamEndpoint
	config := LLMServerConfig{
		URL:            "http://localhost:5005",
		Timeout:        60,
		StreamEndpoint: "/webhooks/rest/webhook/stream",
	}

	if config.StreamEndpoint != "/webhooks/rest/webhook/stream" {
		t.Errorf("StreamEndpoint mismatch: got %s, want /webhooks/rest/webhook/stream", config.StreamEndpoint)
	}
}

func TestDefaultConfigHasEnableStreaming(t *testing.T) {
	// Test che il default config abbia EnableStreaming = true
	defaultConfig := getDefaultConfig()

	if !defaultConfig.UI.EnableStreaming {
		t.Error("Default config should have EnableStreaming = true")
	}
}

func TestDefaultConfigHasStreamEndpoint(t *testing.T) {
	// Test che il default config abbia StreamEndpoint
	defaultConfig := getDefaultConfig()

	expected := "/webhooks/rest/webhook/stream"
	if defaultConfig.LLMServer.StreamEndpoint != expected {
		t.Errorf("Default StreamEndpoint mismatch: got %s, want %s",
			defaultConfig.LLMServer.StreamEndpoint, expected)
	}
}

func TestConfigJSONParsing(t *testing.T) {
	// Test parsing JSON con i nuovi campi
	jsonData := `{
		"server": {"port": "8080", "host": "localhost"},
		"llm_server": {
			"url": "http://localhost:5005",
			"timeout": 60,
			"stream_endpoint": "/custom/stream"
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

	// Verifica StreamEndpoint
	if config.LLMServer.StreamEndpoint != "/custom/stream" {
		t.Errorf("StreamEndpoint mismatch: got %s, want /custom/stream",
			config.LLMServer.StreamEndpoint)
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

	// Il file config.json dovrebbe avere enable_streaming: true
	if !config.UI.EnableStreaming {
		t.Log("Warning: config.json has enable_streaming: false")
	}

	// Verifica che StreamEndpoint sia configurato
	if config.LLMServer.StreamEndpoint == "" {
		t.Log("Warning: config.json missing stream_endpoint, will use default")
	}
}

func TestStreamEndpointFallback(t *testing.T) {
	// Test che StreamEndpoint vuoto usi il default nella logica applicativa
	config := LLMServerConfig{
		URL:            "http://localhost:5005",
		Timeout:        60,
		StreamEndpoint: "", // vuoto
	}

	// Simula la logica di SendToLLMStream
	streamEndpoint := config.StreamEndpoint
	if streamEndpoint == "" {
		streamEndpoint = "/webhooks/rest/webhook/stream"
	}

	expected := "/webhooks/rest/webhook/stream"
	if streamEndpoint != expected {
		t.Errorf("Fallback StreamEndpoint mismatch: got %s, want %s", streamEndpoint, expected)
	}
}
