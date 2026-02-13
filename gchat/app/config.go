package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
	"os"
	"time"
)

type Config struct {
	Server             ServerConfig       `json:"server"`
	LLMServer          LLMServerConfig    `json:"llm_server"`
	Log                LogConfig          `json:"log"`
	PredefinedQuestions []PredefinedQuestion `json:"predefined_questions"`
	UI                 UIConfig           `json:"ui"`
	Transcription      TranscriptionConfig `json:"transcription"`
}

type ServerConfig struct {
	Port string `json:"port"`
	Host string `json:"host"`
}

type LLMServerConfig struct {
	URL            string `json:"url"`
	Timeout        int    `json:"timeout"`
	StreamEndpoint string `json:"stream_endpoint"`
}

type LogConfig struct {
	Level      string `json:"level"`
	File       string `json:"file"`
	EnableDebug bool   `json:"enable_debug"`
	DebugFile   string `json:"debug_file"`
}

type PredefinedQuestion struct {
	ID       string `json:"id"`
	Text     string `json:"text"`
	Title    string `json:"title"`
	Question string `json:"question"`
	Category string `json:"category"`
	Color    string `json:"color"`
	Order    int    `json:"order"`
}

type UIConfig struct {
	WelcomeMessage  string `json:"welcome_message"`
	EnableStreaming bool   `json:"enable_streaming"`
}

type TranscriptionConfig struct {
	Enabled bool   `json:"enabled"`
	URL     string `json:"url"`
}

type ServerConfigResponse struct {
	CurrentYear      int    `json:"current_year"`
	DataSourceType   string `json:"data_source_type"`
	Status          string `json:"status"`
}

type ServerStatusResponse struct {
	Status        string                 `json:"status"`
	ModelLoaded   bool                   `json:"model_loaded"`
	CurrentYear   int                    `json:"current_year"`
	DataLoaded    map[string]interface{} `json:"data_loaded"`
	Framework     string                 `json:"framework"`
	LLM           string                 `json:"llm"`
}

func LoadConfig() *Config {
	configPath := "config/config.json"

	if _, err := os.Stat(configPath); os.IsNotExist(err) {
		log.Printf("Config file not found at %s, using defaults", configPath)
		return getDefaultConfig()
	}

	data, err := ioutil.ReadFile(configPath)
	if err != nil {
		log.Printf("Error reading config file: %v, using defaults", err)
		return getDefaultConfig()
	}

	var config Config
	if err := json.Unmarshal(data, &config); err != nil {
		log.Printf("Error parsing config file: %v, using defaults", err)
		return getDefaultConfig()
	}

	return &config
}

func GetCurrentYearFromServer(llmServerURL string) (int, error) {
	client := &http.Client{
		Timeout: 5 * time.Second,
	}

	// Prova prima l'endpoint /config
	resp, err := client.Get(llmServerURL + "/config")
	if err == nil {
		defer resp.Body.Close()
		if resp.StatusCode == 200 {
			body, err := ioutil.ReadAll(resp.Body)
			if err == nil {
				var configResp ServerConfigResponse
				if json.Unmarshal(body, &configResp) == nil {
					log.Printf("SERVER_CONFIG: Anno corrente dal server: %d", configResp.CurrentYear)
					return configResp.CurrentYear, nil
				}
			}
		}
	}

	// Fallback: prova endpoint /status
	resp, err = client.Get(llmServerURL + "/status")
	if err == nil {
		defer resp.Body.Close()
		if resp.StatusCode == 200 {
			body, err := ioutil.ReadAll(resp.Body)
			if err == nil {
				var statusResp ServerStatusResponse
				if json.Unmarshal(body, &statusResp) == nil && statusResp.CurrentYear > 0 {
					log.Printf("SERVER_STATUS: Anno corrente dal server: %d", statusResp.CurrentYear)
					return statusResp.CurrentYear, nil
				}
			}
		}
	}

	return 0, fmt.Errorf("impossibile ottenere anno corrente dal server")
}

func getDefaultConfig() *Config {
	return &Config{
		Server: ServerConfig{
			Port: "8080",
			Host: "localhost",
		},
		LLMServer: LLMServerConfig{
			URL:            "http://localhost:5005",
			Timeout:        30,
			StreamEndpoint: "/webhooks/rest/webhook/stream",
		},
		Log: LogConfig{
			Level:       "info",
			File:        "log/app.log",
			EnableDebug: false,
			DebugFile:   "log/gias_api_debug.log",
		},
		PredefinedQuestions: []PredefinedQuestion{
			{
				ID:       "help_general",
				Text:     "Come posso aiutarti?",
				Title:    "Ottieni informazioni generali sulle funzionalità disponibili",
				Question: "Come puoi aiutarmi?",
				Category: "generale",
				Order:    1,
			},
			{
				ID:       "activities_plan_a",
				Text:     "Attività Piano A",
				Title:    "Visualizza le attività associate al piano A",
				Question: "Quali attività ha il piano A?",
				Category: "piani",
				Order:    2,
			},
			{
				ID:       "activities_plan_b",
				Text:     "Attività Piano B",
				Title:    "Visualizza le attività associate al piano B",
				Question: "Quali attività ha il piano B?",
				Category: "piani",
				Order:    3,
			},
			{
				ID:       "contact_info",
				Text:     "Contatti",
				Title:    "Informazioni per contattare il supporto tecnico",
				Question: "Come posso contattare il supporto?",
				Category: "generale",
				Order:    4,
			},
		},
		UI: UIConfig{
			WelcomeMessage:  "Sono Gi, il tuo assistente virtuale. Come posso aiutarti a utilizzare al meglio il sistema Gisa?",
			EnableStreaming: true,
		},
		Transcription: TranscriptionConfig{
			Enabled: false,
			URL:     "",
		},
	}
}

// GetBackendStatus ritorna lo status completo del backend incluso il nome del modello LLM
func GetBackendStatus() *ServerStatusResponse {
	cfg := LoadConfig()
	llmServerURL := cfg.LLMServer.URL
	if llmServerURL == "" {
		llmServerURL = "http://localhost:5005"
	}

	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Get(llmServerURL + "/status")
	if err != nil {
		log.Printf("BACKEND_STATUS_ERROR: %v", err)
		return &ServerStatusResponse{
			Status:    "error",
			Framework: "LangGraph",
			LLM:       "unavailable",
		}
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return &ServerStatusResponse{
			Status:    "error",
			Framework: "LangGraph",
			LLM:       "unavailable",
		}
	}

	body, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		return &ServerStatusResponse{
			Status:    "error",
			Framework: "LangGraph",
			LLM:       "unavailable",
		}
	}

	var statusResp ServerStatusResponse
	if err := json.Unmarshal(body, &statusResp); err != nil {
		return &ServerStatusResponse{
			Status:    "error",
			Framework: "LangGraph",
			LLM:       "unavailable",
		}
	}

	log.Printf("BACKEND_STATUS_OK: framework=%s, llm=%s", statusResp.Framework, statusResp.LLM)
	return &statusResp
}